import asyncio
import json
import structlog
import aiohttp
from aiohttp import web

from app.hid.auth import validate_access_token
from app.hardware.front_panel import FrontPanelController, FrontPanelNotConnectedError

log = structlog.get_logger()


async def front_panel_ws_handler(
    request: web.Request,
    controller: FrontPanelController,
    jwt_secret: str,
) -> web.StreamResponse:
    token = request.query.get("token")
    if not token:
        log.warning("front_panel_ws_unauthorized", ip=request.remote, reason="missing")
        return web.Response(status=401, text="Unauthorized: Missing token")

    user_id = validate_access_token(token, jwt_secret)
    if not user_id:
        log.warning("front_panel_ws_unauthorized", ip=request.remote, reason="invalid")
        return web.Response(status=401, text="Unauthorized: Invalid token")

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    log.info("front_panel_ws_connected", user_id=user_id, ip=request.remote)
    
    # Send initial status
    initial_led = controller.get_status()
    if initial_led:
        await ws.send_json({"type": "led_status", **initial_led})
    
    await ws.send_json({
        "type": "video_status", 
        "status": controller.get_video_status()
    })

    queue = controller.subscribe()

    reader_task: asyncio.Task | None = None
    writer_task: asyncio.Task | None = None

    async def reader() -> None:
        try:
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type == aiohttp.WSMsgType.ERROR:
                        break
                    continue

                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    log.warning("front_panel_ws_malformed_json", user_id=user_id)
                    await ws.send_json({"type": "error", "reason": "malformed_json"})
                    continue

                cmd_type = data.get("type")
                log.debug("front_panel_ws_command", cmd=cmd_type, user_id=user_id)

                try:
                    if cmd_type == "power_press":
                        await controller.power_press()
                        await ws.send_json({"type": "ack", "cmd": "power_press"})
                    elif cmd_type == "power_hold":
                        await controller.power_hold()
                        await ws.send_json({"type": "ack", "cmd": "power_hold"})
                    elif cmd_type == "reset":
                        await controller.reset()
                        await ws.send_json({"type": "ack", "cmd": "reset"})
                    else:
                        log.warning("front_panel_ws_unknown_command", received=cmd_type, user_id=user_id)
                        await ws.send_json({"type": "error", "reason": "unknown_command", "received": cmd_type})
                except FrontPanelNotConnectedError:
                    await ws.send_json({"type": "error", "reason": "not_connected"})
                except Exception as e:
                    log.error("front_panel_ws_error", error=str(e), user_id=user_id)
                    await ws.send_json({"type": "error", "reason": "internal"})
                    break
        finally:
            if writer_task and not writer_task.done():
                writer_task.cancel()

    async def writer() -> None:
        try:
            while True:
                frame = await queue.get()
                try:
                    await asyncio.wait_for(ws.send_json(frame), timeout=1.0)
                except asyncio.TimeoutError:
                    log.warning("front_panel_ws_slow_client", ip=request.remote)
                    await ws.close()
                    return
                except Exception as e:
                    log.debug("front_panel_ws_send_error", error=str(e))
                    return
        except asyncio.CancelledError:
            pass
        finally:
            if reader_task and not reader_task.done():
                reader_task.cancel()

    try:
        reader_task = asyncio.create_task(reader())
        writer_task = asyncio.create_task(writer())
        await asyncio.gather(reader_task, writer_task, return_exceptions=True)
    finally:
        controller.unsubscribe(queue)
        log.info("front_panel_ws_disconnected", user_id=user_id, ip=request.remote)

    return ws
