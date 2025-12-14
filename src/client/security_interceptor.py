""" Перехватчик событий для монитора безопасности """
from multiprocessing import Queue
from queue import Empty
import time

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent
from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, \
    CAMERA_QUEUE_NAME, SECURITY_MONITOR_QUEUE_NAME, \
    OPTICS_CONTROL_QUEUE_NAME


class SecurityInterceptor(BaseCustomProcess):
    """Перехватчик событий для мониторинга безопасности"""
    log_prefix = "[INTERCEPTOR]"
    event_source_name = "security_interceptor"
    events_q_name = event_source_name

    def __init__(self, queues_dir: QueuesDirectory, log_level: int = DEFAULT_LOG_LEVEL):
        super().__init__(
            log_prefix=SecurityInterceptor.log_prefix,
            queues_dir=queues_dir,
            events_q_name=SecurityInterceptor.events_q_name,
            event_source_name=SecurityInterceptor.event_source_name,
            log_level=log_level
        )
        self._log_message(LOG_INFO, "Перехватчик безопасности создан")

    def _check_events_q(self):
        """Перехватываем события и отправляем копию в монитор безопасности"""
        while True:
            try:
                event: Event = self._events_q.get_nowait()

                if not isinstance(event, Event):
                    continue

                # Перехватываем события от камеры
                if event.source == CAMERA_QUEUE_NAME and event.operation == 'camera_update':
                    # Отправляем копию в монитор безопасности
                    security_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
                    if security_q:
                        # Создаем событие для проверки безопасности
                        check_event = Event(
                            source=self._event_source_name,
                            destination=SECURITY_MONITOR_QUEUE_NAME,
                            operation='camera_update',
                            parameters=event.parameters,
                            extra_parameters={'intercepted': True}
                        )
                        security_q.put(check_event)
                        self._log_message(LOG_DEBUG, f"Перехвачено событие камеры: {event.parameters}")

                # Пропускаем событие дальше к целевому получателю
                target_q: Queue = self._queues_dir.get_queue(event.destination)
                if target_q:
                    target_q.put(event)

            except Empty:
                break

    def run(self):
        self._log_message(LOG_INFO, "Перехватчик безопасности запущен")

        while not self._quit:
            self._check_events_q()
            self._check_control_q()
            time.sleep(0.1)