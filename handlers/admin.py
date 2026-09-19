from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db
from keyboards.main import _btn, _kb
from states.admin import AdminStates
from texts.deal_messages import manager_balance_sent_text
from utils.admin_access import is_admin, is_super_admin
from utils.currencies import BALANCE_KEYS, BALANCE_META
from utils.emoji import ce
from utils.media import edit_ui, reply_ui, send_ui

router = Router()


def _admin_home_text(user_id: int) -> str:
    if is_super_admin(user_id):
        return "🛠 <b>Главный админ</b>\n\nВыберите действие:"
    return "🛠 <b>Админ-панель</b>\n\nВыберите действие:"


def admin_menu(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                "Начислить баланс",
                fallback_emoji="💰",
                callback="admin:credit",
                icon_key="deal_money",
            )
        ],
        [
            _btn(
                "Мой баланс",
                fallback_emoji="👤",
                callback="admin:balance",
                icon_key="deal_person",
            )
        ],
        [
            _btn(
                "Передать на баланс",
                fallback_emoji="⭐",
                callback="admin:send",
                icon_key="btn_deal_stars",
            )
        ],
    ]
    if user_id is not None and is_super_admin(user_id):
        rows.append(
            [
                _btn(
                    "Добавить воркера",
                    fallback_emoji="➕",
                    callback="admin:grant",
                    icon_key="btn_create",
                )
            ]
        )
        rows.append(
            [
                _btn(
                    "Забанить",
                    fallback_emoji="🚫",
                    callback="admin:ban",
                    icon_key="btn_cancel",
                ),
                _btn(
                    "Разбанить",
                    fallback_emoji="✅",
                    callback="admin:unban",
                    icon_key="btn_deal_recv",
                ),
            ]
        )
    rows.append(
        [
            _btn(
                "Закрыть",
                fallback_emoji="❌",
                callback="admin:close",
                icon_key="btn_cancel",
            )
        ]
    )
    return _kb(rows)


def admin_currency_menu(*, prefix: str = "admin:add") -> InlineKeyboardMarkup:
    from utils.currencies import BALANCE_META, rows_of

    buttons = [
        _btn(
            meta["label"],
            fallback_emoji=meta["fallback"],
            callback=f"{prefix}:{key}",
            icon_key=meta["btn_icon"],
        )
        for key, meta in BALANCE_META.items()
    ]
    rows = rows_of(buttons, 2)
    rows.append(
        [
            _btn(
                "Назад",
                fallback_emoji="🔙",
                callback="admin:cancel",
                icon_key="btn_back",
            )
        ]
    )
    return _kb(rows)


def admin_cancel() -> InlineKeyboardMarkup:
    return _kb(
        [
            [
                _btn(
                    "Отмена",
                    fallback_emoji="❌",
                    callback="admin:cancel",
                    icon_key="btn_cancel",
                )
            ]
        ]
    )


def _balance_text(user) -> str:
    from utils.currencies import BALANCE_GROUPS, BALANCE_META

    lines = []
    for group_name, keys in BALANCE_GROUPS:
        lines.append(f"<b>{group_name}</b>")
        for key in keys:
            meta = BALANCE_META[key]
            col = f"balance_{key}"
            try:
                raw = user[col] if user else 0
            except (KeyError, IndexError, TypeError):
                raw = 0
            icon = ce(meta["emoji_key"], meta["fallback"])
            if meta["integer"]:
                lines.append(f"{icon} {meta['label']}: {int(raw or 0)}")
            else:
                lines.append(f"{icon} {meta['label']}: {float(raw or 0):.2f}")
        lines.append("")
    return "\n".join(lines).rstrip()


async def _deny_if_not_admin(event: Message | CallbackQuery) -> bool:
    uid = event.from_user.id
    if await is_admin(uid):
        return False
    if isinstance(event, CallbackQuery):
        await event.answer()
    return True


async def _deny_if_not_super_admin(event: Message | CallbackQuery) -> bool:
    if await _deny_if_not_admin(event):
        return True
    uid = event.from_user.id
    if is_super_admin(uid):
        return False
    if isinstance(event, CallbackQuery):
        await event.answer()
    return True


async def _parse_telegram_id(message: Message) -> int | None:
    raw = message.text.strip()
    if not raw.isdigit():
        await reply_ui(message, "❌ Нужен числовой Telegram ID.", admin_cancel())
        return None
    user_id = int(raw)
    if user_id <= 0:
        await reply_ui(message, "❌ Некорректный ID.", admin_cancel())
        return None
    return user_id


@router.message(Command("panel_test"))
async def cmd_panel_test(message: Message) -> None:
    if await _deny_if_not_admin(message):
        return
    from utils.panel import probe

    url, verdict = await probe()
    await reply_ui(
        message,
        "🔌 <b>Связь с панелью</b>\n\n"
        f"Адрес: <code>{url}</code>\n"
        f"{verdict}",
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if await _deny_if_not_admin(message):
        return
    await state.clear()
    await reply_ui(
        message,
        _admin_home_text(message.from_user.id),
        admin_menu(message.from_user.id),
    )


@router.callback_query(F.data == "menu:admin")
async def menu_admin(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    await state.clear()
    await edit_ui(
        callback,
        _admin_home_text(callback.from_user.id),
        admin_menu(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    await state.clear()
    await edit_ui(callback, "Админ-панель закрыта.")
    await callback.answer()


@router.callback_query(F.data == "admin:cancel")
async def admin_cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    await state.clear()
    await edit_ui(
        callback,
        _admin_home_text(callback.from_user.id),
        admin_menu(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"admin:send", "admin:stars"}))
async def admin_send_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    await state.clear()
    money = ce("deal_money", "💰")
    await edit_ui(
        callback,
        f"{money} <b>Передать на баланс</b>\n\nВыберите валюту:",
        admin_currency_menu(prefix="admin:xfer"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:xfer:"))
async def admin_send_currency(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    currency = callback.data.split(":")[-1]
    meta = BALANCE_META.get(currency)
    if not meta or currency not in BALANCE_KEYS:
        await callback.answer("Неизвестная валюта", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_send_user_id)
    await state.update_data(send_currency=currency)
    icon = ce(meta["emoji_key"], meta["fallback"])
    await edit_ui(
        callback,
        f"{icon} <b>Передать {meta['label']}</b>\n\n"
        "Отправьте Telegram ID покупателя или продавца числом\n"
        "(например <code>123456789</code>)",
        admin_cancel(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_send_user_id, F.text)
async def admin_send_got_id(message: Message, state: FSMContext) -> None:
    if await _deny_if_not_admin(message):
        return
    target_id = await _parse_telegram_id(message)
    if target_id is None:
        return
    data = await state.get_data()
    currency = data.get("send_currency")
    meta = BALANCE_META.get(currency or "")
    if not meta:
        await state.clear()
        await reply_ui(
            message,
            "Сессия сброшена. Откройте /admin снова.",
            admin_menu(message.from_user.id),
        )
        return
    await state.update_data(send_user_id=target_id)
    await state.set_state(AdminStates.waiting_send_amount)
    icon = ce(meta["emoji_key"], meta["fallback"])
    hint = "целым числом" if meta["integer"] else "числом"
    await reply_ui(
        message,
        f"{icon} {meta['label']} → <code>{target_id}</code>\n\n"
        f"Введите сумму {hint}\n"
        "(например <code>50</code>)",
        admin_cancel(),
    )


@router.message(AdminStates.waiting_send_amount, F.text)
async def admin_send_got_amount(message: Message, state: FSMContext) -> None:
    if await _deny_if_not_admin(message):
        return
    raw = message.text.strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        await reply_ui(message, "❌ Введите число.", admin_cancel())
        return
    if amount <= 0:
        await reply_ui(message, "❌ Сумма должна быть больше 0.", admin_cancel())
        return

    data = await state.get_data()
    currency = data.get("send_currency")
    target_id = data.get("send_user_id")
    meta = BALANCE_META.get(currency or "")
    if not meta or currency not in BALANCE_KEYS or not target_id:
        await state.clear()
        await reply_ui(
            message,
            "Сессия сброшена. Откройте /admin снова.",
            admin_menu(message.from_user.id),
        )
        return
    if meta["integer"] and not float(amount).is_integer():
        await reply_ui(
            message,
            f"❌ {meta['label']} должны быть целым числом.",
            admin_cancel(),
        )
        return

    credit = int(amount) if meta["integer"] else float(amount)
    user = await db.add_balance(int(target_id), currency, credit)
    notify = manager_balance_sent_text(amount=credit, currency=currency)
    notified = True
    try:
        await send_ui(message.bot, int(target_id), notify)
    except Exception:
        notified = False

    await state.clear()
    icon = ce(meta["emoji_key"], meta["fallback"])
    check = ce("deal_check", "✅")
    amount_text = f"{int(credit)}" if meta["integer"] else f"{float(credit):g}"
    text = (
        f"{check} Готово\n\n"
        f"{icon} <b>{amount_text} {meta['label']}</b> зачислены на баланс "
        f"<code>{target_id}</code> от менеджера."
    )
    if not notified:
        text += "\n\n⚠️ Пользователь ещё не писал боту — сообщение не ушло, баланс уже начислен."
    if user:
        text += f"\n\nЕго баланс:\n{_balance_text(user)}"
    await reply_ui(message, text, admin_menu(message.from_user.id))


@router.callback_query(F.data == "admin:credit")
async def admin_credit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    await state.clear()
    await edit_ui(
        callback,
        "💰 <b>Выберите валюту</b>",
        admin_currency_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:add:"))
async def admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    currency = callback.data.split(":")[-1]
    meta = BALANCE_META.get(currency)
    if not meta:
        await callback.answer("Неизвестная валюта", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_amount)
    await state.update_data(currency=currency, target_id=callback.from_user.id)
    icon = ce(meta["emoji_key"], meta["fallback"])
    await edit_ui(
        callback,
        f"Начисление {icon} <b>{meta['label']}</b> себе\n\n"
        "Введите сумму начисления\n"
        "(можно отрицательную, чтобы списать)",
        admin_cancel(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:balance")
async def admin_balance_view(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    await edit_ui(
        callback,
        f"👤 <b>Ваш баланс</b>\n\n{_balance_text(user)}",
        admin_menu(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:grant")
async def admin_grant_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_super_admin(callback):
        return
    await state.set_state(AdminStates.waiting_admin_id)
    await edit_ui(
        callback,
        "➕ <b>Добавить воркера</b>\n\n"
        "Отправьте Telegram ID пользователя числом\n"
        "(например <code>123456789</code>)",
        admin_cancel(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_admin_id, F.text)
async def admin_got_admin_id(message: Message, state: FSMContext) -> None:
    if await _deny_if_not_super_admin(message):
        return

    new_id = await _parse_telegram_id(message)
    if new_id is None:
        return

    if is_super_admin(new_id):
        await state.clear()
        await reply_ui(
            message,
            "❌ Это ID главного админа, его нельзя назначить воркером.",
            admin_menu(message.from_user.id),
        )
        return

    added = await db.add_admin(new_id)
    await state.clear()

    if added:
        text = f"✅ Пользователь <code>{new_id}</code> добавлен как воркер."
        try:
            await send_ui(
                message.bot,
                new_id,
                "🛠 Вам выдан доступ к <b>админ-панели</b> бота.\n"
                "Напишите /start — в меню появится кнопка «Админ-панель».",
            )
        except Exception:
            text += "\n\n⚠️ Не удалось уведомить пользователя (он ещё не писал боту)."
    else:
        text = f"ℹ️ <code>{new_id}</code> уже является воркером."

    workers = await db.list_admins()
    if workers:
        ids_line = ", ".join(f"<code>{a}</code>" for a in workers)
        extra = f"\n\nТекущие воркеры:\n{ids_line}"
    else:
        extra = "\n\nВоркеров пока нет."
    await reply_ui(
        message,
        f"{text}{extra}",
        admin_menu(message.from_user.id),
    )


@router.callback_query(F.data == "admin:ban")
async def admin_ban_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_super_admin(callback):
        return
    await state.set_state(AdminStates.waiting_ban_id)
    await edit_ui(
        callback,
        "🚫 <b>Забанить</b>\n\n"
        "Отправьте Telegram ID пользователя числом\n"
        "(например <code>123456789</code>)",
        admin_cancel(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_ban_id, F.text)
async def admin_got_ban_id(message: Message, state: FSMContext) -> None:
    if await _deny_if_not_super_admin(message):
        return

    target_id = await _parse_telegram_id(message)
    if target_id is None:
        return

    if is_super_admin(target_id):
        await state.clear()
        await reply_ui(
            message,
            "❌ Нельзя забанить этого пользователя.",
            admin_menu(message.from_user.id),
        )
        return

    banned = await db.ban_user(target_id)
    await state.clear()
    if banned:
        text = f"🚫 Пользователь <code>{target_id}</code> забанен."
    else:
        text = f"ℹ️ <code>{target_id}</code> уже в бане."
    await reply_ui(message, text, admin_menu(message.from_user.id))


@router.callback_query(F.data == "admin:unban")
async def admin_unban_start(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_super_admin(callback):
        return
    await state.set_state(AdminStates.waiting_unban_id)
    await edit_ui(
        callback,
        "✅ <b>Разбанить</b>\n\n"
        "Отправьте Telegram ID пользователя числом\n"
        "(например <code>123456789</code>)",
        admin_cancel(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_unban_id, F.text)
async def admin_got_unban_id(message: Message, state: FSMContext) -> None:
    if await _deny_if_not_super_admin(message):
        return

    target_id = await _parse_telegram_id(message)
    if target_id is None:
        return

    unbanned = await db.unban_user(target_id)
    await state.clear()
    if unbanned:
        text = f"✅ Пользователь <code>{target_id}</code> разбанен."
    else:
        text = f"ℹ️ <code>{target_id}</code> не был в бане."
    await reply_ui(message, text, admin_menu(message.from_user.id))


@router.message(AdminStates.waiting_amount, F.text)
async def admin_got_amount(message: Message, state: FSMContext) -> None:
    if await _deny_if_not_admin(message):
        return

    raw = message.text.strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        await reply_ui(message, "❌ Введите число.", admin_cancel())
        return

    if amount == 0:
        await reply_ui(message, "❌ Сумма не может быть 0.", admin_cancel())
        return

    data = await state.get_data()
    target_id = int(data.get("target_id") or message.from_user.id)
    currency = data.get("currency")
    meta = BALANCE_META.get(currency or "")
    if not meta or currency not in BALANCE_KEYS:
        await state.clear()
        await reply_ui(
            message,
            "Сессия сброшена. Откройте /admin снова.",
            admin_menu(message.from_user.id),
        )
        return

    if meta["integer"] and not float(amount).is_integer():
        await reply_ui(
            message,
            f"❌ {meta['label']} должны быть целым числом.",
            admin_cancel(),
        )
        return

    user = await db.add_balance(target_id, currency, amount)
    await state.clear()

    sign = "+" if amount > 0 else ""
    icon = ce(meta["emoji_key"], meta["fallback"])
    await reply_ui(
        message,
        f"✅ Готово\n\n"
        f"{icon} {meta['label']}: {sign}{amount:g}\n\n"
        f"Текущий баланс:\n"
        f"{_balance_text(user)}",
        admin_menu(message.from_user.id),
    )
