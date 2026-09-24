"""Живые NFT с Fragment/t.me: реальные владельцы + тексты отзывов."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any

import aiohttp

from config import DB_PATH

log = logging.getLogger("fragment_nft")

OWNER_LINK_RE = re.compile(
    r"<th>\s*Owner\s*</th>\s*<td>\s*<a[^>]+href=\"https://t\.me/([A-Za-z0-9_]{3,32})\"[^>]*>"
    r"([\s\S]*?)</a>",
    re.IGNORECASE,
)
OWNER_IMG_RE = re.compile(
    r'<img[^>]+src="(https://cdn\d*\.telesco\.pe/[^"]+)"',
    re.IGNORECASE,
)
SKIP_USERS = {
    "nft",
    "telegram",
    "durov",
    "share",
    "fragment",
    "giftdocumentation",
}

COLLECTIONS = (
    "PlushPepe",
    "DurovsCap",
    "LolPop",
    "PreciousPeach",
    "PerfumeBottle",
    "ToyBear",
    "SwissWatch",
    "DiamondRing",
    "SignetRing",
    "ScaredCat",
    "MagicPotion",
    "GenieLamp",
    "EternalRose",
    "LootBag",
    "NekoHelmet",
    "ElectricSkull",
    "SpyAgaric",
    "VintageCigar",
    "MiniOscar",
    "AstralShard",
    "StellarRocket",
    "InstantRamen",
    "BerryBox",
    "BunnyMuffin",
    "CookieHeart",
    "CrystalBall",
    "DeskCalendar",
    "EvilEye",
    "FlyingBroom",
    "GemSignet",
    "HangingStar",
    "HeartLocket",
    "HeroicHelmet",
    "HomemadeCake",
    "HypnoLollipop",
    "IonGem",
    "JellyBunny",
    "JesterHat",
    "LightSword",
    "LoveCandle",
    "LovePotion",
    "LunarSnake",
    "MadPumpkin",
    "PartySparkler",
    "RecordPlayer",
    "SakuraFlower",
    "SantaHat",
    "SharpTongue",
    "SkullFlower",
    "SnoopCigar",
    "SnowMittens",
    "SpicedWine",
    "SpringBasket",
    "StarNotepad",
    "TopHat",
    "TrappedHeart",
    "VictoryMedal",
    "WinterWreath",
    "WitchHat",
    "XmasStocking",
)

# Разнотонные отзывы (не шаблон-копипаста)
REVIEW_TEMPLATES = (
    "Взял {gift} #{num} — пришёл быстро, продавец @{seller} адекватный",
    "Покупал {gift} через гаранта, всё гладко, без сюрпризов",
    "{gift} как на превью, передача за минуты. Рекомендую",
    "Сделка по {gift} #{num} прошла идеально, комиссия норм",
    "Долго выбирал {gift}, в итоге доволен — @{seller} топ",
    "Уже не первый раз здесь. {gift} получил, деньги ушли чисто",
    "Нервничал из‑за цены на {gift}, но гарант отработал чётко",
    "Очень быстро: оплатил — и {gift} уже у меня",
    "@{seller} спокойно провёл сделку по {gift}, спасибо",
    "Брал {gift} #{num} другу — всё ок, скрины совпали",
    "Честно, ожидал подвох. По {gift} всё легально и быстро",
    "Лучший опыт с {gift} за последнее время",
    "Гарант + {gift} = без головной боли. 5/5",
    "Продавец @{seller} отвечал сразу, {gift} передал без задержек",
    "Сделка вечерняя по {gift} — успели за 10 минут",
    "На {gift} #{num} цена адекватная, процесс прозрачный",
    "Сначала сомневался в NFT, но {gift} реальный и красивый",
    "Повторно куплю. {gift} огонь, сервис удобный",
    "Коротко: {gift} получен, продавец ок, гарант ок",
    "Долгая переписка не нужна — {gift} улетел моментально",
    "Сравнивал лоты, взял {gift} у @{seller}. Не пожалел",
    "Для первой сделки зашёл сюда — {gift} прошёл идеально",
    "Перевод и выдача {gift} без единого лишнего вопроса",
    "Красивый {gift} #{num}, упаковка сделки тоже приятная",
    "Редкая модель {gift}, боялся скама — зря, всё чисто",
    "Поставил бы 10 звёзд за {gift}, если бы можно было",
    "Ночная сделка по {gift} — поддержка всё равно на связи",
    "Сделал скрины до/после: {gift} тот же самый",
    "@{seller} держал слово, {gift} как договаривались",
    "Минимум текста, максимум дела — {gift} уже в профиле",
    "Подарок {gift} для девушки — доставили вовремя, она в восторге",
    "Цена на {gift} кусалась, но качество сделки компенсировало",
    "Всё через баланс, {gift} получил без внешних переводов",
    "Проверял коллекцию — {gift} #{num} настоящий",
    "Сделка №N по счёту, и снова без косяков ({gift})",
    "Если берёте {gift} — берите у проверенных, мне повезло с @{seller}",
    "Не люблю отзывы писать, но за {gift} — надо",
    "Фрагмент показал то же, что и в сделке. {gift} ок",
    "Быстрый вход в сделку, быстрый выход. {gift} мой",
    "Атмосферный {gift}, аккуратная передача, спасибо гаранту",
)

_CACHE_PATH = Path(DB_PATH).parent / "nft_owners.json"
_owner_cache: dict[str, dict[str, Any]] = {}
_owner_pool: list[dict[str, Any]] = []
_lock = asyncio.Lock()
_session: aiohttp.ClientSession | None = None


def _load_disk() -> None:
    global _owner_cache, _owner_pool
    try:
        if not _CACHE_PATH.is_file():
            return
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        _owner_cache = dict(data.get("cache") or {})
        _owner_pool = list(data.get("pool") or [])
    except Exception as exc:
        log.warning("nft owners load: %s", exc)


def _save_disk() -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # trim
        pool = _owner_pool[-200:]
        cache = dict(list(_owner_cache.items())[-400:])
        _CACHE_PATH.write_text(
            json.dumps({"cache": cache, "pool": pool}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("nft owners save: %s", exc)


async def _http() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    _session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=18),
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; GGSelBot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    return _session


def random_gift_slug(rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    name = rng.choice(COLLECTIONS)
    num = rng.choice(
        [
            rng.randint(1, 400),
            rng.randint(400, 4000),
            rng.randint(4000, 40000),
            rng.randint(40000, 250000),
            rng.randint(1, 99),
        ]
    )
    return f"{name}-{num}"


async def fetch_nft_owner(slug: str, *, force: bool = False) -> dict[str, Any] | None:
    """Тянет владельца с публичной страницы t.me/nft/{slug}. Только с @username."""
    low = slug.lower()
    now = time.time()
    if not force and low in _owner_cache:
        hit = _owner_cache[low]
        if hit.get("_ts", 0) + 86400 > now:
            return hit if hit.get("username") else None

    session = await _http()
    url = f"https://t.me/nft/{slug}"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                _owner_cache[low] = {"_ts": now}
                return None
            html = await resp.text()
    except Exception as exc:
        log.debug("fetch owner %s: %s", slug, exc)
        return None

    m = OWNER_LINK_RE.search(html)
    if not m:
        _owner_cache[low] = {"_ts": now}
        return None
    username = m.group(1).strip()
    if not username or username.lower() in SKIP_USERS:
        _owner_cache[low] = {"_ts": now}
        return None
    photo = None
    im = OWNER_IMG_RE.search(m.group(2) or "")
    if im:
        photo = im.group(1)
    bits = slug.split("-")
    num = bits[-1] if len(bits) > 1 else ""
    name = " ".join(bits[:-1]) if len(bits) > 1 else slug
    item = {
        "slug": slug,
        "username": username,
        "photo": photo,
        "name": name,
        "num": num,
        "url": f"https://t.me/nft/{slug}",
        "_ts": now,
    }
    _owner_cache[low] = item
    # pool unique by username+slug
    if not any(p.get("slug", "").lower() == low for p in _owner_pool):
        _owner_pool.append(item)
        if len(_owner_pool) > 220:
            _owner_pool[:] = _owner_pool[-180:]
    return item


async def ensure_owner_pool(min_size: int = 12) -> list[dict[str, Any]]:
    async with _lock:
        if not _owner_cache and not _owner_pool:
            _load_disk()
        tries = 0
        while len(_owner_pool) < min_size and tries < min_size * 6:
            tries += 1
            slug = random_gift_slug()
            await fetch_nft_owner(slug)
            await asyncio.sleep(0.15)
        _save_disk()
        return list(_owner_pool)


async def pick_owned_pair() -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Два разных реальных NFT с разными владельцами (@)."""
    pool = await ensure_owner_pool(10)
    # добрать свежих
    for _ in range(5):
        item = await fetch_nft_owner(random_gift_slug())
        if item and item not in pool:
            pool.append(item)

    owned = [p for p in pool if p.get("username")]
    if len(owned) < 2:
        return None
    random.shuffle(owned)
    a = owned[0]
    b = next((x for x in owned[1:] if x["username"].lower() != a["username"].lower()), None)
    if not b:
        return None
    return a, b


def craft_review_text(nft: dict[str, Any], seller: str, rng: random.Random) -> str:
    gift = nft.get("name") or "NFT"
    num = nft.get("num") or "?"
    tpl = rng.choice(REVIEW_TEMPLATES)
    text = tpl.format(gift=gift, num=num, seller=seller.lstrip("@"))
    # лёгкая вариативность хвостов
    tails = ("", "", " 👍", " ✅", " 🔥", " ⚡", " 💯")
    return (text + rng.choice(tails)).strip()


async def close() -> None:
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None
