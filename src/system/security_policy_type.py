""" модуль описания типа политики безопасности """

from dataclasses import dataclass


@dataclass
class SecurityPolicy:
    """ политика безопасности """
    source: str         # отправитель запроса
    destination: str    # получатель
    operation: str      # запрашиваемая операция
