import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import config
import logs as logs_module
from scheduler.jobs import create_scheduler
from bot.telegram_bot import create_bot_app, broadcast_text, reset_bot_app
from listener.userbot import start_userbot
from dashboard_data import dashboard_state, safe_sources, safe_targets
from templates import VARIABLES, render_template
from output.formatter import format_market_board

# ─── Logging setup ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logs_module.install()

# ─── FastAPI health server ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan — startup and shutdown."""
    logger.info("FastAPI health server started")
    yield
    logger.info("FastAPI health server stopped")


app = FastAPI(
    title="Dollar Bot Health",
    lifespan=lifespan,
)

# CORS: the static dashboard may be served from a different origin
# (e.g. the Freebuff static deploy) while the API runs here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "running", "service": "dollar-bot"}


@app.get("/api/dashboard")
async def dashboard_api():
    return dashboard_state()


@app.get("/api/logs")
async def logs_api(limit: int = 200, level: str = ""):
    return {"logs": logs_module.recent(limit=min(limit, 500), level=level)}


@app.post("/api/logs/clear")
async def logs_clear():
    logs_module.clear()
    return {"ok": True}


class SourceUpdate(BaseModel):
    active: bool


@app.post("/api/sources/{username}")
async def update_source(username: str, update: SourceUpdate):
    import database as db
    try:
        result = db.get_client().table("source_channels").update({"active": update.active}).eq("username", username).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Source not found")
        return {"ok": True, "source": result.data[0]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Supabase is unavailable or the channels table is missing") from exc


class TemplatePayload(BaseModel):
    id: int | None = None
    name: str
    body: str
    destination: str = "all"


@app.get("/api/templates")
async def templates_api():
    import database as db
    try:
        rows = db.get_templates()
        return {"templates": rows, "variables": VARIABLES, "demo_data": False}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Template storage is unavailable") from exc


@app.post("/api/templates/preview")
async def template_preview(payload: TemplatePayload):
    return render_template(payload.body, dashboard_state())


@app.post("/api/templates/send")
async def send_template(payload: TemplatePayload):
    """Render a template and publish it to the chosen destination audience."""
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Template body is empty")
    rendered = render_template(payload.body, dashboard_state())
    if rendered["unknown_variables"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot send: unknown variables " + ", ".join(rendered["unknown_variables"]),
        )
    sent = await broadcast_text(rendered["rendered"], payload.destination)
    return {"sent": len(sent), "recipients": sent}


class SettingPayload(BaseModel):
    enabled: bool


@app.get("/api/settings/source_link")
async def get_source_link_setting():
    import database as db
    return {"enabled": db.get_setting("show_source_link", "off") == "on"}


@app.post("/api/settings/source_link")
async def set_source_link_setting(payload: SettingPayload):
    import database as db
    db.set_setting("show_source_link", "on" if payload.enabled else "off")
    return {"enabled": payload.enabled}


@app.post("/api/subscribers/{chat_id}/toggle")
async def toggle_subscriber(chat_id: int):
    import database as db
    row = db.toggle_subscriber(chat_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"ok": True, "subscribed": row.get("subscribed"), "subscriber": row}


@app.post("/api/templates")
async def save_template(payload: TemplatePayload):
    import database as db
    if not payload.name.strip() or not payload.body.strip():
        raise HTTPException(status_code=400, detail="Template name and body are required")
    row = db.upsert_template(payload.id, payload.name, payload.body, payload.destination)
    if not row:
        raise HTTPException(status_code=503, detail="Template storage is unavailable. Run migration 003.")
    return {"template": row}


@app.delete("/api/templates/{template_id}")
async def remove_template(template_id: int):
    import database as db
    if not db.delete_template(template_id):
        raise HTTPException(status_code=503, detail="Template could not be deleted")
    return {"ok": True}


@app.post("/api/targets/{chat_id}/toggle")
async def toggle_target(chat_id: int):
    import database as db
    try:
        rows = db.get_client().table("publish_targets").select("enabled").eq("chat_id", chat_id).limit(1).execute().data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Publishing target not found")
        enabled = not bool(rows[0].get("enabled"))
        result = db.get_client().table("publish_targets").update({"enabled": enabled}).eq("chat_id", chat_id).execute()
        return {"ok": True, "enabled": enabled, "target": result.data[0] if result.data else None}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Supabase is unavailable or the publish_targets table is missing") from exc


@app.get("/api/metals")
async def metals_api():
    """Latest silver-kg and Dubai-lira observations for the metals board."""
    import database as db
    try:
        silver = db.get_recent_by_product("silver_kg", limit=4)
        lira = db.get_recent_by_product("dubai_lira", limit=4)
        return {"silver_kg": silver, "dubai_lira": lira}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Supabase is unavailable or the observations table is missing") from exc


@app.post("/api/publish/board")
async def publish_board():
    """Build the current market board and publish it to all live destinations."""
    state = dashboard_state()
    snapshots = state.get("snapshots", [])
    if not snapshots:
        raise HTTPException(status_code=400, detail="No current market data to publish yet")
    board = format_market_board(snapshots)
    sent = await broadcast_text(board, "all")
    return {"sent": len(sent), "recipients": sent}


# ─── React/Vite frontend ───
DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the React/Vite frontend from dist/ when it has been built."""
    index = os.path.join(DIST_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return HTMLResponse(
        "<pre style='font:16px/1.6 system-ui;padding:24px'>Dollar Bot — frontend not built yet. Run <code>vite build</code>.</pre>"
    )


if os.path.isdir(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA fallback: serve real files, otherwise index.html. Never shadow API routes."""
        if full_path.startswith("api/") or full_path == "health":
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = os.path.join(DIST_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        index = os.path.join(DIST_DIR, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"detail": "Not found"}, status_code=404)


# ─── Self-ping keep-alive ───
# Free hosts (e.g. Render) spin down web services after ~15 min without inbound
# HTTP traffic. External cron pingers are primary; this self-ping is a safety net
# that keeps traffic flowing even if every external pinger fails.
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
SELF_PING_INTERVAL = int(os.environ.get("SELF_PING_SECONDS", "600"))


async def self_ping():
    """Ping our own /health endpoint periodically so the instance never idles out."""
    if not RENDER_EXTERNAL_URL:
        logger.info("Self-ping disabled (RENDER_EXTERNAL_URL not set)")
        return
    url = f"{RENDER_EXTERNAL_URL}/health"
    logger.info(f"Self-ping enabled -> {url} every {SELF_PING_INTERVAL}s")
    while True:
        await asyncio.sleep(SELF_PING_INTERVAL)
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
            logger.info(f"Self-ping -> {resp.status_code}")
        except Exception as exc:
            logger.warning(f"Self-ping failed: {exc}")


async def run_bot():
    """Run the Telegram Bot API bot, restarting automatically on failure.

    Like the userbot, a transient bot failure must not take the whole app down:
    on error the cached application is dropped (it is single-use) and a fresh
    one is built after a short backoff.
    """
    while True:
        try:
            application = create_bot_app()

            logger.info("Starting Telegram bot...")
            await application.initialize()
            await application.start()
            await application.updater.start_polling()

            logger.info("Telegram bot started successfully")

            # Keep running
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
        reset_bot_app()
        logger.warning("Telegram bot stopped; restarting in 30 seconds")
        await asyncio.sleep(30)


# ─── Main entry point ───
async def main():
    """Start all three concurrent components."""
    logger.info("=== Dollar Bot Starting ===")
    
    port = int(os.environ.get("PORT", "8080"))
    
    # Create scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")
    
    # Start FastAPI in background
    config_uvicorn = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config_uvicorn)
    
    # Run all three concurrently
    tasks = [
        asyncio.create_task(server.serve(), name="fastapi"),
        asyncio.create_task(run_bot(), name="telegram-bot"),
        asyncio.create_task(start_userbot(), name="telethon-userbot"),
        asyncio.create_task(self_ping(), name="self-ping"),
    ]
    
    logger.info(f"All components starting on port {port}")
    
    # Wait for any task to complete (they should run forever)
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.exception():
                logger.error(f"Task {task.get_name()} failed: {task.exception()}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown()
        for task in tasks:
            task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
