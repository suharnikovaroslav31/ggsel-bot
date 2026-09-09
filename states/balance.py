from aiogram.fsm.state import State, StatesGroup


class BalanceStates(StatesGroup):
    waiting_withdraw_amount = State()
