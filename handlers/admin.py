from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import db
from keyboards.main import _btn
from states.admin import AdminStates
from utils.admin_access import is_admin, is_super_admin
from utils.currencies import BALANCE_KEYS, BALANCE_META
from utils.emoji import ce
from utils.media import edit_ui, reply_ui, send_ui

router = Router()


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
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_currency_menu() -> InlineKeyboardMarkup:
    from utils.currencies import BALANCE_META, rows_of

    buttons = [
        _btn(
            meta["label"],
            fallback_emoji=meta["fallback"],
            callback=f"admin:add:{key}",
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
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
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
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        admin_menu(message.from_user.id),
    )


@router.callback_query(F.data == "menu:admin")
async def menu_admin(callback: CallbackQuery, state: FSMContext) -> None:
    if await _deny_if_not_admin(callback):
        return
    await state.clear()
    await edit_ui(
        callback,
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
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
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        admin_menu(callback.from_user.id),
    )
    await callback.answer()


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

    admins = await db.list_admins()
    ids_line = ", ".join(f"<code>{a}</code>" for a in admins)
    await reply_ui(
        message,
        f"{text}\n\nТекущие воркеры:\n{ids_line}",
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
