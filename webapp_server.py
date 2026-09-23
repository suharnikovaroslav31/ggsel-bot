"""Telegram Mini App: статика + API на PORT (Bothost)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import random
import re
import secrets
import string
import time
from typing import Any
from urllib.parse import parse_qsl, unquote, unquote_plus

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
NFT_LINK_RE = re.compile(
    r"https?://(?:t|telegram)\.me/nft/([A-Za-z0-9_\-]+)/?",
    re.IGNORECASE,
)
NFT_RE = re.compile(
    r"^https?://(?:t|telegram)\.me/nft/[A-Za-z0-9_\-]+/?$",
    re.IGNORECASE,
)
WEBAPP_DIR = BASE_DIR / "static_ui"
EMOJI_DIR = DB_PATH.parent / "emoji"
NFT_IMG_DIR = DB_PATH.parent / "nft_img"

# Живая витрина: ротация раз в 2 минуты (плюс реальные лоты продавцов)
# Floors ≈ Fragment snapshot (TON), источник giftswatchdata / fragment
_MARKET_ROTATE_SEC = 120
_SHOWCASE_FLOOR_TON: dict[str, float] = {
    "PlushPepe": 3999.0,
    "DurovsCap": 435.0,
    "LolPop": 5.0,
    "PreciousPeach": 322.0,
    "PerfumeBottle": 80.0,
    "ToyBear": 40.0,
    "SwissWatch": 59.0,
    "DiamondRing": 35.0,
    "SignetRing": 35.0,
    "ScaredCat": 297.0,
    "MagicPotion": 73.0,
    "GenieLamp": 40.0,
    "EternalRose": 29.0,
    "LootBag": 138.0,
    "NekoHelmet": 40.0,
    "ElectricSkull": 35.0,
    "SpyAgaric": 7.0,
    "VintageCigar": 47.0,
    "MiniOscar": 83.0,
    "AstralShard": 148.0,
}
_SHOWCASE_NFTS = (
    "PlushPepe-128",
    "DurovsCap-7",
    "LolPop-4421",
    "PreciousPeach-88",
    "PerfumeBottle-203",
    "ToyBear-915",
    "SwissWatch-44",
    "DiamondRing-301",
    "SignetRing-77",
    "ScaredCat-1204",
    "MagicPotion-56",
    "GenieLamp-19",
    "EternalRose-333",
    "LootBag-812",
    "NekoHelmet-45",
    "ElectricSkull-67",
    "SpyAgaric-902",
    "VintageCigar-14",
    "MiniOscar-3",
    "AstralShard-221",
)
_SHOWCASE_SELLERS = (
    "tonfox",
    "nftlane",
    "giftok",
    "dealwave",
    "starpay",
    "rarebrod",
    "rubnode",
    "p2psafe",
    "pepe_hub",
    "cap_trade",
)


def _collection_key(slug: str) -> str:
    bits = str(slug or "").split("-")
    return bits[0] if bits else slug


def _realistic_ton_price(slug: str, rng: random.Random) -> float:
    """Цена около floor Fragment: floor…floor+~12%, иногда чуть ниже."""
    floor = float(_SHOWCASE_FLOOR_TON.get(_collection_key(slug), 25.0))
    # Листинги обычно floor…+8–15%; иногда -2% «быстрая продажа»
    mult = 0.98 + rng.random() * 0.14
    price = floor * mult
    if price >= 100:
        return float(int(round(price)))
    if price >= 10:
        return round(price, 1)
    return round(price, 2)


def _market_seed() -> int:
    return int(time.time()) // _MARKET_ROTATE_SEC


def _market_rotate_in() -> int:
    return max(1, _MARKET_ROTATE_SEC - int(time.time()) % _MARKET_ROTATE_SEC)


def _showcase_market_items(limit: int = 10) -> list[dict[str, Any]]:
    """Детерминированная витрина на окно 2 мин — цены как на Fragment (TON)."""
    seed = _market_seed()
    rng = random.Random(seed)
    nfts = list(_SHOWCASE_NFTS)
    rng.shuffle(nfts)
    sellers = list(_SHOWCASE_SELLERS)
    rng.shuffle(sellers)
    items: list[dict[str, Any]] = []
    for i, slug in enumerate(nfts[:limit]):
        meta = _parse_nft_meta(f"https://t.me/nft/{slug}")
        if not meta:
            continue
        seller = sellers[i % len(sellers)]
        amount = _realistic_ton_price(slug, rng)
        items.append(
            {
                "code": f"v{seed}_{i}",
                "amount": amount,
                "pay_method": "ton",
                "deal_type": "gift",
                "status": "open",
                "listing": "sell",
                "nft": meta,
                "seller": seller,
                "seller_id": None,
                "owner_id": None,
                "demo": True,
            }
        )
    return items


_bot: Bot | None = None
_bot_username = ""


def attach_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


async def _notify(user_id: int, text: str, markup=None) -> None:
    if _bot is None or not user_id:
        return
    try:
        await _bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        pass


def _hmac_matches(pairs: dict[str, str], received: str, skip: set[str]) -> bool:
    data_check = "\n".join(
        f"{k}={v}" for k, v in sorted(pairs.items()) if k not in skip
    )
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, received)


def _pair_variants(init_data: str) -> list[dict[str, str]]:
    blobs = [init_data]
    for decoder in (unquote, unquote_plus):
        try:
            decoded = decoder(init_data)
        except Exception:
            continue
        if decoded and decoded not in blobs:
            blobs.append(decoded)
    variants: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for raw in blobs:
        parsed_list = [dict(parse_qsl(raw, keep_blank_values=True, encoding="utf-8"))]
        manual: dict[str, str] = {}
        for part in raw.split("&"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            manual[key] = value
        if manual:
            parsed_list.append(manual)
            parsed_list.append({k: unquote(v) for k, v in manual.items()})
        for parsed in parsed_list:
            if not parsed:
                continue
            key = tuple(sorted(parsed.items()))
            if key in seen:
                continue
            seen.add(key)
            variants.append(parsed)
    return variants


def _verify_init_data(init_data: str) -> dict[str, Any] | None:
    if not init_data or not BOT_TOKEN:
        return None
    for parsed in _pair_variants(init_data):
        received = (parsed.get("hash") or "").strip()
        if not received:
            continue
        if not (
            _hmac_matches(parsed, received, {"hash"})
            or _hmac_matches(parsed, received, {"hash", "signature"})
        ):
            continue
        try:
            user = json.loads(parsed.get("user") or "")
        except json.JSONDecodeError:
            continue
        if not isinstance(user, dict) or not user.get("id"):
            continue
        start_param = (parsed.get("start_param") or "").strip()
        user["_start_param"] = start_param
        return user
    return None


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
    if not is_super_admin(uid) and await db.is_banned(uid):
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
    picked = 0
    if row is not None:
        try:
            picked = int(row["lang_picked"] or 0)
        except (KeyError, IndexError, TypeError):
            picked = 0
    return {
        "id": uid,
        "username": (row["username"] if row else None) or "",
        "full_name": (row["full_name"] if row else "") or "",
        "language": (row["language"] if row else "ru") or "ru",
        "lang_picked": picked,
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
    code = row["code"]
    link = f"https://t.me/{_bot_username}?start=deal_{code}" if _bot_username else ""
    return {
        "code": code,
        "deal_type": row["deal_type"],
        "pay_method": row["pay_method"],
        "amount": float(row["amount"]),
        "status": row["status"],
        "description": row["description"] or "",
        "role": role,
        "seller_id": seller or None,
        "buyer_id": buyer or None,
        "link": link,
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
    uname = (row["username"] if row else "") or ""
    avg, cnt = await db.user_rating(uid, uname)
    payload["rating"] = avg
    payload["rating_count"] = cnt
    return web.json_response({"ok": True, "user": payload})


_LANG_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})?$", re.I)


def _normalize_locale(raw: str) -> str:
    lang = str(raw or "en").strip().lower().replace("_", "-")
    if not _LANG_RE.fullmatch(lang):
        return "en"
    return lang


async def api_language(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    body = await request.json()
    lang = _normalize_locale(str(body.get("language") or "en"))
    uid = int(tg_user["id"])
    await db.set_language(uid, lang)
    # Не ждём Telegram: иначе Mini App зависает на выборе языка / старте.
    asyncio.create_task(_refresh_start_button(uid, str(body.get("deal") or "").strip()))
    return web.json_response({"ok": True, "language": lang})


async def _refresh_start_button(uid: int, deal: str = "") -> None:
    if _bot is None:
        return
    try:
        msg_id = await db.get_last_welcome_msg_id(uid)
        if not msg_id:
            return
        from keyboards.main import open_app_kb
        from utils.app_gate import APP_READY
        from utils.media import edit_message_ui

        query = f"deal={deal}" if deal else ""
        await asyncio.wait_for(
            edit_message_ui(_bot, uid, msg_id, APP_READY, open_app_kb(query)),
            timeout=8,
        )
    except Exception:
        pass


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
    return web.json_response({"ok": True, "deals": deals}, headers={"Cache-Control": "no-store"})


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
    raw_amount = str(body.get("amount") or "").strip().replace(",", ".").replace(" ", "")
    raw_amount = re.sub(r"[^\d.\-]", "", raw_amount)
    try:
        amount = float(raw_amount)
    except ValueError:
        return web.json_response({"ok": False, "error": "amount"}, status=400)
    if amount <= 0 or amount > 10_000_000:
        return web.json_response({"ok": False, "error": "amount"}, status=400)
    if deal_type in {"gift", "nft"}:
        normalized = _normalize_nft_description(description)
        if not normalized:
            return web.json_response({"ok": False, "error": "nft_link"}, status=400)
        description = normalized
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
    link = f"https://t.me/{_bot_username}?start=deal_{code}" if _bot_username else ""
    deal = await db.get_deal_by_code(code)
    payload = _deal_json(deal, uid)
    if not payload.get("link"):
        payload["link"] = link
    return web.json_response(
        {"ok": True, "deal": payload, "link": payload["link"] or f"deal_{code}"},
    )


async def _load_deal(code: str, uid: int):
    deal = await db.get_deal_by_code(code)
    if not deal:
        return None, web.json_response({"ok": False, "error": "not_found"}, status=404)
    return deal, None


async def api_deal_get(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    deal, err_resp = await _load_deal(code, uid)
    if err_resp:
        return err_resp
    payload = _deal_json(deal, uid)
    if not payload["role"] and deal["status"] not in {"open"}:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    return web.json_response({"ok": True, "deal": payload}, headers={"Cache-Control": "no-store"})


async def api_deal_cancel(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    if not await db.cancel_deal(code, uid):
        return web.json_response({"ok": False, "error": "cannot_cancel"}, status=400)
    report_deal(code, "cancelled", actor_id=uid)
    deal = await db.get_deal_by_code(code)
    return web.json_response({"ok": True, "deal": _deal_json(deal, uid) if deal else None})


async def api_deal_join(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    uid = int(tg_user["id"])
    code = request.match_info["code"]
    deal = await db.get_deal_by_code(code)
    if not deal:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    seller = int(deal["seller_id"] or 0)
    buyer = int(deal["buyer_id"] or 0) if deal["buyer_id"] else 0
    if uid in {seller, buyer} and uid:
        return web.json_response(
            {"ok": True, "joined": False, "role": _deal_json(deal, uid)["role"], "deal": _deal_json(deal, uid)}
        )
    if deal["status"] != "open":
        return web.json_response({"ok": False, "error": "cannot_join"}, status=400)
    role = await db.join_deal(code, uid)
    if not role:
        return web.json_response({"ok": False, "error": "cannot_join"}, status=400)
    report_deal(code, "joined", actor_id=uid)
    deal = await db.get_deal_by_code(code)
    await _notify_join(deal, code, uid)
    return web.json_response(
        {"ok": True, "joined": True, "role": role, "deal": _deal_json(deal, uid)}
    )


async def _notify_join(deal, code: str, uid: int) -> None:
    from keyboards.main import open_app_kb
    from texts.deal_messages import buyer_seller_joined_text, seller_deal_connected_text

    if not deal:
        return
    seller_id = int(deal["seller_id"] or 0)
    buyer_id = int(deal["buyer_id"] or 0) if deal["buyer_id"] else 0
    if not seller_id or not buyer_id:
        return
    other = buyer_id if uid == seller_id else seller_id
    kb = open_app_kb(f"deal={code}")
    buyer_user = await db.get_user(buyer_id)
    seller_user = await db.get_user(seller_id)
    if other == seller_id:
        text = seller_deal_connected_text(
            code=code,
            buyer_username=buyer_user["username"] if buyer_user else None,
            buyer_id=buyer_id,
            buyer_deals=await db.count_user_deals(buyer_id),
            description=deal["description"] or "",
            pay_method=deal["pay_method"],
            amount=float(deal["amount"]),
        )
    else:
        text = buyer_seller_joined_text(
            code=code,
            seller_username=seller_user["username"] if seller_user else None,
            seller_id=seller_id,
            seller_completed_deals=await db.count_completed_deals(seller_id),
        )
    await _notify(other, text, kb)


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
    from keyboards.main import open_app_kb

    await _notify(
        int(deal["seller_id"]),
        f"✅ Оплата по сделке <code>{code}</code> прошла.",
        open_app_kb(f"deal={code}"),
    )
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
        from keyboards.main import open_app_kb

        await _notify(
            int(deal["buyer_id"]),
            f"📦 Товар по сделке <code>{code}</code> передан гаранту @{MANAGER_USERNAME}.",
            open_app_kb(f"deal={code}"),
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
    from keyboards.main import open_app_kb

    await _notify(
        int(deal["seller_id"]),
        f"✅ Сделка <code>{code}</code> завершена.",
        open_app_kb(f"deal={code}"),
    )
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


def _review_json(row) -> dict[str, Any]:
    def _col(name: str, default: str = "") -> str:
        try:
            return str(row[name] or default)
        except (KeyError, IndexError, TypeError):
            return default

    def _int(name: str) -> int | None:
        try:
            v = row[name]
        except (KeyError, IndexError, TypeError):
            return None
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    amount = 0.0
    try:
        amount = float(row["amount"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        amount = 0.0

    return {
        "id": int(row["id"]),
        "username": row["username"] or "",
        "rating": int(row["rating"] or 5),
        "body": row["body"] or "",
        "date": row["review_date"] or "",
        "sort_order": int(row["sort_order"] or 0),
        "nft_url": _col("nft_url"),
        "deal_code": _col("deal_code"),
        "seller_username": _col("seller_username"),
        "buyer_username": _col("buyer_username"),
        "seller_id": _int("seller_id"),
        "buyer_id": _int("buyer_id"),
        "author_role": _col("author_role", "buyer") or "buyer",
        "amount": amount,
        "pay_method": _col("pay_method"),
        "deal_type": _col("deal_type", "gift") or "gift",
    }


def _extract_nft_slug(raw: str) -> str | None:
    m = NFT_LINK_RE.search(str(raw or "").strip())
    return m.group(1) if m else None


def _parse_nft_meta(raw: str) -> dict[str, str] | None:
    slug = _extract_nft_slug(raw)
    if not slug:
        return None
    bits = slug.split("-")
    num = bits.pop() if len(bits) > 1 else ""
    name = " ".join(bits) or slug
    low = slug.lower()
    hue = sum(ord(c) for c in low) % 360
    # Proxied first — Telegram WebView иногда режет hotlink с fragment.com
    return {
        "url": f"https://t.me/nft/{slug}",
        "slug": slug,
        "name": name,
        "num": num,
        "img": f"/n/{low}.jpg",
        "img_alt": f"https://nft.fragment.com/gift/{low}.medium.jpg",
        "img_fallbacks": [
            f"https://nft.fragment.com/gift/{low}.medium.jpg",
            f"https://nft.fragment.com/gift/{low}.webp",
            f"https://nft.fragment.com/gift/{slug}.medium.jpg",
            f"https://nft.fragment.com/gift/{low}.large.jpg",
        ],
        "color": f"hsl({hue} 42% 38%)",
    }


def _normalize_nft_description(raw: str) -> str | None:
    meta = _parse_nft_meta(raw)
    return meta["url"] if meta else None



async def api_reviews_list(request: web.Request) -> web.Response:
    newest = str(request.query.get("sort") or "new").lower() != "old"
    rows = await db.list_reviews(newest_first=newest)
    return web.json_response(
        {"ok": True, "reviews": [_review_json(r) for r in rows]},
        headers={"Cache-Control": "no-store"},
    )


async def api_feed(request: web.Request) -> web.Response:
    rows = await db.list_feed_reviews(limit=24)
    items = []
    for r in rows:
        nft = _parse_nft_meta(r["nft_url"] or "")
        if not nft:
            continue
        deal = None
        code = (r["deal_code"] or "").strip()
        if code:
            deal = await db.get_deal_by_code(code)
        items.append(
            {
                "id": int(r["id"]),
                "username": r["username"] or "",
                "body": r["body"] or "",
                "date": r["review_date"] or "",
                "rating": int(r["rating"] or 5),
                "nft": nft,
                "deal_code": code,
                "deal": (
                    {
                        "code": deal["code"],
                        "deal_type": deal["deal_type"],
                        "pay_method": deal["pay_method"],
                        "amount": float(deal["amount"]),
                        "status": deal["status"],
                        "description": deal["description"] or "",
                    }
                    if deal
                    else None
                ),
            }
        )
    return web.json_response({"ok": True, "items": items}, headers={"Cache-Control": "no-store"})


async def api_feed_item(request: web.Request) -> web.Response:
    try:
        rid = int(request.match_info["rid"])
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "input"}, status=400)
    row = await db.get_review(rid)
    if not row:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    nft = _parse_nft_meta(row["nft_url"] or "")
    code = (row["deal_code"] or "").strip()
    deal = await db.get_deal_by_code(code) if code else None
    seller = await db.get_user(int(deal["seller_id"])) if deal and deal["seller_id"] else None
    buyer = await db.get_user(int(deal["buyer_id"])) if deal and deal["buyer_id"] else None
    rev = _review_json(row)
    seller_name = (
        (seller["username"] if seller and seller["username"] else None)
        or rev.get("seller_username")
        or None
    )
    buyer_name = (
        (buyer["username"] if buyer and buyer["username"] else None)
        or rev.get("buyer_username")
        or None
    )
    return web.json_response(
        {
            "ok": True,
            "item": {
                **rev,
                "nft": nft,
                "deal": (
                    {
                        "code": deal["code"],
                        "deal_type": deal["deal_type"],
                        "pay_method": deal["pay_method"],
                        "amount": float(deal["amount"]),
                        "status": deal["status"],
                        "description": deal["description"] or "",
                        "seller": seller_name,
                        "buyer": buyer_name,
                    }
                    if deal
                    else None
                ),
            },
        },
        headers={"Cache-Control": "no-store"},
    )


async def api_market(request: web.Request) -> web.Response:
    items: list[dict[str, Any]] = []
    seen_nft: set[str] = set()
    try:
        rows = await db.list_market_nfts(limit=40)
    except Exception as exc:
        log.exception("market list failed: %s", exc)
        rows = []

    for r in rows:
        nft = _parse_nft_meta(r["description"] or "")
        if not nft:
            continue
        slug = (nft.get("slug") or "").lower()
        if slug:
            seen_nft.add(slug)
        seller_id = int(r["seller_id"] or 0)
        buyer_id = int(r["buyer_id"] or 0) if r["buyer_id"] else 0
        listing = "sell" if seller_id else "buy"
        owner_id = seller_id or buyer_id
        owner = await db.get_user(owner_id) if owner_id else None
        items.append(
            {
                "code": r["code"],
                "amount": float(r["amount"]),
                "pay_method": r["pay_method"],
                "deal_type": r["deal_type"],
                "status": r["status"],
                "listing": listing,
                "nft": nft,
                "seller": (owner["username"] if owner and owner["username"] else None),
                "seller_id": owner_id or None,
                "owner_id": owner_id or None,
                "demo": False,
            }
        )

    # Добиваем витрину «живыми» лотами — ротация каждые 2 минуты
    for demo in _showcase_market_items(12):
        slug = ((demo.get("nft") or {}).get("slug") or "").lower()
        if slug and slug in seen_nft:
            continue
        if slug:
            seen_nft.add(slug)
        items.append(demo)
        if len(items) >= 16:
            break

    return web.json_response(
        {
            "ok": True,
            "items": items,
            "seed": _market_seed(),
            "rotate_in": _market_rotate_in(),
        },
        headers={"Cache-Control": "no-store"},
    )


async def api_admin_review_add(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    admin_uid = int(tg_user["id"])
    if not await is_admin(admin_uid):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    body = await request.json()
    author = str(body.get("username") or body.get("author") or "").strip().lstrip("@")
    seller_u = str(body.get("seller") or body.get("seller_username") or "").strip().lstrip("@")
    buyer_u = str(body.get("buyer") or body.get("buyer_username") or "").strip().lstrip("@")
    text = str(body.get("body") or body.get("text") or "").strip()
    date = str(body.get("date") or "").strip()
    nft_url = str(body.get("nft_url") or body.get("nft") or "").strip()
    deal_code = str(body.get("deal_code") or body.get("deal") or "").strip()
    pay_method = str(body.get("pay_method") or body.get("pay") or "stars").strip().lower()
    deal_type = str(body.get("deal_type") or body.get("type") or "gift").strip().lower()
    author_role = str(body.get("author_role") or body.get("role") or "buyer").strip().lower()
    if author_role not in {"buyer", "seller"}:
        author_role = "buyer"
    if deal_type not in {"gift", "channel", "stars", "nft"}:
        deal_type = "gift"
    if pay_method not in PAY_REQUISITE and pay_method != "stars":
        pay_method = "stars"
    try:
        rating = int(body.get("rating") or 5)
    except (TypeError, ValueError):
        rating = 5
    try:
        amount = float(str(body.get("amount") or "0").replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        amount = 0.0
    if amount < 0:
        amount = 0.0

    admin_user = await db.get_user(admin_uid)
    admin_uname = (
        (admin_user["username"] if admin_user else None) or tg_user.get("username") or ""
    ).lstrip("@")
    me_aliases = {"me", "я", "self"}
    if admin_uname:
        me_aliases.add(admin_uname.lower())
    me_aliases.add(str(admin_uid))

    def _is_me(name: str) -> bool:
        n = str(name or "").strip().lstrip("@").lower()
        return bool(n) and n in me_aliases

    await db.ensure_user(admin_uid)
    if _is_me(author) or not author:
        author = admin_uname or str(admin_uid)
        author_id = admin_uid
        if admin_uname:
            row = await db.get_user(admin_uid)
            if row and not (row["username"] or "").strip():
                await db.conn.execute(
                    "UPDATE users SET username = ? WHERE user_id = ?",
                    (admin_uname, admin_uid),
                )
                await db.conn.commit()
    else:
        author_id = await db.ensure_named_user(author)

    if author_role == "buyer":
        buyer_u = buyer_u or author
        if not seller_u:
            return web.json_response({"ok": False, "error": "seller"}, status=400)
    else:
        seller_u = seller_u or author
        if not buyer_u:
            return web.json_response({"ok": False, "error": "buyer"}, status=400)

    if not author or not text:
        return web.json_response({"ok": False, "error": "input"}, status=400)
    if nft_url and not _parse_nft_meta(nft_url):
        return web.json_response({"ok": False, "error": "nft_link"}, status=400)

    async def _party(name: str, *, prefer_author: bool = False) -> tuple[str, int]:
        n = str(name or "").strip().lstrip("@")
        if _is_me(n):
            return admin_uname or n, admin_uid
        if prefer_author and n.lower() == author.lower():
            return author, author_id
        return n, await db.ensure_named_user(n)

    if author_role == "buyer":
        buyer_u, buyer_id = await _party(buyer_u, prefer_author=True)
        seller_u, seller_id = await _party(seller_u)
    else:
        seller_u, seller_id = await _party(seller_u, prefer_author=True)
        buyer_u, buyer_id = await _party(buyer_u)

    if deal_code:
        deal = await db.get_deal_by_code(deal_code)
        if not deal:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        if not nft_url:
            nft_url = deal["description"] or ""
        if not amount:
            amount = float(deal["amount"] or 0)
        pay_method = deal["pay_method"] or pay_method
        deal_type = deal["deal_type"] or deal_type
    else:
        if seller_id == buyer_id:
            return web.json_response({"ok": False, "error": "same_party"}, status=400)
        deal_code = _deal_code()
        desc = nft_url or f"review:{author}"
        await db.create_completed_deal(
            code=deal_code,
            seller_id=seller_id,
            buyer_id=buyer_id,
            deal_type=deal_type,
            pay_method=pay_method,
            amount=amount or 1.0,
            description=desc,
        )
        report_deal(deal_code, "completed", actor_id=admin_uid)

    row = await db.add_review(
        author,
        rating,
        text,
        date,
        nft_url=nft_url,
        deal_code=deal_code,
        seller_username=seller_u,
        buyer_username=buyer_u,
        seller_id=seller_id,
        buyer_id=buyer_id,
        author_role=author_role,
        amount=amount or 1.0,
        pay_method=pay_method,
        deal_type=deal_type,
    )
    return web.json_response(
        {"ok": True, "review": _review_json(row) if row else None, "deal_code": deal_code}
    )


async def api_public_profile(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    key = str(request.match_info.get("key") or "").strip().lstrip("@")
    if not key:
        return web.json_response({"ok": False, "error": "input"}, status=400)

    viewer = int(tg_user["id"])
    user = None
    uid: int | None = None
    if key.lstrip("-").isdigit():
        uid = int(key)
        user = await db.get_user(uid)
    if not user:
        user = await db.find_user_by_username(key)
        if user:
            uid = int(user["user_id"])

    if user and uid is not None:
        uname = (user["username"] or "").lstrip("@")
        full_name = user["full_name"] or uname or str(uid)
    else:
        # Ник есть в отзывах, но аккаунта ещё нет — показываем витрину по нику
        uname = key
        full_name = key
        uid = 0
        avg, cnt = await db.user_rating(0, uname)
        reviews = [_review_json(r) for r in await db.list_user_reviews(0, uname, limit=40)]
        return web.json_response(
            {
                "ok": True,
                "profile": {
                    "user_id": None,
                    "username": uname,
                    "full_name": full_name,
                    "rating": avg,
                    "rating_count": cnt,
                    "completed_deals": 0,
                    "is_self": False,
                    "deals": [],
                    "reviews": reviews,
                },
            },
            headers={"Cache-Control": "no-store"},
        )

    avg, cnt = await db.user_rating(uid, uname)
    completed = await db.count_completed_deals(uid)
    deals_raw = await db.list_user_completed_deals(uid, limit=30)
    out_deals = []
    for raw in deals_raw:
        d = _deal_json(raw, viewer)
        sid = int(raw["seller_id"] or 0)
        bid = int(raw["buyer_id"] or 0) if raw["buyer_id"] else 0
        su = await db.get_user(sid) if sid else None
        bu = await db.get_user(bid) if bid else None
        item = dict(d)
        item["seller_username"] = ((su["username"] if su else None) or "").lstrip("@")
        item["buyer_username"] = ((bu["username"] if bu else None) or "").lstrip("@")
        item["my_role"] = "seller" if sid == uid else "buyer" if bid == uid else ""
        out_deals.append(item)

    reviews = [_review_json(r) for r in await db.list_user_reviews(uid, uname, limit=40)]
    return web.json_response(
        {
            "ok": True,
            "profile": {
                "user_id": uid,
                "username": uname,
                "full_name": full_name,
                "rating": avg,
                "rating_count": cnt,
                "completed_deals": completed,
                "is_self": uid == viewer,
                "deals": out_deals,
                "reviews": reviews,
            },
        },
        headers={"Cache-Control": "no-store"},
    )


async def api_admin_review_delete(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    if not await is_admin(int(tg_user["id"])):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    try:
        rid = int(request.match_info["rid"])
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "input"}, status=400)
    ok = await db.delete_review(rid)
    return web.json_response({"ok": True, "deleted": ok})


async def api_admin_review_move(request: web.Request) -> web.Response:
    tg_user, err = await _auth(request)
    if err:
        return err
    if not await is_admin(int(tg_user["id"])):
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    try:
        rid = int(request.match_info["rid"])
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "input"}, status=400)
    body = await request.json()
    direction = str(body.get("direction") or "up")
    if direction not in {"up", "down"}:
        return web.json_response({"ok": False, "error": "input"}, status=400)
    ok = await db.move_review(rid, direction)
    rows = await db.list_reviews(newest_first=True)
    return web.json_response({"ok": True, "moved": ok, "reviews": [_review_json(r) for r in rows]})


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


async def serve_nft_img(request: web.Request) -> web.StreamResponse:
    """Прокси картинок Fragment — стабильно в Mini App WebView."""
    raw = str(request.match_info.get("slug") or "")
    slug = raw.rsplit(".", 1)[0] if "." in raw else raw
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", slug):
        raise web.HTTPNotFound()
    low = slug.lower()
    NFT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    cached = NFT_IMG_DIR / f"{low}.jpg"
    if cached.is_file() and cached.stat().st_size > 200:
        return web.FileResponse(
            cached,
            headers={"Cache-Control": "public, max-age=604800"},
        )

    candidates = [
        f"https://nft.fragment.com/gift/{low}.medium.jpg",
        f"https://nft.fragment.com/gift/{low}.large.jpg",
        f"https://nft.fragment.com/gift/{low}.webp",
        f"https://nft.fragment.com/gift/{slug}.medium.jpg",
        f"https://nft.fragment.com/gift/{slug}.webp",
    ]
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=12)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; GGSelBot/1.0)",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    data: bytes | None = None
    content_type = "image/jpeg"
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for url in candidates:
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        body = await resp.read()
                        if len(body) < 200:
                            continue
                        data = body
                        content_type = resp.headers.get("Content-Type") or content_type
                        break
                except Exception:
                    continue
    except Exception as exc:
        log.warning("nft img fetch %s: %s", low, exc)

    if not data:
        raise web.HTTPNotFound()

    try:
        cached.write_bytes(data)
    except OSError:
        pass
    return web.Response(
        body=data,
        content_type=content_type.split(";")[0].strip() or "image/jpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    )


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/profile/{key}", api_public_profile)
    app.router.add_post("/api/language", api_language)
    app.router.add_post("/api/requisites", api_requisites)
    app.router.add_post("/api/withdraw", api_withdraw)
    app.router.add_get("/api/deals", api_deals_list)
    app.router.add_get("/api/deals/{code}", api_deal_get)
    app.router.add_post("/api/deals", api_deals_create)
    app.router.add_post("/api/deals/{code}/cancel", api_deal_cancel)
    app.router.add_post("/api/deals/{code}/join", api_deal_join)
    app.router.add_post("/api/deals/{code}/paybal", api_deal_paybal)
    app.router.add_post("/api/deals/{code}/sent", api_deal_sent)
    app.router.add_post("/api/deals/{code}/recv", api_deal_recv)
    app.router.add_get("/api/reviews", api_reviews_list)
    app.router.add_get("/api/feed", api_feed)
    app.router.add_get("/api/feed/{rid}", api_feed_item)
    app.router.add_get("/api/market", api_market)
    app.router.add_post("/api/admin/credit", api_admin_credit)
    app.router.add_post("/api/admin/transfer", api_admin_transfer)
    app.router.add_post("/api/admin/grant", api_admin_grant)
    app.router.add_post("/api/admin/ban", api_admin_ban)
    app.router.add_get("/api/admin/workers", api_admin_workers)
    app.router.add_post("/api/admin/reviews", api_admin_review_add)
    app.router.add_post("/api/admin/reviews/{rid}/delete", api_admin_review_delete)
    app.router.add_post("/api/admin/reviews/{rid}/move", api_admin_review_move)
    app.router.add_get("/e/{key}.webp", serve_emoji)
    app.router.add_get("/n/{slug}", serve_nft_img)
    app.router.add_static("/assets", path=str(WEBAPP_DIR), name="webapp_static")
    app.router.add_get("/l/{lang}/deal/{code}", index)
    app.router.add_get("/l/{lang}", index)
    app.router.add_get("/deal/{code}", index)
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
