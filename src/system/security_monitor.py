""" модуль монитора безопасности """
from abc import abstractmethod
from multiprocessing import Queue, Process
from queue import Empty

from time import sleep

from src.system.custom_process import BaseCustomProcess
from src.system.config import LOG_ERROR, SECURITY_MONITOR_QUEUE_NAME,\
    CRITICALITY_STR, DEFAULT_LOG_LEVEL, \
    LOG_DEBUG, LOG_INFO
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent


class BaseSecurityMonitor(BaseCustomProcess):
    """ класс монитора безопасности """
    log_prefix = "[SECURITY]"
    event_source_name = SECURITY_MONITOR_QUEUE_NAME
    events_q_name = event_source_name

    def __init__(self, queues_dir: QueuesDirectory, log_level: int):
        # вызываем конструктор базового класса
        super().__init__(
            log_prefix=BaseSecurityMonitor.log_prefix,
            queues_dir=queues_dir,
            events_q_name=BaseSecurityMonitor.event_source_name,
            event_source_name=BaseSecurityMonitor.event_source_name,
            log_level=log_level)

        # инициализируем интервал обновления
        self._recalc_interval_sec = 0.1
        self._log_message(LOG_INFO, "создан монитор безопасности")


    def _check_events_q(self):
        """_check_events_q в цикле проверим все входящие сообщения,
        выход из цикла по условию отсутствия новых сообщений
        """

        while True:
            try:
                event: Event = self._events_q.get_nowait()
            except Empty:
                # в очереди не команд на обработку,
                # выходим из цикла проверки
                break
            if not isinstance(event, Event):
                # событие неправильного типа, пропускаем
                continue

            self._log_message(LOG_DEBUG, f"получен запрос {event}")

            if self._check_event(event):
                self._proceed(event)
                

    @abstractmethod
    def _check_event(self, event: Event):
        """ проверка события на допустимость политиками безопасности """

    def _proceed(self, event: Event):
        """ отправить проверенное событие конечному получателю """
        destination_q = self._queues_dir.get_queue(event.destination)
        if destination_q is None:
            self._log_message(
                LOG_ERROR, f"ошибка обработки запроса {event}, получатель не найден")
        else:
            destination_q.put(event)
            self._log_message(
                LOG_DEBUG, f"запрос отправлен получателю {event}")


    def run(self):
        self._log_message(LOG_INFO, "старт монитора безопасности")

        while self._quit is False:
            sleep(self._recalc_interval_sec)
            self._check_events_q()
            self._check_control_q()
