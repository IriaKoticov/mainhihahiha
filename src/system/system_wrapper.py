""" модуль для группового управления компонентами системы """


from multiprocessing import Process
from typing import List
from src.system.config import LOG_ERROR, LOG_INFO, CRITICALITY_STR


class SystemComponentsContainer:
    """ контейнер компонентов """    

    def __init__(self, components: List[Process], log_level = LOG_ERROR):
        self._components = components
        self.log_prefix = "[СИСТЕМА]"
        self.log_level = log_level

    def _log_message(self, criticality: int, message: str):
        """_log_message печатает сообщение заданного уровня критичности

        Args:
            criticality (int): уровень критичности
            message (str): текст сообщения
        """
        if criticality <= self.log_level:
            print(f"[{CRITICALITY_STR[criticality]}]{self.log_prefix} {message}")

    def start(self):
        """ запуск всех компонентов """

        for component in self._components:
            self._log_message(LOG_INFO, f"запуск {component.__class__.__name__}")
            component.start()

    def stop(self):
        """ остановка всех компонентов """

        for component in self._components:
            self._log_message(LOG_INFO, f"остановка {component.__class__.__name__}")
            component.stop()

        for component in self._components:
            component.join()

    def clean(self):
        """ очистка всех компонентов """
        for component in self._components:
            self._log_message(LOG_INFO, f"удаление {component.__class__.__name__}")
            del component
