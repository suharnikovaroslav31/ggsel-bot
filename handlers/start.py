import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db
from keyboards.main import open_app_kb
from texts.deal_messages import (
    buyer_goods_ready_text,
    buyer_payment_accepted_text,
    buyer_seller_joined_text,
    deal_completed_text,
    seller_deal_connected_text,
)
from utils.app_gate import entry_kb, entry_text, send_app, wipe_reply_kb
from utils.media import reply_ui, send_ui
from utils.panel import report_deal

log = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    referrer_id = None
    args = (command.args or "").strip()

    if args.startswith("deal_"):
        await _handle_deal_start(message, args.removeprefix("deal_"))
        return

    if args.isdigit():
        rid = int(args)
        if rid != message.from_user.id:
            referrer_id = rid

    await db.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referrer_id=referrer_id,
    )
    user = await db.get_user(message.from_user.id)

    prev_id = await db.get_last_welcome_msg_id(message.from_user.id)
    if prev_id:
        try:
            await message.bot.delete_message(message.chat.id, prev_id)
        except Exception:
            pass

    sent = await reply_ui(
        message,
        entry_text(user),
        entry_kb(user),
    )
    await db.set_last_welcome_msg_id(message.from_user.id, sent.message_id)
    await wipe_reply_kb(message.bot, message.chat.id)
    await _delete_user_message(message)


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    await send_app(message)


async def _delete_user_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def _send_retry(coro_factory, attempts: int = 4):
    last_exc = None
    for i in range(attempts):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            log.warning("send retry %s/%s failed: %s", i + 1, attempts, exc)
            await asyncio.sleep(1.5 * (i + 1))
    if last_exc:
        raise last_exc


async def _handle_deal_start(message: Message, code: str) -> None:
    await wipe_reply_kb(message.bot, message.chat.id)
    await db.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    user = await db.get_user(message.from_user.id)
    deal = await db.get_deal_by_code(code)
    if not deal:
        sent = await _send_retry(lambda: reply_ui(message, "❌ Сделка не найдена.", entry_kb(user)))
        if sent:
            await db.set_last_welcome_msg_id(message.from_user.id, sent.message_id)
        await _delete_user_message(message)
        return

    seller_id = int(deal["seller_id"] or 0)
    buyer_id = deal["buyer_id"]
    uid = message.from_user.id

    if uid == seller_id or uid == buyer_id:
        sent = await _send_retry(lambda: reply_ui(message, entry_text(user), entry_kb(user, code)))
        if sent:
            await db.set_last_welcome_msg_id(message.from_user.id, sent.message_id)
        await _delete_user_message(message)
        return

    if deal["status"] != "open":
        sent = await _send_retry(
            lambda: reply_ui(message, "❌ Сделка уже занята или закрыта.", entry_kb(user))
        )
        if sent:
            await db.set_last_welcome_msg_id(message.from_user.id, sent.message_id)
        await _delete_user_message(message)
        return

    joined_as = await db.join_deal(code, uid)
    if not joined_as:
        sent = await _send_retry(
            lambda: reply_ui(
                message,
                "❌ Не удалось подключиться к сделке. Попробуйте ещё раз.",
                entry_kb(user, code),
            )
        )
        if sent:
            await db.set_last_welcome_msg_id(message.from_user.id, sent.message_id)
        await _delete_user_message(message)
        return

    deal = await db.get_deal_by_code(code)
    report_deal(code, "joined", actor_id=uid)
    seller_id = int(deal["seller_id"] or 0)
    buyer_id = deal["buyer_id"]
    other = buyer_id if uid == seller_id else seller_id
    if other:
        await _notify_deal_parties(message, deal, code, resend_only_for=int(other))
    sent = await _send_retry(lambda: reply_ui(message, entry_text(user), entry_kb(user, code)))
    if sent:
        await db.set_last_welcome_msg_id(message.from_user.id, sent.message_id)
    await _delete_user_message(message)


async def _notify_deal_parties(
    message: Message,
    deal,
    code: str,
    resend_only_for: int | None = None,
) -> None:
    if not deal:
        return
    description = ""
    try:
        description = deal["description"] or ""
    except (KeyError, IndexError, TypeError):
        description = ""

    seller_id = int(deal["seller_id"] or 0)
    buyer_id = deal["buyer_id"]
    if not seller_id or not buyer_id:
        return

    status = deal["status"]
    amount = float(deal["amount"])
    pay_method = deal["pay_method"]

    buyer_user = await db.get_user(buyer_id)
    seller_user = await db.get_user(seller_id)
    buyer_deals = await db.count_user_deals(buyer_id)
    seller_completed = await db.count_completed_deals(seller_id)

    seller_text = seller_deal_connected_text(
        code=code,
        buyer_username=buyer_user["username"] if buyer_user else None,
        buyer_id=buyer_id,
        buyer_deals=buyer_deals,
        description=description,
        pay_method=pay_method,
        amount=amount,
    )

    if status == "active":
        buyer_text = buyer_seller_joined_text(
            code=code,
            seller_username=seller_user["username"] if seller_user else None,
            seller_id=seller_id,
            seller_completed_deals=seller_completed,
        )
        buyer_markup = open_app_kb(f"deal={code}")
        seller_markup = open_app_kb(f"deal={code}")
    elif status == "paid":
        buyer_text = buyer_payment_accepted_text(
            code=code,
            seller_username=seller_user["username"] if seller_user else None,
            seller_id=seller_id,
            description=description,
            pay_method=pay_method,
            amount=amount,
        )
        buyer_markup = open_app_kb(f"deal={code}")
        seller_markup = open_app_kb(f"deal={code}")
    elif status == "goods_sent":
        buyer_text = buyer_goods_ready_text(code=code)
        buyer_markup = open_app_kb(f"deal={code}")
        seller_markup = open_app_kb(f"deal={code}")
    elif status == "completed":
        buyer_text = deal_completed_text(code=code, role="buyer")
        buyer_markup = open_app_kb(f"deal={code}")
        seller_markup = open_app_kb(f"deal={code}")
        seller_text = deal_completed_text(code=code, role="seller")
    else:
        return

    send_seller = resend_only_for is None or resend_only_for == seller_id
    send_buyer = resend_only_for is None or resend_only_for == buyer_id

    if send_seller:
        try:
            await _send_retry(
                lambda: send_ui(message.bot, seller_id, seller_text, seller_markup)
            )
        except Exception as exc:
            log.warning("failed to notify seller: %s", exc)

    if send_buyer:
        try:
            if message.from_user.id == buyer_id:
                await _send_retry(
                    lambda: reply_ui(message, buyer_text, buyer_markup)
                )
            else:
                await _send_retry(
                    lambda: send_ui(message.bot, buyer_id, buyer_text, buyer_markup)
                )
        except Exception as exc:
            log.error("failed to notify buyer: %s", exc)


@router.callback_query(F.data.startswith("menu:"))
@router.callback_query(F.data.startswith("withdraw:"))
@router.callback_query(F.data.startswith("deal:role:"))
@router.callback_query(F.data.startswith("deal:type:"))
@router.callback_query(F.data.startswith("deal:pay:"))
@router.callback_query(F.data.startswith("req:"))
@router.callback_query(F.data == "deal:cancel")
async def open_miniapp_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await send_app(callback, state)


@router.callback_query(F.data.in_({"lang:ru", "lang:en"}))
async def set_language(callback: CallbackQuery, state: FSMContext) -> None:
    new_lang = "en" if callback.data.endswith("en") else "ru"
    await db.upsert_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name,
    )
    await db.set_language(callback.from_user.id, new_lang)
    await send_app(callback, state)


@router.message(F.text.regexp(r"^(?!/).+"))
async def fallback_open_app(message: Message, state: FSMContext) -> None:
    await send_app(message, state)
