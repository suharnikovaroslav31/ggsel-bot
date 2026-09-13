"""Отправка событий сделок в панель Ural Team.

Панель принимает POST {PANEL_API_URL}/api/deals с заголовком X-Api-Secret.
Отправка идёт фоном с повторами: если панель недоступна, сделка в этом боте
всё равно проходит нормально.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from config import PANEL_API_SECRET, PANEL_API_URL
from database import db

log = logging.getLogger("panel")

_TIMEOUT = aiohttp.ClientTimeout(total=10)
_RETRIES = 3
# Такие ответы означают ошибку в данных или секрете — повтор не поможет.
_FATAL_STATUSES = {400, 401, 403, 404, 422}

# Событие → этап сделки. Берём его из названия события, а не из БД: пока
# событие ждёт отправки, сделка уже может уйти на следующий шаг.
EVENT_STAGES = {
    "created": "open",
    "joined": "active",
    "paid": "paid",
    "goods_sent": "goods_sent",
    "completed": "completed",
    "cancelled": "cancelled",
}

_queue: asyncio.Queue | None = None
_worker: asyncio.Task | None = None


def _endpoint() -> str:
    base = PANEL_API_URL.rstrip("/")
    if not base:
        return ""
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return base if base.endswith("/api/deals") else f"{base}/api/deals"


def enabled() -> bool:
    return bool(_endpoint() and PANEL_API_SECRET)


async def _person(user_id: int | None) -> dict:
    if not user_id:
        return {}
    row = await db.get_user(int(user_id))
    return {
        "id": int(user_id),
        "username": (row["username"] if row else "") or "",
        "name": (row["full_name"] if row else "") or "",
    }


async def _payload(code: str, event: str, actor_id: int | None) -> dict | None:
    deal = await db.get_deal_by_code(code)
    if not deal:
        return None
    try:
        description = deal["description"] or ""
    except (KeyError, IndexError, TypeError):
        description = ""
    return {
        "source": "gg_sel",
        "event": event,
        "id": deal["code"],
        "status": EVENT_STAGES.get(event, deal["status"]),
        "db_status": deal["status"],
        "deal_type": deal["deal_type"],
        "pay_method": deal["pay_method"],
        "amount": float(deal["amount"] or 0),
        "description": description,
        "seller": await _person(int(deal["seller_id"] or 0) or None),
        "buyer": await _person(int(deal["buyer_id"] or 0) or None),
        "actor_id": actor_id,
        "created_at": str(deal["created_at"] or ""),
    }


async def _send(payload: dict) -> None:
    url = _endpoint()
    headers = {"X-Api-Secret": PANEL_API_SECRET}
    code = payload.get("id")
    delay = 2
    for attempt in range(1, _RETRIES + 1):
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status < 400:
                        return
                    body = (await resp.text())[:200]
                    if resp.status in _FATAL_STATUSES:
                        log.warning("Панель отклонила сделку %s: %s %s", code, resp.status, body)
                        return
                    log.warning("Панель ответила %s на сделку %s: %s", resp.status, code, body)
        except Exception as exc:
            log.warning("Панель недоступна (%s/%s) по сделке %s: %s", attempt, _RETRIES, code, exc)
        if attempt < _RETRIES:
            await asyncio.sleep(delay)
            delay *= 2


async def _pump(queue: asyncio.Queue) -> None:
    """Отправляем события по одному, чтобы панель видела их в нужном порядке."""
    while True:
        code, event, actor_id = await queue.get()
        try:
            payload = await _payload(code, event, actor_id)
            if payload:
                await _send(payload)
        except Exception:
            log.exception("Не смог отправить сделку %s в панель", code)
        finally:
            queue.task_done()


def report_deal(code: str, event: str, *, actor_id: int | None = None) -> None:
    """Поставить событие сделки в очередь на отправку в панель."""
    if not code or not enabled():
        return
    global _queue, _worker
    if _queue is None:
        _queue = asyncio.Queue(maxsize=1000)
    if _worker is None or _worker.done():
        _worker = asyncio.create_task(_pump(_queue))
    try:
        _queue.put_nowait((code, event, actor_id))
    except asyncio.QueueFull:
        log.warning("Очередь панели переполнена, событие %s по сделке %s потеряно", event, code)
