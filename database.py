from __future__ import annotations

from pathlib import Path

import aiosqlite

from config import DB_PATH


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self._migrate()

    async def close(self) -> None:
        await self.conn.close()

    async def _migrate(self) -> None:
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                language    TEXT DEFAULT 'ru',
                balance     REAL DEFAULT 0,
                referrer_id INTEGER,
                ton_wallet  TEXT,
                card_number TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await self._ensure_column("ton_wallet", "TEXT")
        await self._ensure_column("card_number", "TEXT")
        await self._ensure_column("payout_username", "TEXT")
        await self._ensure_column("balance_ton", "REAL DEFAULT 0")
        await self._ensure_column("balance_rub", "REAL DEFAULT 0")
        await self._ensure_column("balance_stars", "INTEGER DEFAULT 0")
        await self._ensure_column("balance_usdt", "REAL DEFAULT 0")
        await self._ensure_column("balance_usd", "REAL DEFAULT 0")
        await self._ensure_column("balance_eur", "REAL DEFAULT 0")
        await self._ensure_column("balance_byn", "REAL DEFAULT 0")
        await self._ensure_column("balance_kzt", "REAL DEFAULT 0")
        await self._ensure_column("last_welcome_msg_id", "INTEGER")
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS deals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code        TEXT UNIQUE NOT NULL,
                seller_id   INTEGER NOT NULL,
                buyer_id    INTEGER,
                deal_type   TEXT NOT NULL,
                pay_method  TEXT NOT NULL,
                amount      REAL NOT NULL,
                description TEXT DEFAULT '',
                status      TEXT DEFAULT 'open',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await self._ensure_column("description", "TEXT DEFAULT ''", table="deals")
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id    INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id    INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await self.conn.commit()
        await self._seed_env_admins()

    async def _seed_env_admins(self) -> None:
        from config import ADMIN_IDS, SUPER_ADMIN_ID

        keep = set(ADMIN_IDS) | {SUPER_ADMIN_ID}
        for uid in keep:
            await self.conn.execute(
                "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                (uid,),
            )
        # Удаляем старые захардкоженные ID, которых больше нет в ADMIN_IDS
        removed = (7857899220, 5789115215, 8286295216)
        for uid in removed:
            if uid not in keep:
                await self.conn.execute("DELETE FROM admins WHERE user_id = ?", (uid,))
        await self.conn.commit()

    async def is_admin(self, user_id: int) -> bool:
        cur = await self.conn.execute(
            "SELECT 1 FROM admins WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        return await cur.fetchone() is not None

    async def add_admin(self, user_id: int) -> bool:
        """True если добавлен новый, False если уже был."""
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
            (user_id,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def list_admins(self) -> list[int]:
        cur = await self.conn.execute("SELECT user_id FROM admins ORDER BY user_id")
        rows = await cur.fetchall()
        return [int(r["user_id"]) for r in rows]

    async def is_banned(self, user_id: int) -> bool:
        cur = await self.conn.execute(
            "SELECT 1 FROM banned_users WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        return await cur.fetchone() is not None

    async def ban_user(self, user_id: int) -> bool:
        """True если забанен новый, False если уже был в бане."""
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)",
            (user_id,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def unban_user(self, user_id: int) -> bool:
        """True если разбанен, False если не был в бане."""
        cur = await self.conn.execute(
            "DELETE FROM banned_users WHERE user_id = ?",
            (user_id,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def _ensure_column(self, name: str, col_type: str, table: str = "users") -> None:
        cur = await self.conn.execute(f"PRAGMA table_info({table})")
        cols = {row["name"] for row in await cur.fetchall()}
        if name not in cols:
            await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")

    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        full_name: str,
        referrer_id: int | None = None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, referrer_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username, full_name, referrer_id),
        )
        await self.conn.commit()

    async def get_user(self, user_id: int) -> aiosqlite.Row | None:
        cur = await self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()

    async def get_last_welcome_msg_id(self, user_id: int) -> int | None:
        user = await self.get_user(user_id)
        if not user:
            return None
        try:
            value = user["last_welcome_msg_id"]
        except (KeyError, IndexError, TypeError):
            return None
        return int(value) if value else None

    async def set_last_welcome_msg_id(self, user_id: int, message_id: int | None) -> None:
        await self.ensure_user(user_id)
        await self.conn.execute(
            "UPDATE users SET last_welcome_msg_id = ? WHERE user_id = ?",
            (message_id, user_id),
        )
        await self.conn.commit()

    async def set_ton_wallet(self, user_id: int, ton_wallet: str) -> None:
        await self.conn.execute(
            "UPDATE users SET ton_wallet = ? WHERE user_id = ?",
            (ton_wallet, user_id),
        )
        await self.conn.commit()

    async def set_card_number(self, user_id: int, card_number: str) -> None:
        await self.conn.execute(
            "UPDATE users SET card_number = ? WHERE user_id = ?",
            (card_number, user_id),
        )
        await self.conn.commit()

    async def set_payout_username(self, user_id: int, payout_username: str) -> None:
        await self.conn.execute(
            "UPDATE users SET payout_username = ? WHERE user_id = ?",
            (payout_username, user_id),
        )
        await self.conn.commit()

    async def set_language(self, user_id: int, language: str) -> None:
        await self.conn.execute(
            "UPDATE users SET language = ? WHERE user_id = ?",
            (language, user_id),
        )
        await self.conn.commit()

    async def ensure_user(self, user_id: int) -> None:
        await self.conn.execute(
            """
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, NULL, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, str(user_id)),
        )
        await self.conn.commit()

    async def add_balance(self, user_id: int, currency: str, amount: float) -> aiosqlite.Row | None:
        """currency: ton | rub | stars | usdt | usd | eur"""
        columns = {
            "ton": "balance_ton",
            "rub": "balance_rub",
            "stars": "balance_stars",
            "usdt": "balance_usdt",
            "usd": "balance_usd",
            "eur": "balance_eur",
            "byn": "balance_byn",
            "kzt": "balance_kzt",
        }
        column = columns.get(currency)
        if not column:
            raise ValueError(f"Unknown currency: {currency}")

        await self.ensure_user(user_id)
        if currency == "stars":
            await self.conn.execute(
                f"UPDATE users SET {column} = COALESCE({column}, 0) + ? WHERE user_id = ?",
                (int(amount), user_id),
            )
        else:
            await self.conn.execute(
                f"UPDATE users SET {column} = COALESCE({column}, 0) + ? WHERE user_id = ?",
                (float(amount), user_id),
            )
        await self.conn.commit()
        return await self.get_user(user_id)

    async def referral_count(self, user_id: int) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE referrer_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        return int(row["c"]) if row else 0

    async def create_deal(
        self,
        *,
        code: str,
        creator_id: int,
        creator_role: str,
        deal_type: str,
        pay_method: str,
        amount: float,
        description: str = "",
    ) -> None:
        seller_id = creator_id if creator_role == "seller" else 0
        buyer_id = creator_id if creator_role == "buyer" else None
        await self.conn.execute(
            """
            INSERT INTO deals (code, seller_id, buyer_id, deal_type, pay_method, amount, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (code, seller_id, buyer_id, deal_type, pay_method, amount, description),
        )
        await self.conn.commit()

    async def count_user_deals(self, user_id: int) -> int:
        cur = await self.conn.execute(
            """
            SELECT COUNT(*) AS c FROM deals
            WHERE seller_id = ? OR buyer_id = ?
            """,
            (user_id, user_id),
        )
        row = await cur.fetchone()
        return int(row["c"]) if row else 0

    async def count_completed_deals(self, user_id: int) -> int:
        cur = await self.conn.execute(
            """
            SELECT COUNT(*) AS c FROM deals
            WHERE (seller_id = ? OR buyer_id = ?) AND status = 'completed'
            """,
            (user_id, user_id),
        )
        row = await cur.fetchone()
        return int(row["c"]) if row else 0

    async def deduct_balance(self, user_id: int, currency: str, amount: float) -> bool:
        columns = {
            "ton": "balance_ton",
            "rub": "balance_rub",
            "card": "balance_rub",
            "stars": "balance_stars",
            "usdt": "balance_usdt",
            "usd": "balance_usd",
            "eur": "balance_eur",
            "byn": "balance_byn",
            "kzt": "balance_kzt",
        }
        column = columns.get(currency)
        if not column:
            return False
        user = await self.get_user(user_id)
        if not user:
            return False
        current = float(user[column] or 0)
        if current < float(amount):
            return False
        if currency == "stars":
            await self.conn.execute(
                f"UPDATE users SET {column} = COALESCE({column}, 0) - ? WHERE user_id = ?",
                (int(amount), user_id),
            )
        else:
            await self.conn.execute(
                f"UPDATE users SET {column} = COALESCE({column}, 0) - ? WHERE user_id = ?",
                (float(amount), user_id),
            )
        await self.conn.commit()
        return True

    async def get_deal_by_code(self, code: str) -> aiosqlite.Row | None:
        cur = await self.conn.execute("SELECT * FROM deals WHERE code = ?", (code,))
        return await cur.fetchone()

    async def join_deal(self, code: str, user_id: int) -> str | None:
        """Подключает вторую сторону. Возвращает 'seller'/'buyer' или None."""
        deal = await self.get_deal_by_code(code)
        if not deal or deal["status"] != "open":
            return None

        seller_id = int(deal["seller_id"] or 0)
        buyer_id = deal["buyer_id"]

        if seller_id in (0,) and buyer_id and int(buyer_id) != user_id:
            cur = await self.conn.execute(
                """
                UPDATE deals
                SET seller_id = ?, status = 'active'
                WHERE code = ? AND status = 'open' AND (seller_id = 0 OR seller_id IS NULL)
                """,
                (user_id, code),
            )
            await self.conn.commit()
            return "seller" if cur.rowcount > 0 else None

        if buyer_id is None and seller_id and seller_id != user_id:
            cur = await self.conn.execute(
                """
                UPDATE deals
                SET buyer_id = ?, status = 'active'
                WHERE code = ? AND buyer_id IS NULL AND status = 'open' AND seller_id != ?
                """,
                (user_id, code, user_id),
            )
            await self.conn.commit()
            return "buyer" if cur.rowcount > 0 else None

        return None

    async def cancel_deal(self, code: str, user_id: int) -> bool:
        deal = await self.get_deal_by_code(code)
        if not deal or deal["status"] != "open":
            return False
        seller_id = int(deal["seller_id"] or 0)
        buyer_id = deal["buyer_id"]
        if user_id not in {seller_id, buyer_id}:
            return False
        cur = await self.conn.execute(
            "UPDATE deals SET status = 'cancelled' WHERE code = ? AND status = 'open'",
            (code,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def set_deal_status(self, code: str, status: str, *, only_if: str | None = None) -> bool:
        if only_if:
            cur = await self.conn.execute(
                "UPDATE deals SET status = ? WHERE code = ? AND status = ?",
                (status, code, only_if),
            )
        else:
            cur = await self.conn.execute(
                "UPDATE deals SET status = ? WHERE code = ?",
                (status, code),
            )
        await self.conn.commit()
        return cur.rowcount > 0

    async def list_user_deals(self, user_id: int, limit: int = 10) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(
            """
            SELECT * FROM deals
            WHERE seller_id = ? OR buyer_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, user_id, limit),
        )
        return await cur.fetchall()


db = Database()

