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
        from utils.currencies import BALANCE_KEYS, BALANCE_META

        for key in BALANCE_KEYS:
            col = f"balance_{key}"
            if BALANCE_META.get(key, {}).get("integer"):
                await self._ensure_column(col, "INTEGER DEFAULT 0")
            else:
                await self._ensure_column(col, "REAL DEFAULT 0")
        await self._ensure_column("last_welcome_msg_id", "INTEGER")
        await self._ensure_column("lang_picked", "INTEGER DEFAULT 0")
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
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bot_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT NOT NULL,
                rating      INTEGER NOT NULL DEFAULT 5,
                body        TEXT NOT NULL,
                review_date TEXT DEFAULT '',
                sort_order  INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await self._ensure_column("nft_url", "TEXT DEFAULT ''", table="reviews")
        await self._ensure_column("deal_code", "TEXT DEFAULT ''", table="reviews")
        await self._ensure_column("seller_username", "TEXT DEFAULT ''", table="reviews")
        await self._ensure_column("buyer_username", "TEXT DEFAULT ''", table="reviews")
        await self._ensure_column("seller_id", "INTEGER", table="reviews")
        await self._ensure_column("buyer_id", "INTEGER", table="reviews")
        await self._ensure_column("author_role", "TEXT DEFAULT 'buyer'", table="reviews")
        await self._ensure_column("amount", "REAL DEFAULT 0", table="reviews")
        await self._ensure_column("pay_method", "TEXT DEFAULT ''", table="reviews")
        await self._ensure_column("deal_type", "TEXT DEFAULT 'gift'", table="reviews")
        await self.conn.commit()
        await self._seed_env_admins()
        await self._purge_demo_reviews()

    async def _seed_env_admins(self) -> None:
        from config import ADMIN_IDS, SUPER_ADMIN_ID

        # Разово снести всех старых воркеров после смены аккаунтов.
        # Новых, выданных через панель, это больше не трогает.
        cur = await self.conn.execute(
            "SELECT 1 FROM bot_meta WHERE key = ? LIMIT 1",
            ("purge_workers_rebind_20260919",),
        )
        if await cur.fetchone() is None:
            await self.conn.execute("DELETE FROM admins")
            await self.conn.execute(
                "INSERT INTO bot_meta (key, value) VALUES (?, ?)",
                ("purge_workers_rebind_20260919", "1"),
            )

        # Разово разбанить всех и пересадить владельца на новый ID.
        cur = await self.conn.execute(
            "SELECT 1 FROM bot_meta WHERE key = ? LIMIT 1",
            ("purge_bans_owner_8608272141_v2",),
        )
        if await cur.fetchone() is None:
            await self.conn.execute("DELETE FROM banned_users")
            await self.conn.execute(
                "DELETE FROM admins WHERE user_id IN (?, ?)",
                (8058806494, SUPER_ADMIN_ID),
            )
            await self.conn.execute(
                "INSERT INTO bot_meta (key, value) VALUES (?, ?)",
                ("purge_bans_owner_8608272141_v2", "1"),
            )

        # Владельца никогда не держим в бане.
        await self.conn.execute(
            "DELETE FROM banned_users WHERE user_id = ?",
            (SUPER_ADMIN_ID,),
        )

        extra = set(ADMIN_IDS) - {SUPER_ADMIN_ID}
        for uid in extra:
            await self.conn.execute(
                "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                (uid,),
            )
        # Главный админ — не воркер
        await self.conn.execute(
            "DELETE FROM admins WHERE user_id = ?",
            (SUPER_ADMIN_ID,),
        )
        await self.conn.commit()

    async def is_admin(self, user_id: int) -> bool:
        cur = await self.conn.execute(
            "SELECT 1 FROM admins WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        return await cur.fetchone() is not None

    async def add_admin(self, user_id: int) -> bool:
        """True если добавлен новый, False если уже был."""
        from config import SUPER_ADMIN_ID

        if user_id == SUPER_ADMIN_ID:
            return False
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
            (user_id,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def list_admins(self) -> list[int]:
        from config import SUPER_ADMIN_ID

        cur = await self.conn.execute("SELECT user_id FROM admins ORDER BY user_id")
        rows = await cur.fetchall()
        return [int(r["user_id"]) for r in rows if int(r["user_id"]) != SUPER_ADMIN_ID]

    async def is_banned(self, user_id: int) -> bool:
        from config import SUPER_ADMIN_ID

        if int(user_id) == SUPER_ADMIN_ID:
            return False
        cur = await self.conn.execute(
            "SELECT 1 FROM banned_users WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        return await cur.fetchone() is not None

    async def ban_user(self, user_id: int) -> bool:
        """True если забанен новый, False если уже был в бане."""
        from config import SUPER_ADMIN_ID

        if int(user_id) == SUPER_ADMIN_ID:
            await self.conn.execute(
                "DELETE FROM banned_users WHERE user_id = ?",
                (user_id,),
            )
            await self.conn.commit()
            return False
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

    async def find_user_by_username(self, username: str) -> aiosqlite.Row | None:
        uname = str(username or "").strip().lstrip("@").lower()
        if not uname:
            return None
        cur = await self.conn.execute(
            "SELECT * FROM users WHERE lower(username) = ? LIMIT 1",
            (uname,),
        )
        return await cur.fetchone()

    async def ensure_named_user(self, username: str, *, prefer_id: int | None = None) -> int:
        """Находит юзера по @username или создаёт «теневой» аккаунт (отрицательный id)."""
        uname = str(username or "").strip().lstrip("@")
        if prefer_id:
            await self.ensure_user(prefer_id)
            row = await self.get_user(prefer_id)
            if row and not (row["username"] or "").strip() and uname:
                await self.conn.execute(
                    "UPDATE users SET username = ? WHERE user_id = ?",
                    (uname, prefer_id),
                )
                await self.conn.commit()
            return int(prefer_id)
        if uname:
            found = await self.find_user_by_username(uname)
            if found:
                return int(found["user_id"])
        cur = await self.conn.execute(
            "SELECT COALESCE(MIN(user_id), 0) AS m FROM users WHERE user_id < 0"
        )
        row = await cur.fetchone()
        next_id = int(row["m"] or 0) - 1 if row and int(row["m"] or 0) < 0 else -1
        await self.conn.execute(
            """
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            """,
            (next_id, uname or None, uname or str(next_id)),
        )
        await self.conn.commit()
        return next_id

    async def create_completed_deal(
        self,
        *,
        code: str,
        seller_id: int,
        buyer_id: int,
        deal_type: str,
        pay_method: str,
        amount: float,
        description: str = "",
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO deals (code, seller_id, buyer_id, deal_type, pay_method, amount, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
            """,
            (code, seller_id, buyer_id, deal_type, pay_method, amount, description),
        )
        await self.conn.commit()

    async def list_user_completed_deals(self, user_id: int, limit: int = 20) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(
            """
            SELECT * FROM deals
            WHERE (seller_id = ? OR buyer_id = ?) AND status = 'completed'
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, user_id, limit),
        )
        return await cur.fetchall()

    async def list_user_reviews(self, user_id: int, username: str = "", limit: int = 30) -> list[aiosqlite.Row]:
        uname = str(username or "").strip().lstrip("@").lower()
        # Только по нику (витрина без аккаунта) — не матчим seller_id=0
        if uname and not user_id:
            cur = await self.conn.execute(
                """
                SELECT * FROM reviews
                WHERE lower(seller_username) = ?
                   OR lower(buyer_username) = ?
                   OR lower(username) = ?
                ORDER BY sort_order ASC, id DESC
                LIMIT ?
                """,
                (uname, uname, uname, limit),
            )
        elif uname:
            cur = await self.conn.execute(
                """
                SELECT * FROM reviews
                WHERE seller_id = ? OR buyer_id = ?
                   OR lower(seller_username) = ?
                   OR lower(buyer_username) = ?
                   OR lower(username) = ?
                ORDER BY sort_order ASC, id DESC
                LIMIT ?
                """,
                (user_id, user_id, uname, uname, uname, limit),
            )
        else:
            cur = await self.conn.execute(
                """
                SELECT * FROM reviews
                WHERE seller_id = ? OR buyer_id = ?
                ORDER BY sort_order ASC, id DESC
                LIMIT ?
                """,
                (user_id, user_id, limit),
            )
        return await cur.fetchall()

    async def user_rating(self, user_id: int, username: str = "") -> tuple[float, int]:
        rows = await self.list_user_reviews(user_id, username, limit=200)
        if not rows:
            return 0.0, 0
        total = sum(int(r["rating"] or 5) for r in rows)
        return round(total / len(rows), 1), len(rows)

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
        try:
            await self.conn.execute(
                "UPDATE users SET language = ?, lang_picked = 1 WHERE user_id = ?",
                (language, user_id),
            )
            await self.conn.commit()
        except Exception:
            await self.conn.execute(
                "UPDATE users SET language = ? WHERE user_id = ?",
                (language, user_id),
            )
            await self.conn.commit()
            try:
                await self._ensure_column("lang_picked", "INTEGER DEFAULT 0")
                await self.conn.execute(
                    "UPDATE users SET lang_picked = 1 WHERE user_id = ?",
                    (user_id,),
                )
                await self.conn.commit()
            except Exception:
                pass

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
        """currency: любой ключ из BALANCE_KEYS или card→rub."""
        from utils.currencies import BALANCE_META, balance_column

        column = balance_column(currency)
        if not column:
            raise ValueError(f"Unknown currency: {currency}")

        await self.ensure_user(user_id)
        key = "rub" if currency == "card" else currency
        if BALANCE_META.get(key, {}).get("integer"):
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
        from utils.currencies import BALANCE_META, balance_column

        column = balance_column(currency)
        if not column:
            return False
        user = await self.get_user(user_id)
        if not user:
            return False
        try:
            current = float(user[column] or 0)
        except (KeyError, IndexError, TypeError):
            current = 0.0
        if current < float(amount):
            return False
        key = "rub" if currency == "card" else currency
        if BALANCE_META.get(key, {}).get("integer"):
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

    async def list_completed_feed(self, limit: int = 12) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(
            """
            SELECT code, deal_type, pay_method, amount, description, status, created_at
            FROM deals
            WHERE status = 'completed'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cur.fetchall()

    async def list_market_nfts(self, limit: int = 40) -> list[aiosqlite.Row]:
        """Открытые NFT/подарки на витрине — только лоты продавца."""
        cur = await self.conn.execute(
            """
            SELECT code, deal_type, pay_method, amount, description, seller_id, buyer_id, status, created_at
            FROM deals
            WHERE status = 'open'
              AND deal_type IN ('gift', 'nft')
              AND seller_id IS NOT NULL
              AND seller_id != 0
              AND (
                lower(description) LIKE '%t.me/nft/%'
                OR lower(description) LIKE '%telegram.me/nft/%'
              )
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cur.fetchall()

    async def _purge_demo_reviews(self) -> None:
        cur = await self.conn.execute(
            "SELECT 1 FROM bot_meta WHERE key = ? LIMIT 1",
            ("purge_all_reviews_manual_v1",),
        )
        if await cur.fetchone() is not None:
            return
        await self.conn.execute("DELETE FROM reviews")
        await self.conn.execute(
            "INSERT INTO bot_meta (key, value) VALUES (?, ?)",
            ("purge_all_reviews_manual_v1", "1"),
        )
        await self.conn.commit()

    async def list_reviews(self, *, newest_first: bool = True) -> list[aiosqlite.Row]:
        order = "sort_order ASC, id DESC" if newest_first else "sort_order DESC, id ASC"
        cur = await self.conn.execute(f"SELECT * FROM reviews ORDER BY {order}")
        return await cur.fetchall()

    async def list_feed_reviews(self, limit: int = 24) -> list[aiosqlite.Row]:
        cur = await self.conn.execute(
            """
            SELECT * FROM reviews
            WHERE nft_url IS NOT NULL AND trim(nft_url) != ''
            ORDER BY sort_order ASC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cur.fetchall()

    async def add_review(
        self,
        username: str,
        rating: int,
        body: str,
        review_date: str = "",
        *,
        nft_url: str = "",
        deal_code: str = "",
        seller_username: str = "",
        buyer_username: str = "",
        seller_id: int | None = None,
        buyer_id: int | None = None,
        author_role: str = "buyer",
        amount: float = 0,
        pay_method: str = "",
        deal_type: str = "gift",
    ) -> aiosqlite.Row | None:
        cur = await self.conn.execute("SELECT COALESCE(MIN(sort_order), 0) AS m FROM reviews")
        row = await cur.fetchone()
        sort_order = int(row["m"] or 0) - 1
        cur = await self.conn.execute(
            """
            INSERT INTO reviews (
                username, rating, body, review_date, sort_order, nft_url, deal_code,
                seller_username, buyer_username, seller_id, buyer_id, author_role,
                amount, pay_method, deal_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username.lstrip("@"),
                max(1, min(5, int(rating))),
                body.strip(),
                review_date.strip(),
                sort_order,
                (nft_url or "").strip(),
                (deal_code or "").strip(),
                (seller_username or "").strip().lstrip("@"),
                (buyer_username or "").strip().lstrip("@"),
                seller_id,
                buyer_id,
                author_role if author_role in {"buyer", "seller"} else "buyer",
                float(amount or 0),
                (pay_method or "").strip().lower(),
                (deal_type or "gift").strip().lower(),
            ),
        )
        await self.conn.commit()
        return await self.get_review(int(cur.lastrowid))

    async def get_review(self, review_id: int) -> aiosqlite.Row | None:
        cur = await self.conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
        return await cur.fetchone()

    async def delete_review(self, review_id: int) -> bool:
        cur = await self.conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        await self.conn.commit()
        return cur.rowcount > 0

    async def move_review(self, review_id: int, direction: str) -> bool:
        rows = await self.list_reviews(newest_first=True)
        ids = [int(r["id"]) for r in rows]
        if review_id not in ids:
            return False
        i = ids.index(review_id)
        j = i - 1 if direction == "up" else i + 1
        if j < 0 or j >= len(ids):
            return False
        a, b = rows[i], rows[j]
        await self.conn.execute(
            "UPDATE reviews SET sort_order = ? WHERE id = ?",
            (int(b["sort_order"]), int(a["id"])),
        )
        await self.conn.execute(
            "UPDATE reviews SET sort_order = ? WHERE id = ?",
            (int(a["sort_order"]), int(b["id"])),
        )
        await self.conn.commit()
        return True


db = Database()

