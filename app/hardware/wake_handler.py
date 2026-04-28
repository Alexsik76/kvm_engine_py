import asyncio
import structlog
from aiohttp import web
from app.hid.auth import validate_access_token

log = structlog.get_logger()


def make_wake_handler(hw_manager, jwt_secret: str):
    async def wake_handler(request: web.Request) -> web.Response:
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.query.get("token")

        if not token:
            log.warning("wake_unauthorized", reason="missing_token", ip=request.remote)
            return web.Response(status=401, text="Unauthorized: Missing token")

        user_id = validate_access_token(token, jwt_secret)
        if not user_id:
            log.warning("wake_unauthorized", reason="invalid_token", ip=request.remote)
            return web.Response(status=401, text="Unauthorized: Invalid token")

        log.info("wake_requested", user_id=user_id, ip=request.remote)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, hw_manager.force_rebind_gadget)
            await loop.run_in_executor(None, hw_manager.wake_host)
            log.info("wake_completed", user_id=user_id)
            return web.json_response({"status": "ok"})
        except Exception as e:
            log.error("wake_failed", user_id=user_id, error=str(e))
            return web.json_response(
                {"status": "error", "message": "wake operation failed"},
                status=500,
            )

    return wake_handler
