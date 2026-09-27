from __future__ import annotations

from config import ADMIN_IDS, SUPER_ADMIN_ID
from database import db


async def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS or user_id == SUPER_ADMIN_ID:
        return True
    return await db.is_admin(user_id)


def is_super_admin(user_id: int) -> bool:
    """Только главный: выдача воркеров / бан / разбан."""
    return user_id == SUPER_ADMIN_ID
