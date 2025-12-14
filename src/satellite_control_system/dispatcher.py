from queue import Empty, Queue

from src.system.config import (
    DATABASE_QUEUE_NAME,
    DEFAULT_LOG_LEVEL,
    DISPATCHER_QUEUE_NAME,
    LOG_INFO,
    OPTICS_CONTROL_QUEUE_NAME,
    ORBIT_CONTROL_QUEUE_NAME,
)
from src.system.custom_process import BaseCustomProcess
from src.system.event_types import Event
from src.system.queues_dir import QueuesDirectory


class Dispatcher(BaseCustomProcess):
    log_prefix = "[DISPATH]"
    event_source_name = DISPATCHER_QUEUE_NAME
    events_q_name = event_source_name

    def __init__(self, queues_dir: QueuesDirectory, log_level: int = DEFAULT_LOG_LEVEL):
        super().__init__(
            log_prefix=Dispatcher.log_prefix,
            queues_dir=queues_dir,
            events_q_name=Dispatcher.event_source_name,
            event_source_name=Dispatcher.event_source_name,
            log_level=log_level,
        )

    def _check_events_q(self):
        while True:
            try:
                # Получаем сообщение из очереди
                event: Event = self._events_q.get_nowait()

                # Проверяем, что сообщение принадлежит типу Event (см. файл event_types.py)
                if not isinstance(event, Event):
                    return

                # Проверяем вид операции и обрабатываем
                match event.operation:
                    case "req_add_photo_to_data_base":
                        lat, lon = event.parameters
                        q: Queue = self._queues_dir.get_queue(DATABASE_QUEUE_NAME)
                        q.put(
                            Event(
                                source=self.events_q_name,
                                destination=event.destination,
                                operation="add_photo",
                                parameters=(lat, lon),
                            )
                        )
                        self._log_message(LOG_INFO, f"снимок cохранен ({lat}, {lon})")

                    case "req_to_swich_orbit":
                        pass
                    case "req_to_take_photo":
                        pass
                    case "resp_with_photo":
                        pass
                    case "resp_with_state_satellite":
                        pass
                    case "resp_feedback":
                        pass
            except Empty:
                break
