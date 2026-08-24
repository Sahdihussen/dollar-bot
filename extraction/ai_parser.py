import asyncio
import json
import logging
import re
from typing import Optional

import httpx
import config

logger = logging.getLogger(__name__)


def _extract_json_array(content: str) -> list[dict]:
    """Parse a JSON array from model output, tolerating fences and prose."""
    if not content:
        return []
    content = content.strip()
    # Strip markdown code fences (```json ... ```)
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.M)
    content = re.sub(r"\s*```$", "", content)
    try:
        parsed = json.loads(content)
    except Exception:
        start = content.find("[")
        end = content.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            parsed = json.loads(content[start:end + 1])
        except Exception:
            return []
    if isinstance(parsed, list):
        return [o for o in parsed if isinstance(o, dict)]
    if isinstance(parsed, dict):
        if isinstance(parsed.get("observations"), list):
            return [o for o in parsed["observations"] if isinstance(o, dict)]
        return [parsed] if parsed.get("rate") else []
    return []

SYSTEM_PROMPT = """You are an Iraqi USD/IQD market-rate extraction engine. You read Telegram posts in Arabic, Kurdish, and mixed text and extract individual market observations.

RULES:
1. Extract ONLY information explicitly supported by the post. Never invent rates.
2. Return a JSON array of observations. Each observation has:
   - city: normalized English (baghdad, sulaymaniyah, erbil, mosul, basra, kirkuk, duhok)
   - city_raw: original city text
   - rate: integer (normalized to 100 USD = IQD). e.g. 152850
   - rate_role: MARKET, BUY, SELL, OFFICIAL, or UNKNOWN
   - quote_label_raw: original label (ع, ط, بيع, شراء, etc.)
   - quote_label_normalized: عرض, طلب, SELL, BUY, or null
   - dollar_category_raw: original category (پێنجی, سوور, ستاندارد, خبط, etc.)
   - dollar_category_normalized: 5000_IQD_CATEGORY, 25000_IQD_CATEGORY, STANDARD_MIX, MIXED, BLUE_CATEGORY, WHITE_CATEGORY, or UNKNOWN
   - time_context: CURRENT, PREVIOUS, FORECAST, HISTORICAL, or UNKNOWN
   - market_layer: bourse, exchange_shops, trader_groups, local_market, or UNKNOWN
   - product: "usd_iqd" (default) for the IQD-per-100-USD rate; "silver_kg" for silver priced per kilogram; "dubai_lira" for the Dubai gold lira coin.
   - denomination: 100 (default for usd_iqd), or other if explicitly stated
   - confidence: 0.0 to 1.0
   - evidence_text: exact text snippet that produced this observation
3. One post can contain MULTIPLE observations (different cities, categories, labels, products).
4. Numbers like 80, 18, 4 in "80 شین + 18 سپی + 4 پەنجایی" are NOTE_COMPOSITION, not rates.
5. Official rates (السعر الرسمي, البنك المركزي) must have rate_role=OFFICIAL.
6. Do NOT calculate or average rates. Just extract.
7. If unsure about a value, set confidence < 0.5.
8. For product=usd_iqd normalize the rate to IQD per 100 USD (e.g. 152.85 → 152850). For product=silver_kg or dubai_lira the rate is its USD price (e.g. 2180, 958) — do NOT multiply or normalize it.
9. Detect product from text: قاڵب زیو / زیوی پاڵم / زیو / silver / kilo silver → silver_kg; لیرەی کەپسی دوبەی / دوباي / لیرا / gold lira → dubai_lira; otherwise usd_iqd (default).
10. Return ONLY the JSON array, no other text."""

USER_PROMPT_TEMPLATE = """Extract all market observations from this Telegram post — USD/IQD dollar rates, and silver-per-kg / Dubai-lira prices.

Preprocessed context:
{preprocessed_context}

Original post text:
---
{original_text}
---

Return a JSON array of observations. Each observation must have these fields:
city, city_raw, rate, rate_role, quote_label_raw, quote_label_normalized,
dollar_category_raw, dollar_category_normalized, time_context, market_layer,
product, denomination, confidence, evidence_text

If the post contains no extractable rate data, return an empty array: []"""


async def call_orcarouter(text: str, preprocessed: dict) -> Optional[list[dict]]:
    """Call OrcaRouter API (OpenAI-compatible meta-router) as primary provider."""
    if not config.ORCAROUTER_API_KEY:
        logger.warning("No OrcaRouter API key configured")
        return None

    prompt_context = json.dumps({
        "city": preprocessed.get("city"),
        "label": preprocessed.get("label"),
        "category": preprocessed.get("category"),
        "market": preprocessed.get("market"),
        "is_official": preprocessed.get("is_official"),
        "time_context": preprocessed.get("time_context"),
        "candidate_rates": preprocessed.get("candidate_rates", []),
    }, ensure_ascii=False)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        preprocessed_context=prompt_context,
        original_text=text,
    )

    async with httpx.AsyncClient(timeout=45.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    "https://api.orcarouter.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.ORCAROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.ORCAROUTER_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                return _extract_json_array(content)
            except httpx.HTTPStatusError as e:
                # 429 (rate limit) and 5xx are transient: back off and retry.
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
                    continue
                logger.error(f"OrcaRouter API error: {e}")
                return None
            except Exception as e:
                logger.error(f"OrcaRouter API error: {e}")
                return None
    return None


async def call_mistral(text: str, preprocessed: dict) -> Optional[list[dict]]:
    """Call Mistral AI (free-tier OpenAI-compatible endpoint)."""
    if not config.MISTRAL_API_KEY:
        logger.warning("No Mistral API key configured")
        return None

    prompt_context = json.dumps({
        "city": preprocessed.get("city"),
        "label": preprocessed.get("label"),
        "category": preprocessed.get("category"),
        "market": preprocessed.get("market"),
        "is_official": preprocessed.get("is_official"),
        "time_context": preprocessed.get("time_context"),
        "candidate_rates": preprocessed.get("candidate_rates", []),
    }, ensure_ascii=False)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        preprocessed_context=prompt_context,
        original_text=text,
    )

    async with httpx.AsyncClient(timeout=45.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.MISTRAL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.MISTRAL_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                return _extract_json_array(content)
            except httpx.HTTPStatusError as e:
                # 429 (rate limit) and 5xx are transient: back off and retry.
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
                    continue
                logger.error(f"Mistral API error: {e}")
                return None
            except Exception as e:
                logger.error(f"Mistral API error: {e}")
                return None
    return None


async def call_groq(text: str, preprocessed: dict) -> Optional[list[dict]]:
    """Call Groq API for AI parsing."""
    if not config.GROQ_API_KEY:
        logger.warning("No Groq API key configured")
        return None
    
    prompt_context = json.dumps({
        "city": preprocessed.get("city"),
        "label": preprocessed.get("label"),
        "category": preprocessed.get("category"),
        "market": preprocessed.get("market"),
        "is_official": preprocessed.get("is_official"),
        "time_context": preprocessed.get("time_context"),
        "candidate_rates": preprocessed.get("candidate_rates", []),
    }, ensure_ascii=False)
    
    user_prompt = USER_PROMPT_TEMPLATE.format(
        preprocessed_context=prompt_context,
        original_text=text,
    )
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                
                return _extract_json_array(content)
            except httpx.HTTPStatusError as e:
                # 429 (rate limit) and 5xx are transient: back off and retry.
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
                    continue
                logger.error(f"Groq API error: {e}")
                return None
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                return None
    return None


async def call_openrouter(text: str, preprocessed: dict) -> Optional[list[dict]]:
    """Call OpenRouter API as fallback."""
    if not config.OPENROUTER_API_KEY:
        logger.warning("No OpenRouter API key configured")
        return None
    
    prompt_context = json.dumps({
        "city": preprocessed.get("city"),
        "label": preprocessed.get("label"),
        "category": preprocessed.get("category"),
        "market": preprocessed.get("market"),
        "is_official": preprocessed.get("is_official"),
        "time_context": preprocessed.get("time_context"),
        "candidate_rates": preprocessed.get("candidate_rates", []),
    }, ensure_ascii=False)
    
    user_prompt = USER_PROMPT_TEMPLATE.format(
        preprocessed_context=prompt_context,
        original_text=text,
    )
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.OPENROUTER_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                return _extract_json_array(content)
            except httpx.HTTPStatusError as e:
                # 429 (rate limit) and 5xx are transient: back off and retry.
                if e.response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
                    continue
                logger.error(f"OpenRouter API error: {e}")
                return None
            except Exception as e:
                logger.error(f"OpenRouter API error: {e}")
                return None
    return None


async def parse_with_ai(
    text: str,
    preprocessed: dict,
    providers: Optional[list] = None,
) -> tuple[list[dict], bool]:
    """
    AI semantic parsing with OrcaRouter primary, then Mistral, Groq, OpenRouter.

    Returns (observations, all_failed):
      - observations: list of observation dicts from the first provider that
        answered (which may legitimately be an empty list when the post has no
        extractable rates)
      - all_failed: True only when every provider errored out (returned None).
        The deterministic regex fallback should run ONLY in that case, so a
        working AI's "no rates here" verdict is never overridden.
    """
    if providers is None:
        providers = [call_orcarouter, call_mistral, call_groq, call_openrouter]

    for provider in providers:
        result = await provider(text, preprocessed)
        if result is not None:
            logger.info(f"{provider.__name__} parsed {len(result)} observations")
            return result, False

    logger.error("All AI providers failed")
    return [], True
