"""Telegram Mini App: статика + API на PORT (Bothost)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
import string
import time
from typing import Any
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram import Bot
from aiogram.types import MenuButtonWebApp, WebAppInfo

from config import (
    BASE_DIR,
    BOT_TOKEN,
    CUSTOM_EMOJI,
    DB_PATH,
    MANAGER_USERNAME,
    MIN_COMPLETED_DEALS_WITHDRAW,
    SUPER_ADMIN_ID,
    SUPPORT_URL,
    WEB_PORT,
    WEBAPP_URL,
)
from database import db
from utils.admin_access import is_admin, is_super_admin
from utils.currencies import BALANCE_KEYS, BALANCE_META, PAY_REQUISITE, WITHDRAW_METHODS
from utils.panel import report_deal

log = logging.getLogger("webapp")
NFT_RE = re.compile(r"^https://t\.me/nft/[A-Za-z0-9_\-]+$", re.IGNORECASE)
WEBAPP_DIR = BASE_DIR / "static_ui"
EMOJI_DIR = DB_PATH.parent / "emoji"

_bot: Bot | None = None
_bot_username = ""


def attach_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


async def _notify(user_id: int, text: str) -> None:
    if _bot is None:
        return
    try:
        await _bot.send_message(user_id, text, parse_mode="HTML")
    except Exception:
        pass


def _hmac_matches(pairs: dict[str, str], received: str, skip: set[str]) -> bool:
    data_check = "\n".join(
        f"{k}={v}" for k, v in sorted(pairs.items()) if k not in skip
    )
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, received)


def _verify_init_data(init_data: str) -> dict[str, Any] | None:
    if not init_data or not BOT_TOKEN:
        return None
    parsed = dict(parse_qsl(init_data, keep_blank_values=True, encoding="utf-8"))
    received = (parsed.get("hash") or "").strip()
    if not received:
        return None
    if not (
        _hmac_matches(parsed, received, {"hash"})
        or _hmac_matches(parsed, received, {"hash", "signature"})
    ):
        return None
    try:
        auth_date = int(parsed.get("auth_date") or 0)
    except ValueError:
        return None
    if auth_date <= 0 or abs(time.time() - auth_date) > 86_400 * 7:
        return None
    try:
        user = json.loads(parsed.get("user") or "")
    except json.JSONDecodeError:
        return None
    if not isinstance(user, dict) or not user.get("id"):
        return None
    start_param = (parsed.get("start_param") or "").strip()
    user["_start_param"] = start_param
    return user


def _init_data(request: web.Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("tma "):
        raw = auth[4:].strip()
        if raw:
            return raw
    for header in ("X-Telegram-Init-Data", "X-Init-Data"):
        raw = request.headers.get(header, "").strip()
        if raw:
            return raw
    return (request.query.get("_auth") or "").strip()


async def _auth(request: web.Request) -> tuple[dict[str, Any] | None, web.Response | None]:
    raw = _init_data(request)
    tg_user = _verify_init_data(raw)
    if not tg_user:
        log.warning("webapp auth failed present=%s len=%s", bool(raw), len(raw or ""))
        return None, web.json_response({"ok": False, "error": "auth"}, status=401)
    uid = int(tg_user["id"])
    if await db.is_banned(uid):
        return None, web.json_response({"ok": False, "error": "banned"}, status=403)
    await db.upsert_user(
        uid,
        tg_user.get("username"),
        " ".join(
            p for p in (tg_user.get("first_name"), tg_user.get("last_name")) if p
        ).strip()
        or str(uid),
    )
    return tg_user, None


def _bal(row, key: str) -> float | int:
    col = f"balance_{key}"
    try:
        raw = row[col] if row else 0
    except (KeyError, IndexError, TypeError):
        raw = 0
    if BALANCE_META.get(key, {}).get("integer"):
        return int(raw or 0)
    return round(float(raw or 0), 8)


def _user_json(row, uid: int, start_param: str = "") -> dict[str, Any]:
    balances = {key: _bal(row, key) for key in BALANCE_KEYS}
    return {
        "id": uid,
        "username": (row["username"] if row else None) or "",
        "full_name": (row["full_name"] if row else "") or "",
        "language": (row["language"] if row else "ru") or "ru",
        "ton_wallet": (row["ton_wallet"] if row else "") or "",
        "card_number": (row["card_number"] if row else "") or "",
        "payout_username": (row["payout_username"] if row else "") or "",
        "balances": balances,
        "is_admin": False,
        "is_super_admin": is_super_admin(uid),
        "manager": MANAGER_USERNAME,
        "support_url": SUPPORT_URL,
        "bot_username": _bot_username,
        "min_withdraw_deals": MIN_COMPLETED_DEALS_WITHDRAW,
        "start_param": start_param,
    }


def _deal_code(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _deal_json(row, uid: int) -> dict[str, Any]:
    seller = int(row["seller_id"] or 0)
    buyer = int(row["buyer_id"] or 0) if row["buyer_id"] else 0
    role = "seller" if seller == uid else "buyer" if buyer == uid else ""
    return {
        "code": row["code"],
        "deal_type": row["deal_type"],
        "pay_method": row["pay_method"],
        "amount": float(row["amount"]),
        "status": row["status"],
        "description": row["description"] or "",
        "role": role,
        "seller_id": seller or None,
        "buyer_id": buyer or None,
    }


async def api_me(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    row = await db.get_user(uid)
    payload = _user_json(row, uid, tg_user.get("_start_param") or "")
    payload["is_admin"] = await is_admin(uid)
    payload["completed_deals"] = await db.count_completed_deals(uid)
    payload["referral_count"] = await db.referral_count(uid)
    return web.json_response({"ok": True, "user": payload})


async def api_language(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    body = await request.json()
    lang = "en" if str(body.get("language") or "").lower().startswith("en") else "ru"
    await db.set_language(int(tg_user["id"]), lang)
    return web.json_response({"ok": True, "language": lang})


async def api_requisites(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    body = await request.json()
    field = str(body.get("field") or "")
    value = str(body.get("value") or "").strip()
    if field == "ton":
        if len(value) < 10:
            return web.json_response({"ok": False, "error": "bad_ton"}, status=400)
        await db.set_ton_wallet(uid, value)
    elif field == "card":
        digits = "".join(c for c in value if c.isdigit())
        if not (13 <= len(digits) <= 19):
            return web.json_response({"ok": False, "error": "bad_card"}, status=400)
        await db.set_card_number(uid, digits)
    elif field == "username":
        uname = value.lstrip("@")
        if len(uname) < 3:
            return web.json_response({"ok": False, "error": "bad_username"}, status=400)
        await db.set_payout_username(uid, uname)
    else:
        return web.json_response({"ok": False, "error": "unknown_field"}, status=400)
    row = await db.get_user(uid)
    return web.json_response({"ok": True, "user": _user_json(row, uid)})


async def api_withdraw(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    body = await request.json()
    method = str(body.get("method") or "")
    if method not in WITHDRAW_METHODS:
        return web.json_response({"ok": False, "error": "method"}, status=400)
    try:
        amount = float(str(body.get("amount") or "").replace(",", "."))
    except ValueError:
        return web.json_response({"ok": False, "error": "amount"}, status=400)
    if amount <= 0:
        return web.json_response({"ok": False, "error": "amount"}, status=400)

    completed = await db.count_completed_deals(uid)
    if completed < MIN_COMPLETED_DEALS_WITHDRAW:
        return web.json_response(
            {"ok": False, "error": "need_deals", "count": completed},
            status=400,
        )

    balance_key, label, requisite = WITHDRAW_METHODS[method]
    if BALANCE_META[balance_key]["integer"] and not float(amount).is_integer():
        return web.json_response({"ok": False, "error": "integer"}, status=400)

    user = await db.get_user(uid)
    if requisite == "ton" and not (user and (user["ton_wallet"] or "").strip()):
        return web.json_response({"ok": False, "error": "need_ton"}, status=400)
    if requisite == "card" and not (user and (user["card_number"] or "").strip()):
        return web.json_response({"ok": False, "error": "need_card"}, status=400)
    if requisite == "username":
        try:
            payout = (user["payout_username"] or "").strip() if user else ""
        except (KeyError, IndexError, TypeError):
            payout = ""
        if not payout:
            return web.json_response({"ok": False, "error": "need_username"}, status=400)

    ok = await db.deduct_balance(uid, balance_key, amount)
    if not ok:
        return web.json_response({"ok": False, "error": "empty"}, status=400)

    amount_text = f"{int(amount)}" if balance_key == "stars" else f"{amount:g}"
    await _notify(
        SUPER_ADMIN_ID,
        f"💰 Заявка на вывод из Mini App\n"
        f"ID <code>{uid}</code>\n"
        f"{amount_text} {label}",
    )
    return web.json_response({"ok": True, "amount": amount_text, "currency": label})


async def api_deals_list(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    deals = [_deal_json(d, uid) for d in await db.list_user_deals(uid, limit=40)]
    return web.json_response({"ok": True, "deals": deals})


async def api_deals_create(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    body = await request.json()
    role = str(body.get("role") or "")
    deal_type = str(body.get("deal_type") or "")
    pay_method = str(body.get("pay_method") or "")
    description = str(body.get("description") or "").strip()
    if role not in {"seller", "buyer"}:
        return web.json_response({"ok": False, "error": "role"}, status=400)
    if deal_type not in {"gift", "channel", "stars", "nft"}:
        return web.json_response({"ok": False, "error": "type"}, status=400)
    if pay_method not in PAY_REQUISITE and pay_method != "stars":
        return web.json_response({"ok": False, "error": "pay"}, status=400)
    try:
        amount = float(str(body.get("amount") or "").replace(",", "."))
    except ValueError:
        return web.json_response({"ok": False, "error": "amount"}, status=400)
    if amount <= 0 or amount > 10_000_000:
        return web.json_response({"ok": False, "error": "amount"}, status=400)
    if deal_type in {"gift", "nft"}:
        if not NFT_RE.match(description):
            return web.json_response({"ok": False, "error": "nft_link"}, status=400)
    elif not description or len(description) > 500:
        return web.json_response({"ok": False, "error": "description"}, status=400)

    if role == "seller":
        user = await db.get_user(uid)
        need = PAY_REQUISITE.get(pay_method)
        if need == "ton" and not (user and user["ton_wallet"]):
            return web.json_response({"ok": False, "error": "need_ton"}, status=400)
        if need == "card" and not (user and user["card_number"]):
            return web.json_response({"ok": False, "error": "need_card"}, status=400)

    code = _deal_code()
    await db.create_deal(
        code=code,
        creator_id=uid,
        creator_role=role,
        deal_type=deal_type,
        pay_method=pay_method,
        amount=amount,
        description=description,
    )
    report_deal(code, "created", actor_id=uid)
    link = f"https://t.me/{_bot_username}?start=deal_{code}" if _bot_username else code
    deal = await db.get_deal_by_code(code)
    return web.json_response(
        {"ok": True, "deal": _deal_json(deal, uid), "link": link},
    )


async def _load_deal(code: str, uid: int):
    deal = await db.get_deal_by_code(code)
    if not deal:
        return None, web.json_response({"ok": False, "error": "not_found"}, status=404)
    return deal, None


async def api_deal_cancel(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    if not await db.cancel_deal(code, uid):
        return web.json_response({"ok": False, "error": "cannot_cancel"}, status=400)
    report_deal(code, "cancelled", actor_id=uid)
    return web.json_response({"ok": True})


async def api_deal_join(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    role = await db.join_deal(code, uid)
    if not role:
        return web.json_response({"ok": False, "error": "cannot_join"}, status=400)
    report_deal(code, "joined", actor_id=uid)
    deal = await db.get_deal_by_code(code)
    return web.json_response({"ok": True, "role": role, "deal": _deal_json(deal, uid)})


async def api_deal_paybal(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    deal, err = await _load_deal(code, uid)
    if err:
        return err
    if uid != deal["buyer_id"]:
        return web.json_response({"ok": False, "error": "not_buyer"}, status=403)
    if deal["status"] != "active":
        return web.json_response({"ok": False, "error": "status"}, status=400)
    amount = float(deal["amount"])
    if not await db.deduct_balance(uid, deal["pay_method"], amount):
        return web.json_response({"ok": False, "error": "empty"}, status=400)
    if not await db.set_deal_status(code, "paid", only_if="active"):
        return web.json_response({"ok": False, "error": "status"}, status=400)
    report_deal(code, "paid", actor_id=uid)
    await _notify(int(deal["seller_id"]), f"✅ Оплата по сделке <code>{code}</code> прошла.")
    deal = await db.get_deal_by_code(code)
    return web.json_response({"ok": True, "deal": _deal_json(deal, uid)})


async def api_deal_sent(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    deal, err = await _load_deal(code, uid)
    if err:
        return err
    if uid != deal["seller_id"]:
        return web.json_response({"ok": False, "error": "not_seller"}, status=403)
    if deal["status"] != "paid":
        return web.json_response({"ok": False, "error": "status"}, status=400)
    if not await db.set_deal_status(code, "goods_sent", only_if="paid"):
        return web.json_response({"ok": False, "error": "status"}, status=400)
    report_deal(code, "goods_sent", actor_id=uid)
    if deal["buyer_id"]:
        await _notify(
            int(deal["buyer_id"]),
            f"📦 Товар по сделке <code>{code}</code> передан гаранту @{MANAGER_USERNAME}.",
        )
    deal = await db.get_deal_by_code(code)
    return web.json_response({"ok": True, "deal": _deal_json(deal, uid)})


async def api_deal_recv(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    deal, err = await _load_deal(code, uid)
    if err:
        return err
    if uid != deal["buyer_id"]:
        return web.json_response({"ok": False, "error": "not_buyer"}, status=403)
    if deal["status"] != "goods_sent":
        return web.json_response({"ok": False, "error": "status"}, status=400)
    if not await db.set_deal_status(code, "completed", only_if="goods_sent"):
        return web.json_response({"ok": False, "error": "status"}, status=400)
    from utils.currencies import PAY_TO_BALANCE

    credit = PAY_TO_BALANCE.get(deal["pay_method"], "rub")
    await db.add_balance(int(deal["seller_id"]), credit, float(deal["amount"]))
    report_deal(code, "completed", actor_id=uid)
    await _notify(int(deal["seller_id"]), f"✅ Сделка <code>{code}</code> завершена.")
    deal = await db.get_deal_by_code(code)
    return web.json_response({"ok": True, "deal": _deal_json(deal, uid)})


async def api_admin_credit(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    if not await is_admin(int(tg_user["id"])):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    body = await request.json()
    currency = str(body.get("currency") or "")
    if currency not in BALANCE_KEYS:
        return web.json_response({"ok": False, "error": "currency"}, status=400)
    try:
        target = int(body.get("user_id") or tg_user["id"])
        amount = float(str(body.get("amount")).replace(",", "."))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "input"}, status=400)
    if amount == 0:
        return web.json_response({"ok": False, "error": "amount"}, status=400)
    credit = int(amount) if BALANCE_META[currency]["integer"] else amount
    await db.add_balance(target, currency, credit)
    return web.json_response({"ok": True})


async def api_admin_transfer(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    if not await is_admin(int(tg_user["id"])):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    body = await request.json()
    currency = str(body.get("currency") or "")
    if currency not in BALANCE_KEYS:
        return web.json_response({"ok": False, "error": "currency"}, status=400)
    try:
        target = int(body.get("user_id"))
        amount = float(str(body.get("amount")).replace(",", "."))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "input"}, status=400)
    if amount <= 0:
        return web.json_response({"ok": False, "error": "amount"}, status=400)
    credit = int(amount) if BALANCE_META[currency]["integer"] else amount
    await db.add_balance(target, currency, credit)
    label = BALANCE_META[currency]["label"]
    await _notify(
        target,
        f"⭐ Менеджер @{MANAGER_USERNAME} перевёл на баланс "
        f"<b>{credit:g} {label}</b>.",
    )
    return web.json_response({"ok": True})


async def api_admin_grant(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    if not is_super_admin(int(tg_user["id"])):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    body = await request.json()
    try:
        new_id = int(body.get("user_id"))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "input"}, status=400)
    if is_super_admin(new_id):
        return web.json_response({"ok": False, "error": "owner"}, status=400)
    added = await db.add_admin(new_id)
    workers = await db.list_admins()
    return web.json_response({"ok": True, "added": added, "workers": workers})


async def api_admin_ban(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    if not is_super_admin(int(tg_user["id"])):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    body = await request.json()
    action = str(body.get("action") or "ban")
    try:
        target = int(body.get("user_id"))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "input"}, status=400)
    if is_super_admin(target):
        return web.json_response({"ok": False, "error": "owner"}, status=400)
    if action == "unban":
        await db.unban_user(target)
    else:
        await db.ban_user(target)
    return web.json_response({"ok": True})


async def api_admin_workers(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    if not is_super_admin(int(tg_user["id"])):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    return web.json_response({"ok": True, "workers": await db.list_admins()})


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "ggsel-miniapp"})


async def _warmup_emoji(bot: Bot) -> None:
    EMOJI_DIR.mkdir(parents=True, exist_ok=True)
    id_to_keys: dict[str, list[str]] = {}
    for key, emoji_id in CUSTOM_EMOJI.items():
        eid = (emoji_id or "").strip()
        if not eid:
            continue
        id_to_keys.setdefault(eid, []).append(key)
    ids = list(id_to_keys)
    if not ids:
        return
    try:
        stickers = await bot.get_custom_emoji_stickers(ids)
    except Exception as exc:
        log.warning("custom emoji fetch failed: %s", exc)
        return
    for sticker in stickers:
        eid = sticker.custom_emoji_id
        dest = EMOJI_DIR / f"{eid}.webp"
        if not dest.is_file():
            try:
                await bot.download(sticker.thumbnail or sticker, destination=dest)
            except Exception as exc:
                log.warning("emoji download %s: %s", eid, exc)
                continue
        if not dest.is_file():
            continue
        data = dest.read_bytes()
        for key in id_to_keys.get(eid, []):
            alias = EMOJI_DIR / f"{key}.webp"
            if not alias.is_file() or alias.stat().st_size != dest.stat().st_size:
                alias.write_bytes(data)
    log.info("Mini App emoji cache: %s files", len(list(EMOJI_DIR.glob("*.webp"))))


async def serve_emoji(request: web.Request) -> web.StreamResponse:
    key = request.match_info["key"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", key):
        raise web.HTTPNotFound()
    path = EMOJI_DIR / f"{key}.webp"
    if not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(
        path,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/language", api_language)
    app.router.add_post("/api/requisites", api_requisites)
    app.router.add_post("/api/withdraw", api_withdraw)
    app.router.add_get("/api/deals", api_deals_list)
    app.router.add_post("/api/deals", api_deals_create)
    app.router.add_post("/api/deals/{code}/cancel", api_deal_cancel)
    app.router.add_post("/api/deals/{code}/join", api_deal_join)
    app.router.add_post("/api/deals/{code}/paybal", api_deal_paybal)
    app.router.add_post("/api/deals/{code}/sent", api_deal_sent)
    app.router.add_post("/api/deals/{code}/recv", api_deal_recv)
    app.router.add_post("/api/admin/credit", api_admin_credit)
    app.router.add_post("/api/admin/transfer", api_admin_transfer)
    app.router.add_post("/api/admin/grant", api_admin_grant)
    app.router.add_post("/api/admin/ban", api_admin_ban)
    app.router.add_get("/api/admin/workers", api_admin_workers)
    app.router.add_get("/e/{key}.webp", serve_emoji)
    app.router.add_static("/assets", path=str(WEBAPP_DIR), name="webapp_static")
    app.router.add_get("/", index)
    return app


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(
        WEBAPP_DIR / "index.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


async def start_http() -> web.AppRunner:
    runner = web.AppRunner(build_app(), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", WEB_PORT).start()
    log.info("Mini App слушает 0.0.0.0:%s", WEB_PORT)
    return runner


async def bind_bot_menu(bot: Bot) -> None:
    global _bot_username
    attach_bot(bot)
    me = await bot.get_me()
    _bot_username = me.username or ""
    asyncio.create_task(_warmup_emoji(bot))
    url = WEBAPP_URL
    if not url:
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="GGSel",
                web_app=WebAppInfo(url=url),
            )
        )
        log.info("Кнопка меню Mini App: %s", url)
    except Exception as exc:
        log.warning("Не удалось поставить menu button: %s", exc)


async def start_webapp(bot: Bot) -> web.AppRunner:
    runner = await start_http()
    await bind_bot_menu(bot)
    return runner
