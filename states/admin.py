from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    waiting_amount = State()
    waiting_admin_id = State()
    waiting_ban_id = State()
    waiting_unban_id = State()
