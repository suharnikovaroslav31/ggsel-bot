from aiogram.fsm.state import State, StatesGroup


class CreateDealStates(StatesGroup):
    choosing_role = State()
    choosing_type = State()
    choosing_pay = State()
    waiting_amount = State()
    waiting_description = State()
