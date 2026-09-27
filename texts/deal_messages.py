from __future__ import annotations

from config import MANAGER_USERNAME
from utils.emoji import ce

CURRENCY_NAMES = {
    "stars": "STARS",
    "ton": "TON",
    "card": "RUB",
    "usdt": "USDT",
}
CURRENCY_EMOJI_KEYS = {
    "stars": ("balance_stars", "⭐"),
    "ton": ("balance_ton", "💎"),
    "card": ("balance_card", "💳"),
    "usdt": ("balance_usdt", "🪙"),
}

# Дополняем всеми мировыми валютами
try:
    from utils.currencies import BALANCE_META

    for _code, _meta in BALANCE_META.items():
        CURRENCY_NAMES.setdefault(_code, _meta["label"])
        CURRENCY_EMOJI_KEYS.setdefault(
            _code, (_meta["emoji_key"], _meta["fallback"])
        )
except Exception:
    pass


def currency_icon(pay_method: str) -> str:
    key, fallback = CURRENCY_EMOJI_KEYS.get(pay_method, ("", "💱"))
    return ce(key, fallback) if key else fallback


def _manager_pay_notice_blockquote() -> str:
    shield = ce("deal_shield", "🛡")
    chat = ce("deal_chat", "💬")
    manager = MANAGER_USERNAME.lstrip("@")
    return (
        f"<blockquote>"
        f"{shield} Оплата идёт через бота. Товар передаётся <b>ТОЛЬКО</b> через гаранта @{manager}.\n"
        f"\n"
        f"{chat} <i>После оплаты покупателем — передайте товар гаранту.</i>"
        f"</blockquote>"
    )


def deal_created_text(
    *,
    code: str,
    role: str,
    pay_method: str,
    amount: float,
    description: str,
    bot_username: str,
) -> str:
    check = ce("deal_check", "✅")
    cart = ce("deal_cart", "🛒")
    money = ce("deal_money", "💰")
    pen = ce("deal_pen", "✍️")
    link_icon = ce("deal_link", "🔗")

    role_label = "Покупатель" if role == "buyer" else "Продавец"
    other = "продавца" if role == "buyer" else "покупателя"
    currency = CURRENCY_NAMES.get(pay_method, pay_method.upper())
    flag = currency_icon(pay_method)
    desc = description.strip() or "—"
    invite = f"https://t.me/{bot_username}?start=deal_{code}"

    return (
        f"{check} Сделка <b>#{code}</b> успешно создана!\n"
        f"\n"
        f"<blockquote>"
        f"{cart} <b>Роль:</b> {role_label}\n"
        f"{flag} <b>Валюта:</b> {currency}\n"
        f"{money} <b>Сумма:</b> {amount:.1f}\n"
        f"{pen} <b>Описание:</b> {desc}"
        f"</blockquote>\n"
        f"\n"
        f"{link_icon} <b>Ссылка для {other}:</b>\n"
        f"{invite}\n"
        f"\n"
        f"Или пригласите через инлайн: введите @{bot_username} #{code} в любом чате"
    )


def seller_deal_connected_text(
    *,
    code: str,
    buyer_username: str | None,
    buyer_id: int,
    buyer_deals: int,
    description: str,
    pay_method: str,
    amount: float,
) -> str:
    check = ce("deal_check", "✔️")
    buyers = ce("deal_buyers", "👥")
    thought = ce("deal_thought", "💭")
    chart = ce("deal_chart", "📈")
    memo = ce("deal_memo", "📝")
    star = ce("deal_star", "⭐")
    excl = ce("deal_excl", "❕")

    buyer_mention = f"@{buyer_username}" if buyer_username else f"<code>{buyer_id}</code>"
    currency = CURRENCY_NAMES.get(pay_method, pay_method.upper())
    desc = description.strip() or "—"
    manager = MANAGER_USERNAME.lstrip("@")
    handshake = ce("handshake", "🤝")

    return (
        f"{check} Вы подключились к сделке <b>#{code}</b> как <i>продавец</i>.\n"
        f"\n"
        f"{buyers} <b>Покупатель:</b> {buyer_mention}\n"
        f"{thought} <b>ID покупателя:</b> <code>{buyer_id}</code>\n"
        f"{chart} <b>Сделок у покупателя:</b> {buyer_deals}\n"
        f"{memo} <b>Описание:</b> {desc}\n"
        f"{star} <b>Валюта:</b> {currency}\n"
        f"{excl} <b>Сумма:</b> {amount:.1f}\n"
        f"{handshake} <b>Гарант:</b> @{manager}\n"
        f"\n"
        f"{_manager_pay_notice_blockquote()}"
    )


def seller_after_payment_text() -> str:
    return _manager_pay_notice_blockquote()


def buyer_seller_joined_text(
    *,
    code: str,
    seller_username: str | None,
    seller_id: int,
    seller_completed_deals: int,
) -> str:
    bolt = ce("lightning", "⚡️")
    chart = ce("deal_chart", "📈")
    shield = ce("deal_shield", "🛡")
    excl = ce("deal_excl", "❗️")

    seller_mention = f"@{seller_username}" if seller_username else f"<code>{seller_id}</code>"
    manager = MANAGER_USERNAME.lstrip("@")
    handshake = ce("handshake", "🤝")

    return (
        f"{bolt} К сделке <b>#{code}</b> присоединился продавец <b>{seller_mention}</b>!\n"
        f"\n"
        f"<blockquote>"
        f"{handshake} Гарант сделки: @{manager}\n"
        f"{chart} Завершённых сделок у продавца: <b>{seller_completed_deals}</b>"
        f"</blockquote>\n"
        f"\n"
        f"{shield} Оплата — <b>только с баланса бота</b>. "
        f"Не переводите средства напрямую продавцу!\n"
        f"{excl} Товар передаётся через гаранта @{manager}."
    )


def buyer_payment_accepted_text(
    *,
    code: str,
    seller_username: str | None,
    seller_id: int,
    description: str,
    pay_method: str,
    amount: float,
) -> str:
    bell = ce("deal_bell", "🔔")
    person = ce("deal_person", "👤")
    money = ce("deal_money", "💰")
    memo = ce("deal_memo", "📝")
    sparkle = ce("deal_sparkle", "✨")

    seller_mention = f"@{seller_username}" if seller_username else f"<code>{seller_id}</code>"
    currency = CURRENCY_NAMES.get(pay_method, pay_method.upper())
    desc = description.strip() or "—"
    manager = MANAGER_USERNAME.lstrip("@")

    return (
        f"{bell} Ваша оплата по сделке <b>#{code}</b> принята!\n"
        f"\n"
        f"{person} <b>Продавец:</b> {seller_mention}\n"
        f"{money} <b>Сумма:</b> {amount:.1f} {currency}\n"
        f"{memo} <b>Описание:</b> {desc}\n"
        f"\n"
        f"{sparkle} Ожидайте — продавец передаёт товар гаранту @{manager}. "
        f"После этого вы сможете подтвердить получение."
    )


def buyer_goods_ready_text(*, code: str, manager: str | None = None) -> str:
    manager = (manager or MANAGER_USERNAME).lstrip("@")
    check = ce("deal_check", "✔️")
    return (
        f"{check} Продавец передал товар по сделке <b>#{code}</b> гаранту @{manager}.\n\n"
        f"Нажмите кнопку ниже, когда получите товар."
    )


def deal_completed_text(*, code: str, role: str) -> str:
    check = ce("deal_check", "✔️")
    if role == "seller":
        return f"{check} Покупатель подтвердил получение по сделке <b>#{code}</b>.\nСделка завершена."
    return f"{check} Вы подтвердили получение по сделке <b>#{code}</b>.\nСделка завершена."


def manager_balance_sent_text(*, amount: float | int, currency: str) -> str:
    from utils.currencies import BALANCE_META

    meta = BALANCE_META.get(currency) or {
        "label": currency.upper(),
        "fallback": "💰",
        "emoji_key": "deal_money",
        "integer": False,
    }
    icon = ce(meta["emoji_key"], meta["fallback"])
    sparkle = ce("deal_sparkle", "✨")
    person = ce("deal_person", "👤")
    check = ce("deal_check", "✅")
    handshake = ce("handshake", "🤝")
    money = ce("deal_money", "💰")
    manager = MANAGER_USERNAME.lstrip("@")
    if meta.get("integer"):
        amount_text = str(int(amount))
    else:
        amount_text = f"{float(amount):g}"
    return (
        f"{money} <b>Вам поступили средства на баланс бота</b>\n"
        f"\n"
        f"<blockquote>"
        f"{person} Отправитель: менеджер @{manager}\n"
        f"{icon} Валюта: <b>{meta['label']}</b>\n"
        f"{sparkle} Сумма: <b>{amount_text}</b>"
        f"</blockquote>\n"
        f"\n"
        f"{handshake} Средства переданы менеджером, не второй стороной сделки.\n"
        f"{check} Они уже на вашем балансе в боте."
    )
