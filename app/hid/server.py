import asyncio
import json
import base64
import structlog
import aiohttp
from aiohttp import web
from app.ws.server import WSServer
from app.hid.manager import HIDManager
from app.hid.auth import validate_access_token
from app.config import Settings

log = structlog.get_logger()

class HIDServer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.hid = HIDManager(settings.keyboard_device, settings.mouse_device)
        self.ws_server = WSServer(port=settings.hid_port)
        
        # Setup routes
        self.ws_server.add_route("GET", "/ws/control", self.ws_handler)

    async def start(self):
        # Initialize HID Manager
        await self.hid.init()
        # Start WS Server
        await self.ws_server.start()

    async def stop(self):
        await self.ws_server.stop()
        await self.hid.close()

    async def ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        token = request.query.get("token")
        if not token:
            return web.Response(status=401, text="Unauthorized: Missing token")

        user_id = validate_access_token(token, self.settings.jwt_secret)
        if not user_id:
            return web.Response(status=401, text="Unauthorized: Invalid token")

        log.info("ws_client_connected", user_id=user_id, ip=request.remote)

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get("type")
                        payload = data.get("data")
                        
                        if not payload:
                            log.warning("missing_data_in_ws_message")
                            continue

                        if msg_type == "keyboard":
                            raw_keys = payload.get("keys", [])
                            if isinstance(raw_keys, str):
                                try:
                                    keys_list = list(base64.b64decode(raw_keys))
                                except Exception:
                                    log.warning("failed_to_decode_base64_keys")
                                    keys_list = []
                            else:
                                keys_list = raw_keys

                            await self.hid.send_key_report(
                                modifiers=payload.get("modifiers", 0),
                                keys=keys_list
                            )
                        elif msg_type == "mouse":
                            await self.hid.send_mouse_report(
                                buttons=payload.get("buttons", 0),
                                x=payload.get("x", 0),
                                y=payload.get("y", 0),
                                wheel=payload.get("wheel", 0)
                            )
                    except json.JSONDecodeError:
                        log.warning("invalid_json_received")
                    except Exception as e:
                        log.error("error_processing_ws_message", error=str(e))
                
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.error("ws_connection_closed_with_error", error=str(ws.exception()))
        finally:
            log.info("ws_client_disconnected", user_id=user_id, ip=request.remote)
            await self.hid.clear_all()
        
        return ws


