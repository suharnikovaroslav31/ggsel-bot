"""Валюты баланса и методы оплаты сделок — все валюты мира + crypto."""

from __future__ import annotations

# (code, symbol, name_en, flag_or_emoji, group)
# code хранится в нижнем регистре; колонка БД = balance_{code}
_WORLD_FIAT: tuple[tuple[str, str, str, str, str], ...] = (
    # Europe
    ("eur", "€", "Euro", "🇪🇺", "Europe"),
    ("rub", "₽", "Russian Ruble", "🇷🇺", "Europe"),
    ("uah", "₴", "Ukrainian Hryvnia", "🇺🇦", "Europe"),
    ("byn", "Br", "Belarusian Ruble", "🇧🇾", "Europe"),
    ("gbp", "£", "British Pound", "🇬🇧", "Europe"),
    ("chf", "Fr", "Swiss Franc", "🇨🇭", "Europe"),
    ("pln", "zł", "Polish Zloty", "🇵🇱", "Europe"),
    ("czk", "Kč", "Czech Koruna", "🇨🇿", "Europe"),
    ("huf", "Ft", "Hungarian Forint", "🇭🇺", "Europe"),
    ("ron", "lei", "Romanian Leu", "🇷🇴", "Europe"),
    ("bgn", "лв", "Bulgarian Lev", "🇧🇬", "Europe"),
    ("rsd", "дин", "Serbian Dinar", "🇷🇸", "Europe"),
    ("try", "₺", "Turkish Lira", "🇹🇷", "Europe"),
    ("nok", "kr", "Norwegian Krone", "🇳🇴", "Europe"),
    ("sek", "kr", "Swedish Krona", "🇸🇪", "Europe"),
    ("dkk", "kr", "Danish Krone", "🇩🇰", "Europe"),
    ("isk", "kr", "Icelandic Krona", "🇮🇸", "Europe"),
    ("gel", "₾", "Georgian Lari", "🇬🇪", "Europe"),
    ("amd", "֏", "Armenian Dram", "🇦🇲", "Europe"),
    ("azn", "₼", "Azerbaijani Manat", "🇦🇿", "Europe"),
    ("mdl", "L", "Moldovan Leu", "🇲🇩", "Europe"),
    ("all", "L", "Albanian Lek", "🇦🇱", "Europe"),
    ("mkd", "ден", "Macedonian Denar", "🇲🇰", "Europe"),
    ("bam", "KM", "Bosnia Mark", "🇧🇦", "Europe"),
    ("hrk", "kn", "Croatian Kuna", "🇭🇷", "Europe"),
    # CIS / Central Asia
    ("kzt", "₸", "Kazakhstani Tenge", "🇰🇿", "CIS"),
    ("uzs", "soʻm", "Uzbekistani Som", "🇺🇿", "CIS"),
    ("kgs", "сом", "Kyrgyzstani Som", "🇰🇬", "CIS"),
    ("tjs", "ЅМ", "Tajikistani Somoni", "🇹🇯", "CIS"),
    ("tmt", "m", "Turkmenistani Manat", "🇹🇲", "CIS"),
    # Americas
    ("usd", "$", "US Dollar", "🇺🇸", "Americas"),
    ("cad", "C$", "Canadian Dollar", "🇨🇦", "Americas"),
    ("mxn", "Mex$", "Mexican Peso", "🇲🇽", "Americas"),
    ("brl", "R$", "Brazilian Real", "🇧🇷", "Americas"),
    ("ars", "$", "Argentine Peso", "🇦🇷", "Americas"),
    ("clp", "$", "Chilean Peso", "🇨🇱", "Americas"),
    ("cop", "$", "Colombian Peso", "🇨🇴", "Americas"),
    ("pen", "S/", "Peruvian Sol", "🇵🇪", "Americas"),
    ("uyu", "$U", "Uruguayan Peso", "🇺🇾", "Americas"),
    ("bob", "Bs", "Bolivian Boliviano", "🇧🇴", "Americas"),
    ("pyg", "₲", "Paraguayan Guarani", "🇵🇾", "Americas"),
    ("ves", "Bs", "Venezuelan Bolívar", "🇻🇪", "Americas"),
    ("gtq", "Q", "Guatemalan Quetzal", "🇬🇹", "Americas"),
    ("crc", "₡", "Costa Rican Colón", "🇨🇷", "Americas"),
    ("dop", "RD$", "Dominican Peso", "🇩🇴", "Americas"),
    ("hnl", "L", "Honduran Lempira", "🇭🇳", "Americas"),
    ("nio", "C$", "Nicaraguan Córdoba", "🇳🇮", "Americas"),
    ("pab", "B/.", "Panamanian Balboa", "🇵🇦", "Americas"),
    ("jmd", "J$", "Jamaican Dollar", "🇯🇲", "Americas"),
    ("ttd", "TT$", "Trinidad Dollar", "🇹🇹", "Americas"),
    ("bbd", "Bds$", "Barbadian Dollar", "🇧🇧", "Americas"),
    ("bsd", "B$", "Bahamian Dollar", "🇧🇸", "Americas"),
    ("bzd", "BZ$", "Belize Dollar", "🇧🇿", "Americas"),
    ("gyd", "G$", "Guyanese Dollar", "🇬🇾", "Americas"),
    ("srd", "$", "Surinamese Dollar", "🇸🇷", "Americas"),
    ("htg", "G", "Haitian Gourde", "🇭🇹", "Americas"),
    ("cup", "$", "Cuban Peso", "🇨🇺", "Americas"),
    # Asia-Pacific
    ("cny", "¥", "Chinese Yuan", "🇨🇳", "Asia"),
    ("jpy", "¥", "Japanese Yen", "🇯🇵", "Asia"),
    ("krw", "₩", "South Korean Won", "🇰🇷", "Asia"),
    ("inr", "₹", "Indian Rupee", "🇮🇳", "Asia"),
    ("idr", "Rp", "Indonesian Rupiah", "🇮🇩", "Asia"),
    ("thb", "฿", "Thai Baht", "🇹🇭", "Asia"),
    ("vnd", "₫", "Vietnamese Dong", "🇻🇳", "Asia"),
    ("myr", "RM", "Malaysian Ringgit", "🇲🇾", "Asia"),
    ("sgd", "S$", "Singapore Dollar", "🇸🇬", "Asia"),
    ("hkd", "HK$", "Hong Kong Dollar", "🇭🇰", "Asia"),
    ("twd", "NT$", "New Taiwan Dollar", "🇹🇼", "Asia"),
    ("php", "₱", "Philippine Peso", "🇵🇭", "Asia"),
    ("pkr", "₨", "Pakistani Rupee", "🇵🇰", "Asia"),
    ("bdt", "৳", "Bangladeshi Taka", "🇧🇩", "Asia"),
    ("lkr", "Rs", "Sri Lankan Rupee", "🇱🇰", "Asia"),
    ("npr", "Rs", "Nepalese Rupee", "🇳🇵", "Asia"),
    ("mmk", "K", "Myanmar Kyat", "🇲🇲", "Asia"),
    ("khr", "៛", "Cambodian Riel", "🇰🇭", "Asia"),
    ("lak", "₭", "Lao Kip", "🇱🇦", "Asia"),
    ("mnt", "₮", "Mongolian Tögrög", "🇲🇳", "Asia"),
    ("kpw", "₩", "North Korean Won", "🇰🇵", "Asia"),
    ("mvr", "Rf", "Maldivian Rufiyaa", "🇲🇻", "Asia"),
    ("btn", "Nu", "Bhutanese Ngultrum", "🇧🇹", "Asia"),
    ("afn", "؋", "Afghan Afghani", "🇦🇫", "Asia"),
    ("bnd", "B$", "Brunei Dollar", "🇧🇳", "Asia"),
    ("mop", "MOP$", "Macanese Pataca", "🇲🇴", "Asia"),
    # Middle East
    ("aed", "د.إ", "UAE Dirham", "🇦🇪", "Middle East"),
    ("sar", "﷼", "Saudi Riyal", "🇸🇦", "Middle East"),
    ("qar", "﷼", "Qatari Riyal", "🇶🇦", "Middle East"),
    ("kwd", "د.ك", "Kuwaiti Dinar", "🇰🇼", "Middle East"),
    ("bhd", ".د.ب", "Bahraini Dinar", "🇧🇭", "Middle East"),
    ("omr", "ر.ع.", "Omani Rial", "🇴🇲", "Middle East"),
    ("ils", "₪", "Israeli Shekel", "🇮🇱", "Middle East"),
    ("jod", "د.ا", "Jordanian Dinar", "🇯🇴", "Middle East"),
    ("lbp", "ل.ل", "Lebanese Pound", "🇱🇧", "Middle East"),
    ("iqd", "ع.د", "Iraqi Dinar", "🇮🇶", "Middle East"),
    ("irr", "﷼", "Iranian Rial", "🇮🇷", "Middle East"),
    ("yer", "﷼", "Yemeni Rial", "🇾🇪", "Middle East"),
    ("syp", "£", "Syrian Pound", "🇸🇾", "Middle East"),
    # Africa
    ("zar", "R", "South African Rand", "🇿🇦", "Africa"),
    ("egp", "E£", "Egyptian Pound", "🇪🇬", "Africa"),
    ("ngn", "₦", "Nigerian Naira", "🇳🇬", "Africa"),
    ("mad", "د.م.", "Moroccan Dirham", "🇲🇦", "Africa"),
    ("dzd", "د.ج", "Algerian Dinar", "🇩🇿", "Africa"),
    ("tnd", "د.ت", "Tunisian Dinar", "🇹🇳", "Africa"),
    ("lyd", "ل.د", "Libyan Dinar", "🇱🇾", "Africa"),
    ("ghs", "₵", "Ghanaian Cedi", "🇬🇭", "Africa"),
    ("kes", "KSh", "Kenyan Shilling", "🇰🇪", "Africa"),
    ("ugx", "USh", "Ugandan Shilling", "🇺🇬", "Africa"),
    ("tzs", "TSh", "Tanzanian Shilling", "🇹🇿", "Africa"),
    ("etb", "Br", "Ethiopian Birr", "🇪🇹", "Africa"),
    ("xof", "CFA", "West African CFA", "🇸🇳", "Africa"),
    ("xaf", "FCFA", "Central African CFA", "🇨🇲", "Africa"),
    ("cdf", "FC", "Congolese Franc", "🇨🇩", "Africa"),
    ("rwf", "FRw", "Rwandan Franc", "🇷🇼", "Africa"),
    ("mzn", "MT", "Mozambican Metical", "🇲🇿", "Africa"),
    ("aoa", "Kz", "Angolan Kwanza", "🇦🇴", "Africa"),
    ("zmw", "ZK", "Zambian Kwacha", "🇿🇲", "Africa"),
    ("mwk", "MK", "Malawian Kwacha", "🇲🇼", "Africa"),
    ("mur", "₨", "Mauritian Rupee", "🇲🇺", "Africa"),
    ("scr", "₨", "Seychellois Rupee", "🇸🇨", "Africa"),
    ("bwp", "P", "Botswana Pula", "🇧🇼", "Africa"),
    ("nad", "N$", "Namibian Dollar", "🇳🇦", "Africa"),
    ("szl", "E", "Swazi Lilangeni", "🇸🇿", "Africa"),
    ("lsl", "L", "Lesotho Loti", "🇱🇸", "Africa"),
    ("gmd", "D", "Gambian Dalasi", "🇬🇲", "Africa"),
    ("gnf", "FG", "Guinean Franc", "🇬🇳", "Africa"),
    ("sll", "Le", "Sierra Leonean Leone", "🇸🇱", "Africa"),
    ("lrd", "L$", "Liberian Dollar", "🇱🇷", "Africa"),
    ("sdg", "ج.س.", "Sudanese Pound", "🇸🇩", "Africa"),
    ("ssp", "£", "South Sudanese Pound", "🇸🇸", "Africa"),
    ("sos", "Sh", "Somali Shilling", "🇸🇴", "Africa"),
    ("djf", "Fdj", "Djiboutian Franc", "🇩🇯", "Africa"),
    ("kmf", "CF", "Comorian Franc", "🇰🇲", "Africa"),
    ("mga", "Ar", "Malagasy Ariary", "🇲🇬", "Africa"),
    ("cve", "$", "Cape Verdean Escudo", "🇨🇻", "Africa"),
    ("stn", "Db", "São Tomé Dobra", "🇸🇹", "Africa"),
    ("ern", "Nfk", "Eritrean Nakfa", "🇪🇷", "Africa"),
    # Oceania
    ("aud", "A$", "Australian Dollar", "🇦🇺", "Oceania"),
    ("nzd", "NZ$", "New Zealand Dollar", "🇳🇿", "Oceania"),
    ("fjd", "FJ$", "Fijian Dollar", "🇫🇯", "Oceania"),
    ("pgk", "K", "Papua New Guinean Kina", "🇵🇬", "Oceania"),
    ("wst", "WS$", "Samoan Tala", "🇼🇸", "Oceania"),
    ("top", "T$", "Tongan Paʻanga", "🇹🇴", "Oceania"),
    ("vuv", "VT", "Vanuatu Vatu", "🇻🇺", "Oceania"),
    ("sbd", "SI$", "Solomon Islands Dollar", "🇸🇧", "Oceania"),
    ("xpf", "₣", "CFP Franc", "🇵🇫", "Oceania"),
)

_CRYPTO: tuple[tuple[str, str, str, str, str], ...] = (
    ("ton", "TON", "Toncoin", "💎", "Crypto"),
    ("usdt", "USDT", "Tether USDT", "🪙", "Crypto"),
    ("stars", "⭐", "Telegram Stars", "⭐", "Crypto"),
)

# Deduplicate by code (keep first)
_seen: set[str] = set()
WORLD_CURRENCIES: tuple[tuple[str, str, str, str, str], ...] = tuple(
    row
    for row in (_CRYPTO + _WORLD_FIAT)
    if not (row[0] in _seen or _seen.add(row[0]))  # type: ignore[func-returns-value]
)

BALANCE_KEYS: tuple[str, ...] = tuple(c[0] for c in WORLD_CURRENCIES)

CURRENCY_BY_CODE: dict[str, tuple[str, str, str, str, str]] = {c[0]: c for c in WORLD_CURRENCIES}

# Группы для отображения баланса
_group_order = ("Crypto", "Europe", "CIS", "Americas", "Asia", "Middle East", "Africa", "Oceania")
_by_group: dict[str, list[str]] = {g: [] for g in _group_order}
for code, _sym, _name, _flag, group in WORLD_CURRENCIES:
    _by_group.setdefault(group, []).append(code)
BALANCE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    (g, tuple(keys)) for g, keys in _by_group.items() if keys
)

BALANCE_META: dict[str, dict] = {
    code: {
        "label": code.upper(),
        "symbol": sym,
        "name": name,
        "fallback": flag,
        "emoji_key": f"balance_{code}",
        "btn_icon": f"btn_pay_{code}",
        "integer": code == "stars",
        "group": group,
    }
    for code, sym, name, flag, group in WORLD_CURRENCIES
}

# Популярные методы оплаты в создании сделки (полный список — через поиск)
PAY_METHODS: tuple[tuple[str, str, str, str], ...] = (
    ("ton", "btn_pay_ton", "💎", "btn_pay_ton"),
    ("card", "btn_pay_card", "💳", "btn_pay_card"),
    ("stars", "btn_pay_stars", "⭐", "btn_pay_stars"),
    ("usdt", "btn_pay_usdt", "🪙", "btn_pay_usdt"),
    ("usd", "btn_pay_usd", "💸", "btn_pay_usd"),
    ("eur", "btn_pay_eur", "💰", "btn_pay_eur"),
    ("gbp", "btn_pay_gbp", "£", "btn_pay_gbp"),
    ("cny", "btn_pay_cny", "¥", "btn_pay_cny"),
    ("jpy", "btn_pay_jpy", "¥", "btn_pay_jpy"),
    ("try", "btn_pay_try", "₺", "btn_pay_try"),
    ("byn", "btn_pay_byn", "🇧🇾", "btn_pay_byn"),
    ("kzt", "btn_pay_kzt", "🇰🇿", "btn_pay_kzt"),
    ("uah", "btn_pay_uah", "🇺🇦", "btn_pay_uah"),
    ("aed", "btn_pay_aed", "🇦🇪", "btn_pay_aed"),
    ("inr", "btn_pay_inr", "₹", "btn_pay_inr"),
    ("brl", "btn_pay_brl", "R$", "btn_pay_brl"),
)

# pay_method сделки → ключ баланса
PAY_TO_BALANCE: dict[str, str] = {k: k for k in BALANCE_KEYS}
PAY_TO_BALANCE["card"] = "rub"
PAY_TO_BALANCE["rub"] = "rub"

# Реквизиты продавца при создании сделки
PAY_REQUISITE: dict[str, str] = {
    "ton": "ton",
    "usdt": "ton",
    "stars": "username",
}
for _code in BALANCE_KEYS:
    if _code not in PAY_REQUISITE:
        PAY_REQUISITE[_code] = "card"
PAY_REQUISITE["card"] = "card"

# Вывод: withdraw_callback → (balance_key, label, requisite: ton|card|username)
WITHDRAW_METHODS: dict[str, tuple[str, str, str]] = {
    "ton": ("ton", "TON", "ton"),
    "card": ("rub", "RUB", "card"),
    "stars": ("stars", "STARS", "username"),
    "usdt": ("usdt", "USDT", "ton"),
}
for _code, _sym, _name, _flag, _g in WORLD_CURRENCIES:
    if _code in ("ton", "usdt", "stars"):
        continue
    WITHDRAW_METHODS[_code] = (
        _code,
        _code.upper(),
        "card",
    )


def rows_of(items: list, n: int = 2) -> list[list]:
    """Упаковать кнопки по n в ряд."""
    return [items[i : i + n] for i in range(0, len(items), n)]


def balance_column(currency: str) -> str | None:
    """Имя колонки баланса или None."""
    if currency == "card":
        return "balance_rub"
    if currency in BALANCE_KEYS:
        return f"balance_{currency}"
    return None
