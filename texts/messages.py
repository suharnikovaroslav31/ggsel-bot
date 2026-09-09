"""Совместимость: основные тексты живут в texts.i18n."""

from texts.i18n import (  # noqa: F401
    balance_text,
    deal_pay_labels,
    deal_type_labels,
    lang_text,
    requisites_text,
    welcome_text,
)

# Старые константы (русский по умолчанию) для обратной совместимости
DEAL_TYPE_LABELS = deal_type_labels("ru")
DEAL_PAY_LABELS = deal_pay_labels("ru")


def deal_type_text(lang: str | None = "ru") -> str:
    from texts.i18n import t

    return t(lang, "deal_type")


def deal_pay_text(lang: str | None = "ru") -> str:
    from texts.i18n import t

    return t(lang, "deal_pay")
