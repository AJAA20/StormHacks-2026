"""WebSocket broadcast hub: pushes 'new flood data available' events to connected clients.

Frontend subscribes once and re-fetches /api/regions/{id}, /api/route etc. whenever
it receives a message for the region it's currently viewing, instead of polling.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()

_connections: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None


@router.websocket("/ws/updates")
async def updates_ws(ws: WebSocket):
    global _loop
    await ws.accept()
    _loop = asyncio.get_event_loop()
    _connections.add(ws)
    try:
        while True:
            # Keep-alive; client only listens, but recv lets us detect disconnects promptly.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)


async def _broadcast_async(message: dict) -> None:
    dead = []
    for conn in list(_connections):
        try:
            await conn.send_json(message)
        except Exception:
            dead.append(conn)
    for d in dead:
        _connections.discard(d)


def broadcast(message: dict) -> None:
    """Thread-safe broadcast entry point — safe to call from the background job thread."""
    if _loop is None:
        return  # no clients have ever connected; nothing to do
    try:
        asyncio.run_coroutine_threadsafe(_broadcast_async(message), _loop)
    except Exception:
        log.exception("failed to broadcast websocket update")
