import datetime
import structlog
from aiohttp import web
from app.hid.auth import validate_access_token

log = structlog.get_logger()

def require_auth(handler):
    async def wrapped(request: web.Request) -> web.Response:
        settings = request.app.get('settings')
        if not settings:
            log.error("settings_not_found_in_app")
            return web.Response(status=500, text="Internal Server Error")

        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.query.get("token")

        if not token:
            return web.Response(status=401, text="Unauthorized: Missing token")

        user_id = validate_access_token(token, settings.jwt_secret)
        if not user_id:
            return web.Response(status=401, text="Unauthorized: Invalid token")

        return await handler(request)
    return wrapped

def get_node_metadata(settings, created_at: str) -> dict:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": settings.node_id,
        "name": settings.node_name,
        "status": "online",
        "stream_name": settings.stream_name,
        "has_front_panel": settings.has_front_panel,
        "machine_info": settings.machine_info,
        "screenshot": None,
        "last_seen_at": now_iso,
        "created_at": created_at,
        "tunnel_url": settings.public_host or None,
        "ws_port": settings.hid_port,
        "mediamtx_api_port": 9997
    }

@require_auth
async def nodes_list_handler(request: web.Request) -> web.Response:
    settings = request.app.get('settings')
    created_at = request.app.get('created_at', "")
    node_data = get_node_metadata(settings, created_at)
    return web.json_response([node_data])

@require_auth
async def node_detail_handler(request: web.Request) -> web.Response:
    settings = request.app.get('settings')
    created_at = request.app.get('created_at', "")
    node_data = get_node_metadata(settings, created_at)
    return web.json_response(node_data)

@require_auth
async def node_status_handler(request: web.Request) -> web.Response:
    settings = request.app.get('settings')
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    return web.json_response({
        "id": settings.node_id,
        "status": "online",
        "last_seen_at": now_iso
    })
