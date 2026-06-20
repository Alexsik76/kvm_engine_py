import bcrypt
import structlog
from aiohttp import web
from app.auth.tokens import create_access_token, create_refresh_token, verify_refresh_token

log = structlog.get_logger()

async def login_handler(request: web.Request) -> web.Response:
    settings = request.app.get('settings')
    if not settings:
        log.error("settings_not_found_in_app")
        return web.Response(status=500, text="Internal Server Error")

    try:
        data = await request.post()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return web.Response(status=401, text="Unauthorized: Missing credentials")

        if username != settings.device_user_login:
            log.warning("login_failed", reason="invalid_username", username=username)
            return web.Response(status=401, text="Unauthorized: Invalid credentials")

        hashed_password = settings.device_password_hash
        if not hashed_password:
            log.warning("login_failed", reason="empty_password_hash")
            return web.Response(status=401, text="Unauthorized: Invalid credentials")

        is_correct = bcrypt.checkpw(
            password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

        if not is_correct:
            log.warning("login_failed", reason="incorrect_password", username=username)
            return web.Response(status=401, text="Unauthorized: Invalid credentials")

        sub = "device"
        access_token = create_access_token(sub, settings.jwt_secret, settings.access_token_minutes)
        refresh_token = create_refresh_token(sub, settings.jwt_secret, settings.refresh_token_minutes)

        return web.json_response({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        })

    except Exception as e:
        log.error("login_handler_failed", error=str(e))
        return web.Response(status=500, text="Internal Server Error")

async def refresh_handler(request: web.Request) -> web.Response:
    settings = request.app.get('settings')
    if not settings:
        log.error("settings_not_found_in_app")
        return web.Response(status=500, text="Internal Server Error")

    try:
        body = await request.json()
        refresh_token = body.get("refresh_token")

        if not refresh_token:
            return web.Response(status=401, text="Unauthorized: Missing refresh token")

        sub = verify_refresh_token(refresh_token, settings.jwt_secret)
        if not sub:
            log.warning("refresh_failed", reason="invalid_or_expired_token")
            return web.Response(status=401, text="Unauthorized: Invalid or expired refresh token")

        access_token = create_access_token(sub, settings.jwt_secret, settings.access_token_minutes)
        new_refresh_token = create_refresh_token(sub, settings.jwt_secret, settings.refresh_token_minutes)

        return web.json_response({
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        })

    except Exception as e:
        log.error("refresh_handler_failed", error=str(e))
        return web.Response(status=500, text="Internal Server Error")
