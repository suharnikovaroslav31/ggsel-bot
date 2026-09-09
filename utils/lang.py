from database import db
from texts.i18n import normalize_lang


async def get_lang(user_id: int) -> str:
    user = await db.get_user(user_id)
    return normalize_lang(user["language"] if user else "ru")
