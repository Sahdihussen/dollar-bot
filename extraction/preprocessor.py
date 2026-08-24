import re
from typing import Optional

import config

# ─── Arabic/Kurdish numeral normalization ───
ARABIC_NUMS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_numbers(text: str) -> str:
    """Normalize Arabic/Kurdish numerals and number formatting."""
    text = text.translate(ARABIC_NUMS)
    # Remove thousands separators (comma, dot, space, arabic comma)
    text = re.sub(r"(\d)[,٬،\.\s](\d{3})", r"\1\2", text)
    # Continue removing separators for multi-group numbers
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"(\d)[,٬،\.\s](\d{3})", r"\1\2", text)
    return text


# ─── City detection ───
CITY_MAP = {
    "بغداد": "baghdad", "baghdad": "baghdad", "بوغدان": "baghdad",
    "سلێمانی": "sulaymaniyah", "سلێماني": "sulaymaniyah", "سليمانيه": "sulaymaniyah",
    "السليمانية": "sulaymaniyah", "سلیمانی": "sulaymaniyah",
    "sulaymaniyah": "sulaymaniyah", "slemani": "sulaymaniyah",
    "هەولێر": "erbil", "اربيل": "erbil", "أربيل": "erbil",
    "erbil": "erbil", "hewler": "erbil",
    "مووسڵ": "mosul", "الموصل": "mosul", "نینەوا": "mosul",
    "نينوى": "mosul", "mosul": "mosul", "mosul": "mosul",
    "بەسرە": "basra", "البصرة": "basra", "basra": "basra",
    "کەرکووک": "kirkuk", "كركوك": "kirkuk", "kirkuk": "kirkuk",
    "دهۆک": "duhok", "دهوك": "duhok", "duhok": "duhok",
    "کەربەلا": "karbala", "كربلاء": "karbala", "karbala": "karbala",
    "نەجەف": "najaf", "النجف": "najaf", "najaf": "najaf",
    "سامراء": "samarra", "samarra": "samarra",
}

# ─── Label normalization ───
LABEL_MAP = {
    "ع": "عرض", "عرض": "عرض",
    "ط": "طلب", "طلب": "طلب",
    "بيع": "SELL", "فرۆشتن": "SELL", "فروش": "SELL",
    "شراء": "BUY", "شرا": "BUY", "کڕین": "BUY",
}

# ─── Category normalization ───
CATEGORY_MAP = {
    "پێنجی": "5000_IQD_CATEGORY", "پینجی": "5000_IQD_CATEGORY",
    "خمسات": "5000_IQD_CATEGORY", "شين": "5000_IQD_CATEGORY",
    "شین": "BLUE_CATEGORY",
    "دەیی": "10000_IQD_CATEGORY", "عشرات": "10000_IQD_CATEGORY",
    "عشر": "10000_IQD_CATEGORY",
    "سوور": "25000_IQD_CATEGORY", "سور": "25000_IQD_CATEGORY",
    "احمر": "25000_IQD_CATEGORY", "أحمر": "25000_IQD_CATEGORY",
    "ستاندارد": "STANDARD_MIX", "ستەندارد": "STANDARD_MIX",
    "خبط": "MIXED",
    "ازرق": "BLUE_CATEGORY", "أزرق": "BLUE_CATEGORY",
    "أبيض": "WHITE_CATEGORY", "ابيض": "WHITE_CATEGORY",
    "سپي": "WHITE_CATEGORY", "سپی": "WHITE_CATEGORY",
}

# ─── Market layer detection ───
MARKET_MAP = {
    "الكفاح": "AL_KIFAH_BOURSE", "كفاح": "AL_KIFAH_BOURSE",
    "بورصة الكفاح": "AL_KIFAH_BOURSE",
    "الحارثية": "AL_HARITHIYA_BOURSE", "بورصة الحارثية": "AL_HARITHIYA_BOURSE",
    "السموأل": "AL_SAMAWAL_MARKET",
    "اسكان": "ERBIL_ISKAN", "أربيل - اسكان": "ERBIL_ISKAN",
    "اربيل إسكان": "ERBIL_ISKAN",
    "صيرفات": "EXCHANGE_OFFICES", "مكاتب": "EXCHANGE_OFFICES",
    "كروبات": "GROUP_MARKET", "كروبات بغداد": "BAGHDAD_GROUP_MARKET",
    "بورصة": "BOURSE", "البورصات": "BOURSES",
}

# ─── Official rate markers ───
OFFICIAL_MARKERS = [
    "السعر الرسمي", "نرخی فەرمی", "البنك المركزي",
    "البنك المركزي العراقي", "فەرمی", "official",
]

# ─── Channel -> default city (high-confidence only) ───
# Used by the deterministic fallback when a post from a city-specific channel
# doesn't name its city in the text.
CHANNEL_CITY_MAP = {
    "borsa_erbil": "erbil",
    "borsakurdstan": "sulaymaniyah",
    "borsat_alkfah": "baghdad",
    "iraqborsa": "baghdad",
}

# ─── Time context words ───
TIME_CONTEXT_MAP = {
    "الآن": "CURRENT", "هسه": "CURRENT", "ئێستا": "CURRENT",
    "لحظة بلحظة": "CURRENT", "وقت النشر": "CURRENT",
    "اليوم": "CURRENT", "am": "CURRENT",
    "أمس": "HISTORICAL", "قبل": "HISTORICAL",
    "صباح اليوم": "CURRENT", "صباح": "CURRENT",
    "مساء اليوم": "CURRENT", "مساء": "CURRENT",
    "غداً": "FORECAST", "تحديث": "CURRENT",
    "أخر الأسعار": "CURRENT", "آخر الأسعار": "CURRENT",
}


def _match_longest_first(mapping: dict, text: str, lower: bool = False) -> tuple[Optional[str], Optional[str]]:
    """Match map keys by longest-first so specific terms win over substrings.

    e.g. "بيع" must match before the single character "ع" inside it.
    """
    haystack = text.lower() if lower else text
    for raw, normalized in sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True):
        needle = raw.lower() if lower else raw
        if needle in haystack:
            return normalized, raw
    return None, None


def detect_city(text: str) -> tuple[Optional[str], Optional[str]]:
    """Detect city from text. Returns (normalized_city, raw_city_text)."""
    return _match_longest_first(CITY_MAP, text, lower=True)


def detect_label(text: str) -> tuple[Optional[str], Optional[str]]:
    """Detect quote label. Returns (normalized_label, raw_label)."""
    return _match_longest_first(LABEL_MAP, text)


def detect_category(text: str) -> tuple[Optional[str], Optional[str]]:
    """Detect dollar category. Returns (normalized_category, raw_category)."""
    return _match_longest_first(CATEGORY_MAP, text)


def detect_market_layer(text: str) -> tuple[Optional[str], Optional[str]]:
    """Detect market/layer. Returns (normalized_market, raw_market)."""
    return _match_longest_first(MARKET_MAP, text)


def is_official_rate(text: str) -> bool:
    """Check if text contains official rate markers."""
    return any(marker in text for marker in OFFICIAL_MARKERS)


def detect_time_context(text: str) -> str:
    """Detect time context from text."""
    for raw, context in TIME_CONTEXT_MAP.items():
        if raw in text:
            return context
    return "UNKNOWN"


def extract_rates_from_text(text: str) -> list[dict]:
    """Extract candidate rate numbers from text using regex."""
    normalized = normalize_numbers(text)
    rates = []
    
    # Pattern: rate followed by currency symbols
    for m in re.finditer(r"(\d{4,6})\s*(?:\$|USD|دولار|دۆلار)", normalized):
        val = int(m.group(1))
        rates.append({"value": val, "evidence": m.group(0)})
    
    # Pattern: 100$ = rate
    for m in re.finditer(r"(?:100\$|100\s*دولار)\s*[=:]\s*(\d{4,6})", normalized):
        val = int(m.group(1))
        rates.append({"value": val, "evidence": m.group(0)})
    
    # Pattern: rate with label (ع, ط, بيع, شراء)
    for m in re.finditer(r"(\d{4,6})\s*(ع|ط|عرض|طلب|بيع|شراء)", normalized):
        val = int(m.group(1))
        rates.append({"value": val, "evidence": m.group(0)})
    
    # Pattern: plain 6-digit numbers that look like rates (130000-170000 range).
    # Uses digit-only lookarounds instead of \b because Arabic/Kurdish letters are
    # word characters in regex, so a rate glued to a word (e.g. "فرۆشتن154000")
    # has no word boundary between the letter and the digit.
    for m in re.finditer(r"(?<!\d)(\d{6})(?!\d)", normalized):
        val = int(m.group(1))
        if 130000 <= val <= 170000:
            rates.append({"value": val, "evidence": m.group(0)})
    
    # Deduplicate by value
    seen = set()
    unique = []
    for r in rates:
        if r["value"] not in seen:
            seen.add(r["value"])
            unique.append(r)
    
    return unique


def preprocess(text: str) -> dict:
    """
    Run full deterministic preprocessing on a Telegram post.
    Returns structured context for the AI parser.
    """
    city, city_raw = detect_city(text)
    label, label_raw = detect_label(text)
    category, category_raw = detect_category(text)
    market, market_raw = detect_market_layer(text)
    is_official = is_official_rate(text)
    time_context = detect_time_context(text)
    candidate_rates = extract_rates_from_text(text)
    
    return {
        "original_text": text,
        "normalized_text": normalize_numbers(text),
        "city": city,
        "city_raw": city_raw,
        "label": label,
        "label_raw": label_raw,
        "category": category,
        "category_raw": category_raw,
        "market": market,
        "market_raw": market_raw,
        "is_official": is_official,
        "time_context": time_context,
        "candidate_rates": candidate_rates,
    }


def build_fallback_observations(preprocessed: dict, post_id: int, source: str) -> list[dict]:
    """
    Build conservative observations from the deterministic regex layer.

    Used when every AI provider fails so the market board keeps flowing.
    Only in-band USD/IQD candidates (140k-165k per 100 USD) with a city are
    accepted; rates outside the sanity band are dropped.
    """
    candidates = preprocessed.get("candidate_rates", [])
    if not candidates:
        return []

    city = preprocessed.get("city")
    if not city:
        # Fall back to the channel's known default city (high-confidence only).
        city = CHANNEL_CITY_MAP.get((source or "").lower())
    if not city:
        return []
    label = preprocessed.get("label")
    label_raw = preprocessed.get("label_raw")
    category = preprocessed.get("category")
    category_raw = preprocessed.get("category_raw")
    market = preprocessed.get("market") or "local_market"
    time_context = preprocessed.get("time_context") or "UNKNOWN"

    if label in ("عرض", "SELL"):
        role = "SELL"
    elif label in ("طلب", "BUY"):
        role = "BUY"
    else:
        role = "MARKET"

    observations = []
    seen = set()
    for cand in candidates:
        rate = cand.get("value")
        if not rate:
            continue
        rate = int(rate)
        if not (config.SANITY_MIN_RATE <= rate <= config.SANITY_MAX_RATE):
            continue
        if rate in seen:
            continue
        seen.add(rate)
        observations.append({
            "city": city,
            "city_raw": preprocessed.get("city_raw"),
            "rate": rate,
            "rate_role": role,
            "quote_label_raw": label_raw,
            "quote_label_normalized": label if label in ("عرض", "طلب", "SELL", "BUY") else None,
            "dollar_category_raw": category_raw,
            "dollar_category_normalized": category,
            "time_context": time_context,
            "market_layer": market,
            "product": "usd_iqd",
            "denomination": 100,
            "confidence": 0.6 if (city and label) else 0.45,
            "evidence_text": cand.get("evidence", ""),
            "raw_post_id": post_id,
            "source": source,
        })
    return observations
