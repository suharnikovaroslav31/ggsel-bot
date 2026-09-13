from __future__ import annotations

import re
import secrets
import string

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import MANAGER_USERNAME
from database import db
from keyboards.main import (
    buyer_deal_kb,
    cancel_deal_menu,
    deal_created_kb,
    deal_pay_menu,
    deal_role_menu,
    deal_type_menu,
    main_menu,
    requisites_menu,
    seller_deal_kb,
)
from states.deals import CreateDealStates
from texts.deal_messages import (
    buyer_goods_ready_text,
    buyer_payment_accepted_text,
    deal_completed_text,
    deal_created_text,
    seller_after_payment_text,
)
from texts.i18n import deal_pay_labels, deal_type_labels, requisites_text, t
from utils.admin_access import is_admin
from utils.currencies import PAY_REQUISITE, PAY_TO_BALANCE
from utils.lang import get_lang
from utils.media import edit_ui, reply_ui, send_ui
from utils.panel import report_deal

router = Router()

NFT_RE = re.compile(r"^https://t\.me/nft/[A-Za-z0-9_\-]+$", re.IGNORECASE)


def _deal_code(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _edit(callback: CallbackQuery, text: str, markup) -> None:
    await edit_ui(callback, text, markup)


@router.callback_query(F.data == "menu:create")
async def menu_create(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id)
    await state.clear()
    await state.set_state(CreateDealStates.choosing_role)
    await _edit(
        callback,
        "— Кто вы в этой сделке?",
        deal_role_menu(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deal:role:"))
async def choose_role(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id)
    role = callback.data.split(":")[-1]
    if role not in {"seller", "buyer"}:
        await callback.answer("Неизвестная роль", show_alert=True)
        return
    await state.update_data(creator_role=role)
    await state.set_state(CreateDealStates.choosing_type)
    await _edit(callback, t(lang, "deal_type"), deal_type_menu(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("deal:type:"))
async def choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id)
    deal_type = callback.data.split(":")[-1]
    labels = deal_type_labels(lang)
    if deal_type not in labels:
        await callback.answer("Unknown deal type", show_alert=True)
        return

    data = await state.get_data()
    if "creator_role" not in data:
        await state.set_state(CreateDealStates.choosing_role)
        await _edit(callback, "— Кто вы в этой сделке?", deal_role_menu(lang))
        await callback.answer("Сначала выберите роль", show_alert=True)
        return

    await state.update_data(deal_type=deal_type)
    await state.set_state(CreateDealStates.choosing_pay)
    await _edit(callback, t(lang, "deal_pay"), deal_pay_menu(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("deal:pay:"))
async def choose_pay(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id)
    pay_method = callback.data.split(":")[-1]
    pay_labels = deal_pay_labels(lang)
    type_labels = deal_type_labels(lang)
    if pay_method not in pay_labels:
        await callback.answer("Unknown payment method", show_alert=True)
        return

    data = await state.get_data()
    if "deal_type" not in data or "creator_role" not in data:
        await state.set_state(CreateDealStates.choosing_role)
        await _edit(callback, "— Кто вы в этой сделке?", deal_role_menu(lang))
        await callback.answer("Начните создание сделки заново", show_alert=True)
        return

    # Реквизиты нужны тому, кто принимает оплату (продавец)
    if data["creator_role"] == "seller":
        user = await db.get_user(callback.from_user.id)
        need = PAY_REQUISITE.get(pay_method)
        if need == "ton" and not (user and user["ton_wallet"]):
            await callback.answer(t(lang, "need_ton"), show_alert=True)
            text = requisites_text(
                lang,
                ton_wallet=user["ton_wallet"] if user else None,
                card_number=user["card_number"] if user else None,
            )
            await state.clear()
            await _edit(callback, text, requisites_menu(lang))
            return
        if need == "card" and not (user and user["card_number"]):
            await callback.answer(t(lang, "need_card"), show_alert=True)
            text = requisites_text(
                lang,
                ton_wallet=user["ton_wallet"] if user else None,
                card_number=user["card_number"] if user else None,
            )
            await state.clear()
            await _edit(callback, text, requisites_menu(lang))
            return

    await state.update_data(pay_method=pay_method)
    await state.set_state(CreateDealStates.waiting_amount)

    text = (
        f"<b>{t(lang, 'deal_create_title')}</b>\n\n"
        f"{t(lang, 'deal_type_label')}: {type_labels[data['deal_type']]}\n"
        f"{t(lang, 'deal_pay_label')}: {pay_labels[pay_method]}\n\n"
        f"{t(lang, 'deal_amount_prompt')}"
    )
    await _edit(callback, text, cancel_deal_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "deal:cancel")
async def cancel_deal_flow(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await get_lang(callback.from_user.id)
    await state.clear()
    await state.set_state(CreateDealStates.choosing_role)
    await _edit(callback, "— Кто вы в этой сделке?", deal_role_menu(lang))
    await callback.answer()


@router.message(CreateDealStates.waiting_amount, F.text)
async def save_amount(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    raw = message.text.strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        await reply_ui(
            message,
            "❌ Введите сумму числом, например <code>100</code>",
            cancel_deal_menu(lang),
        )
        return

    if amount <= 0 or amount > 10_000_000:
        await reply_ui(
            message,
            "❌ Сумма должна быть больше 0 и не больше 10 000 000",
            cancel_deal_menu(lang),
        )
        return

    data = await state.get_data()
    await state.update_data(amount=amount)
    await state.set_state(CreateDealStates.waiting_description)

    deal_type = data.get("deal_type")
    if deal_type in {"gift", "nft"}:
        prompt = (
            "🎁 Отправьте ссылку на NFT\n"
            "Формат: <code>https://t.me/nft/Name-123</code>"
        )
    else:
        prompt = "📝 Отправьте описание сделки\n(ссылка или текст)"
    await reply_ui(message, prompt, cancel_deal_menu(lang))


@router.message(CreateDealStates.waiting_description, F.text)
async def save_description(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.from_user.id)
    description = message.text.strip()
    data = await state.get_data()
    deal_type = data.get("deal_type")
    pay_method = data.get("pay_method")
    amount = data.get("amount")
    creator_role = data.get("creator_role")

    if deal_type in {"gift", "nft"}:
        if not NFT_RE.match(description):
            await reply_ui(
                message,
                "❌ Нужна ссылка на NFT вида:\n"
                "<code>https://t.me/nft/PlushPepe-111</code>",
                cancel_deal_menu(lang),
            )
            return
    elif len(description) > 500:
        await reply_ui(
            message,
            "❌ Описание слишком длинное (макс. 500).",
            cancel_deal_menu(lang),
        )
        return

    if not deal_type or not pay_method or amount is None or creator_role not in {"seller", "buyer"}:
        await state.clear()
        await reply_ui(
            message,
            "Сессия сброшена. Откройте «Создать сделку» снова.",
            main_menu(lang, is_admin=await is_admin(message.from_user.id)),
        )
        return

    code = _deal_code()
    await db.upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    await db.create_deal(
        code=code,
        creator_id=message.from_user.id,
        creator_role=creator_role,
        deal_type=deal_type,
        pay_method=pay_method,
        amount=float(amount),
        description=description,
    )
    await state.clear()
    report_deal(code, "created", actor_id=message.from_user.id)

    me = await message.bot.get_me()
    text = deal_created_text(
        code=code,
        role=creator_role,
        pay_method=pay_method,
        amount=float(amount),
        description=description,
        bot_username=me.username,
    )
    await reply_ui(message, text, deal_created_kb(code, lang))


@router.callback_query(F.data.startswith("deal:abort:"))
async def abort_deal(callback: CallbackQuery) -> None:
    lang = await get_lang(callback.from_user.id)
    code = callback.data.split(":")[-1]
    ok = await db.cancel_deal(code, callback.from_user.id)
    if not ok:
        await callback.answer("Нельзя отменить эту сделку", show_alert=True)
        return
    report_deal(code, "cancelled", actor_id=callback.from_user.id)
    await edit_ui(
        callback,
        f"❌ Сделка <b>#{code}</b> отменена.",
        main_menu(lang, is_admin=await is_admin(callback.from_user.id)),
    )
    await callback.answer("Сделка отменена")


@router.callback_query(F.data.startswith("deal:paybal:"))
async def buyer_pay_from_balance(callback: CallbackQuery) -> None:
    code = callback.data.split(":")[-1]
    deal = await db.get_deal_by_code(code)
    if not deal:
        await callback.answer("Сделка не найдена", show_alert=True)
        return
    if callback.from_user.id != deal["buyer_id"]:
        await callback.answer("Оплатить может только покупатель", show_alert=True)
        return
    if deal["status"] == "paid":
        await callback.answer("Оплата уже прошла", show_alert=False)
        return
    if deal["status"] != "active":
        await callback.answer("Сейчас оплата недоступна", show_alert=True)
        return

    amount = float(deal["amount"])
    pay_method = deal["pay_method"]
    ok = await db.deduct_balance(callback.from_user.id, pay_method, amount)
    if not ok:
        await callback.answer("Недостаточно средств на балансе", show_alert=True)
        return

    status_ok = await db.set_deal_status(code, "paid", only_if="active")
    if not status_ok:
        await callback.answer("Не удалось зафиксировать оплату", show_alert=True)
        return
    report_deal(code, "paid", actor_id=callback.from_user.id)

    seller_user = await db.get_user(deal["seller_id"])
    description = ""
    try:
        description = deal["description"] or ""
    except (KeyError, IndexError, TypeError):
        description = ""

    buyer_text = buyer_payment_accepted_text(
        code=code,
        seller_username=seller_user["username"] if seller_user else None,
        seller_id=int(deal["seller_id"]),
        description=description,
        pay_method=pay_method,
        amount=amount,
    )
    await edit_ui(callback, buyer_text)
    await callback.answer("Оплата принята")

    try:
        await send_ui(
            callback.bot,
            deal["seller_id"],
            seller_after_payment_text(),
            seller_deal_kb(code),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("deal:sent:"))
async def seller_mark_sent(callback: CallbackQuery) -> None:
    code = callback.data.split(":")[-1]
    deal = await db.get_deal_by_code(code)
    if not deal:
        await callback.answer("Сделка не найдена", show_alert=True)
        return
    if callback.from_user.id != deal["seller_id"]:
        await callback.answer("Только продавец может подтвердить передачу", show_alert=True)
        return
    if deal["status"] == "completed":
        await callback.answer("Сделка уже завершена", show_alert=True)
        return
    if deal["status"] == "goods_sent":
        await callback.answer("Уже отмечено", show_alert=False)
        return
    if deal["status"] != "paid":
        await callback.answer("Дождитесь оплаты покупателя", show_alert=True)
        return

    ok = await db.set_deal_status(code, "goods_sent", only_if="paid")
    if not ok and deal["status"] != "goods_sent":
        await callback.answer("Не удалось обновить статус", show_alert=True)
        return
    report_deal(code, "goods_sent", actor_id=callback.from_user.id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отмечено: товар передан гаранту")

    if deal["buyer_id"]:
        try:
            await send_ui(
                callback.bot,
                deal["buyer_id"],
                buyer_goods_ready_text(code=code, manager=MANAGER_USERNAME),
                buyer_deal_kb(code),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("deal:recv:"))
async def buyer_confirm_received(callback: CallbackQuery) -> None:
    code = callback.data.split(":")[-1]
    deal = await db.get_deal_by_code(code)
    if not deal:
        await callback.answer("Сделка не найдена", show_alert=True)
        return
    if callback.from_user.id != deal["buyer_id"]:
        await callback.answer("Только покупатель может подтвердить получение", show_alert=True)
        return
    if deal["status"] == "completed":
        await callback.answer("Сделка уже завершена", show_alert=False)
        return
    if deal["status"] != "goods_sent":
        await callback.answer(
            "Сначала продавец должен передать товар гаранту",
            show_alert=True,
        )
        return

    ok = await db.set_deal_status(code, "completed", only_if="goods_sent")
    if not ok:
        await callback.answer("Не удалось завершить сделку", show_alert=True)
        return
    report_deal(code, "completed", actor_id=callback.from_user.id)

    # Начисляем продавцу сумму сделки (покупатель уже списал с баланса при оплате)
    pay_method = deal["pay_method"]
    credit_currency = PAY_TO_BALANCE.get(pay_method)
    if credit_currency and deal["seller_id"]:
        try:
            await db.add_balance(int(deal["seller_id"]), credit_currency, float(deal["amount"]))
        except Exception:
            pass

    await edit_ui(callback, deal_completed_text(code=code, role="buyer"))
    await callback.answer("Получение подтверждено")

    try:
        await send_ui(
            callback.bot,
            deal["seller_id"],
            deal_completed_text(code=code, role="seller")
            + f"\n\n💰 На баланс зачислено: <b>{float(deal['amount']):g}</b>",
        )
    except Exception:
        pass
