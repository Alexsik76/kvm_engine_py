import base64
import structlog
import httpx
from aiohttp import web
from urllib.parse import urlparse
from app.auth.node_handlers import require_auth

log = structlog.get_logger()

@require_auth
async def signal_offer_handler(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON body")

    sdp = body.get("sdp")
    sdp_type = body.get("type")
    if not sdp or sdp_type != "offer":
        return web.Response(status=400, text="Missing sdp or invalid type")

    settings = request.app.get("settings")
    if not settings:
        log.error("settings_not_found_in_app")
        return web.Response(status=500, text="Internal Server Error")

    mediamtx_url = f"http://{settings.mediamtx_webrtc_address.rstrip('/')}/{settings.stream_name}/whep"

    headers = {"Content-Type": "application/sdp"}
    if settings.mediamtx_user and settings.mediamtx_pass:
        auth_str = f"{settings.mediamtx_user}:{settings.mediamtx_pass}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded_auth}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                mediamtx_url,
                content=sdp,
                headers=headers,
            )
            if response.status_code not in (200, 201):
                log.error("mediamtx_offer_rejected", status=response.status_code, body=response.text)
                return web.Response(status=502, text="Streaming server rejected the offer")

            session_path = response.headers.get("Location")
            session_url = None
            if session_path:
                if session_path.startswith("http"):
                    session_url = session_path
                else:
                    parsed_base = urlparse(mediamtx_url)
                    session_url = f"{parsed_base.scheme}://{parsed_base.netloc}{session_path}"

            return web.json_response({
                "sdp": response.text,
                "type": "answer",
                "session_url": session_url
            })
        except httpx.RequestError as exc:
            log.error("mediamtx_unreachable", url=mediamtx_url, error=str(exc))
            return web.Response(status=502, text="Streaming server unreachable")

@require_auth
async def signal_ice_handler(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON body")

    candidate = body.get("candidate")
    session_url = body.get("session_url")

    settings = request.app.get("settings")
    if not settings:
        log.error("settings_not_found_in_app")
        return web.Response(status=500, text="Internal Server Error")

    target_url = session_url
    if not target_url:
        target_url = f"http://{settings.mediamtx_webrtc_address.rstrip('/')}/{settings.stream_name}/whep"

    headers = {"Content-Type": "application/trickle-ice-sdpfrag"}
    if settings.mediamtx_user and settings.mediamtx_pass:
        auth_str = f"{settings.mediamtx_user}:{settings.mediamtx_pass}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {encoded_auth}"

    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            await client.patch(
                target_url,
                content=candidate or "",
                headers=headers
            )
        except Exception as exc:
            log.warning("ice_candidate_forwarding_failed", url=target_url, error=str(exc))

    return web.Response(status=204)
