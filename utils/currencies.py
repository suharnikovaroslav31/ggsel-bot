"""Валюты баланса и методы оплаты сделок."""

from __future__ import annotations

# Колонки баланса в БД
BALANCE_KEYS = ("ton", "rub", "byn", "kzt", "stars", "usdt", "usd", "eur")

# Группы для красивого отображения баланса
BALANCE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Crypto", ("ton", "usdt", "stars")),
    ("Fiat", ("rub", "byn", "kzt", "usd", "eur")),
)

# pay_method сделки → ключ баланса
PAY_TO_BALANCE = {
    "ton": "ton",
    "card": "rub",
    "stars": "stars",
    "usdt": "usdt",
    "usd": "usd",
    "eur": "eur",
    "byn": "byn",
    "kzt": "kzt",
}

# Метаданные валют баланса
BALANCE_META: dict[str, dict] = {
    "ton": {
        "label": "TON",
        "fallback": "💎",
        "emoji_key": "balance_ton",
        "btn_icon": "btn_pay_ton",
        "integer": False,
    },
    "rub": {
        "label": "RUB",
        "fallback": "💵",
        "emoji_key": "balance_rub",
        "btn_icon": "btn_pay_rub",
        "integer": False,
    },
    "byn": {
        "label": "BYN",
        "fallback": "🇧🇾",
        "emoji_key": "balance_byn",
        "btn_icon": "btn_pay_byn",
        "integer": False,
    },
    "kzt": {
        "label": "KZT",
        "fallback": "🇰🇿",
        "emoji_key": "balance_kzt",
        "btn_icon": "btn_pay_kzt",
        "integer": False,
    },
    "stars": {
        "label": "STARS",
        "fallback": "⭐",
        "emoji_key": "balance_stars",
        "btn_icon": "btn_pay_stars",
        "integer": True,
    },
    "usdt": {
        "label": "USDT",
        "fallback": "🪙",
        "emoji_key": "balance_usdt",
        "btn_icon": "btn_pay_usdt",
        "integer": False,
    },
    "usd": {
        "label": "USD",
        "fallback": "💸",
        "emoji_key": "balance_usd",
        "btn_icon": "btn_pay_usd",
        "integer": False,
    },
    "eur": {
        "label": "EUR",
        "fallback": "💰",
        "emoji_key": "balance_eur",
        "btn_icon": "btn_pay_eur",
        "integer": False,
    },
}

# Методы оплаты: (pay_key, i18n_btn_key, fallback, icon_key)
PAY_METHODS: tuple[tuple[str, str, str, str], ...] = (
    ("ton", "btn_pay_ton", "💎", "btn_pay_ton"),
    ("card", "btn_pay_card", "💳", "btn_pay_card"),
    ("stars", "btn_pay_stars", "⭐", "btn_pay_stars"),
    ("usdt", "btn_pay_usdt", "🪙", "btn_pay_usdt"),
    ("usd", "btn_pay_usd", "💸", "btn_pay_usd"),
    ("eur", "btn_pay_eur", "💰", "btn_pay_eur"),
    ("byn", "btn_pay_byn", "🇧🇾", "btn_pay_byn"),
    ("kzt", "btn_pay_kzt", "🇰🇿", "btn_pay_kzt"),
)

# Вывод: withdraw_callback → (balance_key, label, requisite: ton|card|username)
WITHDRAW_METHODS = {
    "ton": ("ton", "TON", "ton"),
    "card": ("rub", "RUB", "card"),
    "byn": ("byn", "BYN", "card"),
    "kzt": ("kzt", "KZT", "card"),
    "stars": ("stars", "STARS", "username"),
    "usdt": ("usdt", "USDT", "ton"),
    "usd": ("usd", "USD", "card"),
    "eur": ("eur", "EUR", "card"),
}

# Реквизиты продавца при создании сделки
PAY_REQUISITE = {
    "ton": "ton",
    "usdt": "ton",
    "card": "card",
    "usd": "card",
    "eur": "card",
    "byn": "card",
    "kzt": "card",
}


def rows_of(items: list, n: int = 2) -> list[list]:
    """Упаковать кнопки по n в ряд."""
    return [items[i : i + n] for i in range(0, len(items), n)]
