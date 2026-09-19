from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from config import SUPPORT_URL, WEBAPP_URL
from texts.deal_messages import CURRENCY_NAMES
from texts.i18n import t
from utils.emoji import icon_id


def _btn(
    text: str,
    *,
    fallback_emoji: str,
    callback: str | None = None,
    url: str | None = None,
    icon_key: str | None = None,
) -> InlineKeyboardButton:
    emoji = icon_id(icon_key) if icon_key else None
    label = text if emoji else f"{fallback_emoji} {text}"
    kwargs: dict = {"text": label}
    if callback:
        kwargs["callback_data"] = callback
    if url:
        kwargs["url"] = url
    if emoji:
        kwargs["icon_custom_emoji_id"] = emoji
    return InlineKeyboardButton(**kwargs)


def miniapp_reply_kb() -> ReplyKeyboardMarkup | None:
    if not WEBAPP_URL:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Открыть GGSel", web_app=WebAppInfo(url=WEBAPP_URL))]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def main_menu(lang: str | None = "ru", *, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(t(lang, "btn_requisites"), fallback_emoji="💼", callback="menu:requisites", icon_key="btn_requisites"),
            _btn(t(lang, "btn_create"), fallback_emoji="➕", callback="menu:create", icon_key="btn_create"),
        ],
        [
            _btn(t(lang, "btn_balance"), fallback_emoji="🧳", callback="menu:balance", icon_key="btn_balance"),
            _btn(t(lang, "btn_deals"), fallback_emoji="📑", callback="menu:deals", icon_key="btn_deals"),
        ],
        [
            _btn(t(lang, "btn_refs"), fallback_emoji="🌐", callback="menu:refs", icon_key="btn_refs"),
            _btn(t(lang, "btn_lang"), fallback_emoji="🌐", callback="menu:lang", icon_key="btn_lang"),
        ],
        [_btn(t(lang, "btn_support"), fallback_emoji="🎧", url=SUPPORT_URL, icon_key="btn_support")],
    ]
    if is_admin:
        rows.append(
            [_btn(t(lang, "btn_admin"), fallback_emoji="🛠", callback="menu:admin", icon_key="btn_admin")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def requisites_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn_ton"), fallback_emoji="💎", callback="req:ton", icon_key="btn_ton")],
            [_btn(t(lang, "btn_card"), fallback_emoji="💳", callback="req:card", icon_key="btn_card")],
            [
                _btn(
                    t(lang, "btn_username"),
                    fallback_emoji="👤",
                    callback="req:username",
                    icon_key="btn_role_buyer",
                )
            ],
            [_btn(t(lang, "btn_back"), fallback_emoji="🔙", callback="menu:home", icon_key="btn_back")],
        ]
    )


def deal_role_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Я продавец", fallback_emoji="🏷", callback="deal:role:seller", icon_key="btn_role_seller")],
            [_btn("Я покупатель", fallback_emoji="🛒", callback="deal:role:buyer", icon_key="btn_role_buyer")],
            [_btn(t(lang, "btn_back"), fallback_emoji="🔙", callback="menu:home", icon_key="btn_back")],
        ]
    )


def deal_created_kb(code: str, lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Отменить сделку", fallback_emoji="❌", callback=f"deal:abort:{code}", icon_key="btn_cancel")],
            [_btn("Назад в меню", fallback_emoji="🔙", callback="menu:home", icon_key="btn_back")],
        ]
    )


def deal_type_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn_gift"), fallback_emoji="🎁", callback="deal:type:gift", icon_key="btn_deal_gift")],
            [_btn(t(lang, "btn_channel"), fallback_emoji="📣", callback="deal:type:channel", icon_key="btn_deal_channel")],
            [_btn(t(lang, "btn_stars"), fallback_emoji="⭐", callback="deal:type:stars", icon_key="btn_deal_stars")],
            [_btn(t(lang, "btn_nft"), fallback_emoji="⛓️", callback="deal:type:nft", icon_key="btn_deal_nft")],
            [_btn(t(lang, "btn_back"), fallback_emoji="🔙", callback="menu:home", icon_key="btn_back")],
        ]
    )


def deal_pay_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    from utils.currencies import PAY_METHODS, rows_of

    buttons = [
        _btn(
            t(lang, text_key),
            fallback_emoji=fallback,
            callback=f"deal:pay:{pay_key}",
            icon_key=icon_key,
        )
        for pay_key, text_key, fallback, icon_key in PAY_METHODS
    ]
    rows = rows_of(buttons, 2)
    rows.append(
        [_btn(t(lang, "btn_back"), fallback_emoji="🔄", callback="menu:home", icon_key="btn_back_alt")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn_lang_ru"), fallback_emoji="🇷🇺", callback="lang:ru", icon_key="btn_lang_ru")],
            [_btn(t(lang, "btn_lang_en"), fallback_emoji="🇬🇧", callback="lang:en", icon_key="btn_lang_en")],
            [_btn(t(lang, "btn_back"), fallback_emoji="🔙", callback="menu:home", icon_key="btn_back")],
        ]
    )


def cancel_deal_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn_cancel"), fallback_emoji="❌", callback="deal:cancel", icon_key="btn_cancel")]
        ]
    )


def cancel_requisites_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn_cancel"), fallback_emoji="❌", callback="req:cancel", icon_key="btn_cancel")]
        ]
    )


def back_to_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn_back"), fallback_emoji="🔙", callback="menu:home", icon_key="btn_back")]
        ]
    )


def back_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    return back_to_menu(lang)


def balance_menu(lang: str | None = "ru") -> InlineKeyboardMarkup:
    from utils.currencies import WITHDRAW_METHODS, rows_of

    withdraw_btns = {
        "ton": ("btn_withdraw_ton", "💎", "btn_pay_ton"),
        "card": ("btn_withdraw_card", "💳", "btn_pay_card"),
        "byn": ("btn_withdraw_byn", "🇧🇾", "btn_pay_byn"),
        "kzt": ("btn_withdraw_kzt", "🇰🇿", "btn_pay_kzt"),
        "uah": ("btn_withdraw_uah", "🇺🇦", "btn_pay_uah"),
        "stars": ("btn_withdraw_stars", "⭐", "btn_pay_stars"),
        "usdt": ("btn_withdraw_usdt", "🪙", "btn_pay_usdt"),
        "usd": ("btn_withdraw_usd", "💸", "btn_pay_usd"),
        "eur": ("btn_withdraw_eur", "💰", "btn_pay_eur"),
    }
    buttons = []
    for method in WITHDRAW_METHODS:
        text_key, fallback, icon_key = withdraw_btns[method]
        buttons.append(
            _btn(
                t(lang, text_key),
                fallback_emoji=fallback,
                callback=f"withdraw:{method}",
                icon_key=icon_key,
            )
        )
    rows = rows_of(buttons, 2)
    rows.append([_btn(t(lang, "btn_back"), fallback_emoji="🔙", callback="menu:home", icon_key="btn_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def seller_deal_kb(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(
                    "Товар передан гаранту",
                    fallback_emoji="📦",
                    callback=f"deal:sent:{code}",
                    icon_key="btn_deal_sent",
                )
            ]
        ]
    )


def buyer_deal_kb(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(
                    "Подтвердить получение",
                    fallback_emoji="✅",
                    callback=f"deal:recv:{code}",
                    icon_key="btn_deal_recv",
                )
            ]
        ]
    )


def buyer_pay_kb(code: str, amount: float, pay_method: str, lang: str | None = "ru") -> InlineKeyboardMarkup:
    currency = CURRENCY_NAMES.get(pay_method, pay_method.upper())
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Оплатить с баланса ({amount:.1f} {currency})",
                    callback_data=f"deal:paybal:{code}",
                )
            ],
            [
                _btn(
                    t(lang, "btn_support"),
                    fallback_emoji="🎧",
                    url=SUPPORT_URL,
                    icon_key="btn_support",
                )
            ],
            [
                _btn(
                    "Назад в меню",
                    fallback_emoji="🔙",
                    callback="menu:home",
                    icon_key="btn_back",
                )
            ],
        ]
    )
