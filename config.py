import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
# На Bothost и подобных хостингах данные кладут в DATA_DIR=/app/data
_data_dir = os.getenv("DATA_DIR", "").strip()
DB_PATH = Path(_data_dir) / "bot.db" if _data_dir else BASE_DIR / "data" / "bot.db"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
# Локальный VPN/Clash/V2Ray proxy (если пусто — прямое подключение)
PROXY_URL = os.getenv("PROXY_URL", "").strip()
_DEFAULT_OWNER = "8129409474"
# Воркеры из env (главный админ сюда не входит)
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
# Главный админ: выдача воркеров / бан / разбан
_raw_super = os.getenv("SUPER_ADMIN_ID", _DEFAULT_OWNER).strip()
SUPER_ADMIN_ID = int(_raw_super) if _raw_super.isdigit() else int(_DEFAULT_OWNER)
ADMIN_IDS.discard(SUPER_ADMIN_ID)

MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "GGsel_deal").strip().lstrip("@")
# Кнопка «Техподдержка» ведёт на гаранта, если SUPPORT_URL не задан отдельно
SUPPORT_URL = os.getenv("SUPPORT_URL", "").strip() or f"https://t.me/{MANAGER_USERNAME}"
MIN_COMPLETED_DEALS_WITHDRAW = int(os.getenv("MIN_COMPLETED_DEALS_WITHDRAW", "3") or "3")

# Панель Ural Team: куда слать события сделок (домен бота панели на Bothost).
# Пусто — отправка выключена, бот работает как раньше.
PANEL_API_URL = os.getenv("PANEL_API_URL", "").strip()
PANEL_API_SECRET = os.getenv("PANEL_API_SECRET", "").strip()

# Custom emoji IDs — заполни через пересылку сообщения боту (/emoji_ids).
# Пока пусто: в тексте будут обычные эмодзи-фолбэки.
CUSTOM_EMOJI = {
    "coffee": "5893255507380014983",
    "construction": "5395732581780040886",
    "lightning": "5456140674028019486",
    "one": "5794164805065514131",
    "two": "5794085322400733645",
    "shield": "5902016123972358349",
    "three": "5794280000383358988",
    "trident": "6039802097916974085",
    "four": "5794241397217304511",
    "handshake": "5778672437122045013",
    "requisites_doc": "6034969813032374911",
    "balance_card": "5902056028513505203",
    "balance_ton": "5235630047959727475",
    "balance_rub": "5409048419211682843",
    "balance_stars": "5463289097336405244",
    "balance_usdt": "5778613750688911681",
    "balance_usd": "5233326571099534068",
    "balance_eur": "5778421276024509124",
    "balance_byn": "5879814368572478751",
    "balance_kzt": "5904462880941545555",
    "balance_uah": "",
    "btn_requisites": "5893255507380014983",
    "btn_create": "5361847815255372871",
    "btn_balance": "6039641775377748623",
    "btn_deals": "6034969813032374911",
    "btn_refs": "5447410659077661506",
    "btn_lang": "5447410659077661506",
    "btn_support": "5443038326535759644",
    "btn_ton": "5235630047959727475",
    "btn_card": "5902056028513505203",
    "btn_back": "5895507195524550741",
    "btn_back_alt": "5375338737028841420",
    "btn_cancel": "5210952531676504517",
    "btn_deal_gift": "5203996991054432397",
    "btn_deal_channel": "5424818078833715060",
    "btn_deal_stars": "5463289097336405244",
    "btn_deal_nft": "5271604874419647061",
    "btn_pay_ton": "5235630047959727475",
    "btn_pay_card": "5902056028513505203",
    "btn_pay_stars": "5463289097336405244",
    "btn_pay_usdt": "5778613750688911681",
    "btn_pay_usd": "5233326571099534068",
    "btn_pay_eur": "5778421276024509124",
    "btn_pay_byn": "5879814368572478751",
    "btn_pay_kzt": "5904462880941545555",
    "btn_pay_uah": "",
    "btn_pay_rub": "5409048419211682843",
    # Сообщение продавцу в сделке (можно заменить через /emoji_ids)
    "deal_check": "5206607081334906820",
    "deal_buyers": "6032609071373226027",
    "deal_thought": "5467538555158943525",
    "deal_chart": "5244837092042750681",
    "deal_memo": "5778299625370817409",
    "deal_star": "5463289097336405244",
    "deal_excl": "5274099962655816924",
    "deal_card": "5902056028513505203",
    "deal_shield": "5902016123972358349",
    "deal_chat": "5443038326535759644",
    "deal_bell": "5458603043203327669",
    "deal_person": "6032949275732742941",
    "deal_money": "5893473283696759404",
    "deal_sparkle": "5325547803936572038",
    "btn_deal_sent": "5778672437122045013",
    "btn_deal_recv": "5206607081334906820",
    "deal_cart": "5778672437122045013",
    "deal_pen": "5395444784611480792",
    "deal_link": "5271604874419647061",
    "btn_role_seller": "5893255507380014983",
    "btn_role_buyer": "5778672437122045013",
}
