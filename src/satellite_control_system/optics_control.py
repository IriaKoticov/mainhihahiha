from multiprocessing import Queue
from queue import Empty

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event
from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, \
    OPTICS_CONTROL_QUEUE_NAME, ORBIT_DRAWER_QUEUE_NAME

class OpticsControl(BaseCustomProcess):
    """ Модуль управления потической аппаратурой """
    log_prefix = "[OPTIC]"
    event_source_name = OPTICS_CONTROL_QUEUE_NAME
    events_q_name = event_source_name

    def __init__(
        self,
        queues_dir: QueuesDirectory,
        log_level: int = DEFAULT_LOG_LEVEL
    ):
        super().__init__(
            log_prefix=OpticsControl.log_prefix,
            queues_dir=queues_dir,
            events_q_name=OpticsControl.event_source_name,
            event_source_name=OpticsControl.event_source_name,
            log_level=log_level)

        self._log_message(LOG_INFO, f"модуль управления оптикой создан")


    def _check_events_q(self):
        """ Метод проверяет наличие сообщений для данного компонента системы """
        while True:
            try:
                # Получаем сообщение из очереди
                event: Event = self._events_q.get_nowait()

                # Проверяем, что сообщение принадлежит типу Event (см. файл event_types.py)
                if not isinstance(event, Event):
                    return
                
                # Проверяем вид операции и обрабатываем
                match event.operation:
                    case 'request_photo':
                        self._send_photo_request()
                    case 'post_photo':
                        # Запрос на отрисовку снимка на карте
                        q: Queue = self._queues_dir.get_queue(ORBIT_DRAWER_QUEUE_NAME)
                        lat, lon = event.parameters
                        q.put(
                            Event(
                                source=self._event_source_name, 
                                destination=ORBIT_DRAWER_QUEUE_NAME, 
                                operation='update_photo_map', 
                                parameters=(lat, lon)))
                        self._log_message(LOG_DEBUG, f"рисуем снимок ({lat}, {lon})")

            except Empty:
                break

    
    def run(self):
        self._log_message(LOG_INFO, f"модуль управления оптикой активен")

        while self._quit is False:
            try:
                self._check_events_q()
                self._check_control_q()
            except Exception as e:
                self._log_message(LOG_ERROR, f"ошибка системы контроля оптики: {e}")

    
    def _send_photo_request(self):
        pass
        # Реализуйте функционал контроля оптики