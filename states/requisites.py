from aiogram.fsm.state import State, StatesGroup


class RequisitesStates(StatesGroup):
    waiting_ton = State()
    waiting_card = State()
    waiting_username = State()
