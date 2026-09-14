from __future__ import annotations

from config import MANAGER_USERNAME
from utils.emoji import ce

TEXTS = {
    "ru": {
        "welcome": (
            "{coffee} <b>Добро пожаловать в GGSel</b> {construction}\n"
            "\n"
            "<blockquote>"
            "{lightning} <b>Ваш надежный P2P-гарант:</b>\n"
            "\n"
            "{one} Автоматические сделки с NFT и подарками\n"
            "{two} {shield} Полная защита обеих сторон\n"
            "{three} {trident} Реферальная программа - 50% от комиссии\n"
            "{four} {handshake} Передача товаров через гаранта:\n"
            "@{manager}"
            "</blockquote>"
        ),
        "btn_requisites": "Мои реквизиты",
        "btn_create": "Создать сделку",
        "btn_balance": "Баланс",
        "btn_withdraw_ton": "Вывод на TON-кошелёк",
        "btn_withdraw_card": "Вывод на карту",
        "btn_withdraw_stars": "Вывод Stars",
        "balance_withdraw_hint": "Для вывода средств нужно совершить 3 сделки",
        "balance_withdraw_need_deals": "Для вывода нужно минимум 3 завершённых сделки. Сейчас: {count}",
        "balance_withdraw_empty": "Недостаточно средств на балансе",
        "balance_withdraw_need_ton": "Сначала добавьте TON-кошелёк в «Мои реквизиты»",
        "balance_withdraw_need_card": "Сначала добавьте карту в «Мои реквизиты»",
        "balance_withdraw_ask": "{money} Введите сумму вывода ({currency})\nДоступно: <b>{available}</b>",
        "balance_withdraw_done": "{check} Заявка на вывод <b>{amount}</b> {currency} принята.\n{sparkle} Гарант @{manager} обработает её в ближайшее время.",
        "btn_deals": "Мои сделки",
        "btn_refs": "Рефералы",
        "btn_lang": "Язык / Lang",
        "btn_support": "Техподдержка",
        "btn_admin": "Админ-панель",
        "btn_back": "Вернуться в меню",
        "btn_cancel": "Отмена",
        "btn_ton": "Добавить/изменить TON кошелек",
        "btn_card": "Добавить/изменить карту",
        "btn_username": "Добавить/изменить юзернейм",
        "btn_gift": "Подарок",
        "btn_channel": "Канал/чат",
        "btn_stars": "Звезды",
        "btn_nft": "НФТ Юзернейм",
        "btn_pay_ton": "На TON-кошелек",
        "btn_pay_card": "На карту",
        "btn_pay_stars": "Звезды",
        "btn_pay_usdt": "USDT",
        "btn_pay_usd": "USD",
        "btn_pay_eur": "EUR",
        "btn_pay_byn": "BYN",
        "btn_pay_kzt": "KZT",
        "btn_pay_uah": "UAH",
        "btn_withdraw_usdt": "Вывод USDT",
        "btn_withdraw_usd": "Вывод USD",
        "btn_withdraw_eur": "Вывод EUR",
        "btn_withdraw_byn": "Вывод BYN",
        "btn_withdraw_kzt": "Вывод KZT",
        "btn_withdraw_uah": "Вывод UAH",
        "btn_lang_ru": "Русский",
        "btn_lang_en": "English",
        "requisites_title": "Управление реквизитами",
        "requisites_hint": "Используйте кнопки ниже чтобы добавить/изменить реквизиты",
        "balance_title": "Ваш баланс",
        "lang_title": "Выбор языка / Language",
        "lang_current": "Сейчас: <b>{name}</b>",
        "lang_changed": "✅ Язык изменён на Русский",
        "lang_name": "Русский",
        "deal_type": "— Выберите тип сделки:",
        "deal_pay": "Выберите метод получения оплаты:",
        "deal_create_title": "Создание сделки",
        "deal_type_label": "Тип",
        "deal_pay_label": "Оплата",
        "deal_amount_prompt": "Введите сумму сделки числом\n(например: <code>100</code> или <code>49.5</code>)",
        "deal_created": "✅ <b>Сделка создана</b>",
        "deal_amount": "Сумма",
        "deal_code": "Код",
        "deal_link": "Ссылка для второй стороны",
        "deals_title": "Мои сделки",
        "deals_empty": "Активных сделок пока нет.",
        "refs_title": "Реферальная программа",
        "refs_text": "Вы получаете <b>50%</b> от комиссии бота.",
        "refs_invited": "Приглашено",
        "refs_link": "Ваша ссылка",
        "role_seller": "продавец",
        "role_buyer": "покупатель",
        "ask_ton": "{ton} <b>TON кошелек</b>\n\nОтправьте адрес кошелька одним сообщением.\nПример: <code>UQ...</code> или <code>EQ...</code>",
        "ask_card": "{card} <b>Банковская карта</b>\n\nОтправьте номер карты одним сообщением.\nТолько цифры, 13–19 символов.",
        "ask_username": "{person} <b>Юзернейм для вывода</b>\n\nОтправьте юзернейм одним сообщением.\nПример: <code>@username</code> или <code>username</code>",
        "saved_ton": "{check} TON кошелек сохранён.",
        "saved_card": "{check} Карта сохранена.",
        "saved_username": "{check} Юзернейм сохранён.",
        "need_ton": "Сначала добавьте TON кошелек в реквизитах",
        "need_card": "Сначала добавьте карту в реквизитах",
        "balance_withdraw_need_username": "Сначала добавьте юзернейм в «Мои реквизиты»",
        "deal_type_gift": "Подарок",
        "deal_type_channel": "Канал/чат",
        "deal_type_stars": "Звезды",
        "deal_type_nft": "НФТ Юзернейм",
        "deal_pay_ton": "TON-кошелек",
        "deal_pay_card": "Карта",
        "deal_pay_stars": "Звезды",
        "deal_pay_usdt": "USDT",
        "deal_pay_usd": "USD",
        "deal_pay_eur": "EUR",
        "deal_pay_byn": "BYN",
        "deal_pay_kzt": "KZT",
        "deal_pay_uah": "UAH",
    },
    "en": {
        "welcome": (
            "{coffee} <b>Welcome to GGSel</b> {construction}\n"
            "\n"
            "<blockquote>"
            "{lightning} <b>Your reliable P2P guarantor:</b>\n"
            "\n"
            "{one} Automatic deals with NFTs and gifts\n"
            "{two} {shield} Full protection for both sides\n"
            "{three} {trident} Referral program - 50% of the fee\n"
            "{four} {handshake} Goods transfer via guarantor:\n"
            "@{manager}"
            "</blockquote>"
        ),
        "btn_requisites": "My details",
        "btn_create": "Create deal",
        "btn_balance": "Balance",
        "btn_withdraw_ton": "Withdraw to TON wallet",
        "btn_withdraw_card": "Withdraw to card",
        "btn_withdraw_stars": "Withdraw Stars",
        "balance_withdraw_hint": "To withdraw funds you need to complete 3 deals",
        "balance_withdraw_need_deals": "Withdrawal requires at least 3 completed deals. Now: {count}",
        "balance_withdraw_empty": "Insufficient balance",
        "balance_withdraw_need_ton": "Add a TON wallet in “My details” first",
        "balance_withdraw_need_card": "Add a card in “My details” first",
        "balance_withdraw_ask": "{money} Enter withdrawal amount ({currency})\nAvailable: <b>{available}</b>",
        "balance_withdraw_done": "{check} Withdrawal request for <b>{amount}</b> {currency} accepted.\n{sparkle} Guarantor @{manager} will process it soon.",
        "btn_deals": "My deals",
        "btn_refs": "Referrals",
        "btn_lang": "Language / Язык",
        "btn_support": "Support",
        "btn_admin": "Admin panel",
        "btn_back": "Back to menu",
        "btn_cancel": "Cancel",
        "btn_ton": "Add/change TON wallet",
        "btn_card": "Add/change card",
        "btn_username": "Add/change username",
        "btn_gift": "Gift",
        "btn_channel": "Channel/chat",
        "btn_stars": "Stars",
        "btn_nft": "NFT Username",
        "btn_pay_ton": "To TON wallet",
        "btn_pay_card": "To card",
        "btn_pay_stars": "Stars",
        "btn_pay_usdt": "USDT",
        "btn_pay_usd": "USD",
        "btn_pay_eur": "EUR",
        "btn_pay_byn": "BYN",
        "btn_pay_kzt": "KZT",
        "btn_pay_uah": "UAH",
        "btn_withdraw_usdt": "Withdraw USDT",
        "btn_withdraw_usd": "Withdraw USD",
        "btn_withdraw_eur": "Withdraw EUR",
        "btn_withdraw_byn": "Withdraw BYN",
        "btn_withdraw_kzt": "Withdraw KZT",
        "btn_withdraw_uah": "Withdraw UAH",
        "btn_lang_ru": "Русский",
        "btn_lang_en": "English",
        "requisites_title": "Payment details",
        "requisites_hint": "Use the buttons below to add/change payment details 👇",
        "balance_title": "Your balance",
        "lang_title": "Language / Выбор языка",
        "lang_current": "Current: <b>{name}</b>",
        "lang_changed": "✅ Language changed to English",
        "lang_name": "English",
        "deal_type": "— Choose deal type:",
        "deal_pay": "Choose payment receiving method:",
        "deal_create_title": "Create deal",
        "deal_type_label": "Type",
        "deal_pay_label": "Payment",
        "deal_amount_prompt": "Enter deal amount as a number\n(e.g. <code>100</code> or <code>49.5</code>)",
        "deal_created": "✅ <b>Deal created</b>",
        "deal_amount": "Amount",
        "deal_code": "Code",
        "deal_link": "Link for the other party",
        "deals_title": "My deals",
        "deals_empty": "No active deals yet.",
        "refs_title": "Referral program",
        "refs_text": "You get <b>50%</b> of the bot fee.",
        "refs_invited": "Invited",
        "refs_link": "Your link",
        "role_seller": "seller",
        "role_buyer": "buyer",
        "ask_ton": "{ton} <b>TON wallet</b>\n\nSend wallet address in one message.\nExample: <code>UQ...</code> or <code>EQ...</code>",
        "ask_card": "{card} <b>Bank card</b>\n\nSend card number in one message.\nDigits only, 13–19 characters.",
        "ask_username": "{person} <b>Payout username</b>\n\nSend username in one message.\nExample: <code>@username</code> or <code>username</code>",
        "saved_ton": "{check} TON wallet saved.",
        "saved_card": "{check} Card saved.",
        "saved_username": "{check} Username saved.",
        "need_ton": "Add a TON wallet in payment details first",
        "need_card": "Add a card in payment details first",
        "balance_withdraw_need_username": "Add a username in “My details” first",
        "deal_type_gift": "Gift",
        "deal_type_channel": "Channel/chat",
        "deal_type_stars": "Stars",
        "deal_type_nft": "NFT Username",
        "deal_pay_ton": "TON wallet",
        "deal_pay_card": "Card",
        "deal_pay_stars": "Stars",
        "deal_pay_usdt": "USDT",
        "deal_pay_usd": "USD",
        "deal_pay_eur": "EUR",
        "deal_pay_byn": "BYN",
        "deal_pay_kzt": "KZT",
        "deal_pay_uah": "UAH",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "ru").lower().startswith("en") else "ru"


def t(lang: str | None, key: str, **kwargs) -> str:
    lang = normalize_lang(lang)
    value = TEXTS.get(lang, TEXTS["ru"]).get(key) or TEXTS["ru"].get(key, key)
    return value.format(**kwargs) if kwargs else value


def welcome_text(lang: str | None = "ru") -> str:
    return t(
        lang,
        "welcome",
        coffee=ce("coffee", "☕️"),
        construction=ce("construction", "🚧"),
        lightning=ce("lightning", "⚡️"),
        one=ce("one", "1️⃣"),
        two=ce("two", "2️⃣"),
        three=ce("three", "3️⃣"),
        four=ce("four", "4️⃣"),
        shield=ce("shield", "🛡"),
        trident=ce("trident", "🔱"),
        handshake=ce("handshake", "🤝"),
        manager=MANAGER_USERNAME,
    )


def balance_text(
    lang: str | None = "ru",
    *,
    ton: float = 0.0,
    rub: float = 0.0,
    stars: int = 0,
    usdt: float = 0.0,
    usd: float = 0.0,
    eur: float = 0.0,
    byn: float = 0.0,
    kzt: float = 0.0,
    uah: float = 0.0,
) -> str:
    from utils.currencies import BALANCE_GROUPS, BALANCE_META

    values = {
        "ton": ton,
        "rub": rub,
        "stars": stars,
        "usdt": usdt,
        "usd": usd,
        "eur": eur,
        "byn": byn,
        "kzt": kzt,
        "uah": uah,
    }
    lines = [
        f"{ce('balance_card', '💳')} <b>{t(lang, 'balance_title')}</b>",
        "",
    ]
    for group_name, keys in BALANCE_GROUPS:
        lines.append(f"<b>{group_name}</b>")
        for key in keys:
            meta = BALANCE_META[key]
            icon = ce(meta["emoji_key"], meta["fallback"])
            val = values.get(key, 0)
            if meta["integer"]:
                lines.append(f"{icon} {meta['label']}: {int(val)}")
            else:
                lines.append(f"{icon} {meta['label']}: {float(val):.2f}")
        lines.append("")
    lines.append(f"{ce('deal_excl', '❗️')} {t(lang, 'balance_withdraw_hint')}")
    return "\n".join(lines)


def requisites_text(
    lang: str | None = "ru",
    ton_wallet: str | None = None,
    card_number: str | None = None,
    payout_username: str | None = None,
) -> str:
    doc = ce("requisites_doc", "🪪")
    ton_i = ce("balance_ton", "💎")
    card_i = ce("balance_card", "💳")
    person = ce("deal_person", "👤")
    lines = [
        f"{doc} <b>{t(lang, 'requisites_title')}</b>",
        "",
        t(lang, "requisites_hint"),
    ]
    if ton_wallet or card_number or payout_username:
        lines.append("")
        if ton_wallet:
            lines.append(f"{ton_i} TON: <code>{ton_wallet}</code>")
        if card_number:
            digits = "".join(ch for ch in card_number if ch.isdigit())
            masked = (
                f"{digits[:4]} **** **** {digits[-4:]}" if len(digits) >= 4 else card_number
            )
            label = "Card" if normalize_lang(lang) == "en" else "Карта"
            lines.append(f"{card_i} {label}: <code>{masked}</code>")
        if payout_username:
            uname = payout_username if payout_username.startswith("@") else f"@{payout_username}"
            label = "Username" if normalize_lang(lang) == "en" else "Юзернейм"
            lines.append(f"{person} {label}: <b>{uname}</b>")
    return "\n".join(lines)


def ask_requisite_text(lang: str | None, key: str) -> str:
    return t(
        lang,
        key,
        ton=ce("balance_ton", "💎"),
        card=ce("balance_card", "💳"),
        person=ce("deal_person", "👤"),
        check=ce("deal_check", "✅"),
    )


def saved_requisite_text(lang: str | None, key: str) -> str:
    return t(lang, key, check=ce("deal_check", "✅"))


def withdraw_done_text(lang: str | None, *, amount: str, currency: str, manager: str) -> str:
    return t(
        lang,
        "balance_withdraw_done",
        amount=amount,
        currency=currency,
        manager=manager,
        check=ce("deal_check", "✅"),
        sparkle=ce("deal_sparkle", "✨"),
    )


def withdraw_ask_text(lang: str | None, *, currency: str, available: str) -> str:
    return t(
        lang,
        "balance_withdraw_ask",
        currency=currency,
        available=available,
        money=ce("deal_money", "💰"),
    )


def lang_text(lang: str | None = "ru") -> str:
    lang = normalize_lang(lang)
    return (
        f"🌐 <b>{t(lang, 'lang_title')}</b>\n\n"
        f"{t(lang, 'lang_current', name=t(lang, 'lang_name'))}"
    )


def deal_type_labels(lang: str | None = "ru") -> dict[str, str]:
    return {
        "gift": f"🎁 {t(lang, 'deal_type_gift')}",
        "channel": f"📣 {t(lang, 'deal_type_channel')}",
        "stars": f"⭐ {t(lang, 'deal_type_stars')}",
        "nft": f"⛓️ {t(lang, 'deal_type_nft')}",
    }


def deal_pay_labels(lang: str | None = "ru") -> dict[str, str]:
    return {
        "ton": f"{ce('balance_ton', '💎')} {t(lang, 'deal_pay_ton')}",
        "card": f"{ce('balance_card', '💳')} {t(lang, 'deal_pay_card')}",
        "stars": f"{ce('balance_stars', '⭐')} {t(lang, 'deal_pay_stars')}",
        "usdt": f"{ce('balance_usdt', '🪙')} {t(lang, 'deal_pay_usdt')}",
        "usd": f"{ce('balance_usd', '💸')} {t(lang, 'deal_pay_usd')}",
        "eur": f"{ce('balance_eur', '💰')} {t(lang, 'deal_pay_eur')}",
        "byn": f"{ce('balance_byn', '🇧🇾')} {t(lang, 'deal_pay_byn')}",
        "kzt": f"{ce('balance_kzt', '🇰🇿')} {t(lang, 'deal_pay_kzt')}",
        "uah": f"{ce('balance_uah', '🇺🇦')} {t(lang, 'deal_pay_uah')}",
    }
