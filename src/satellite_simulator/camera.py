from multiprocessing import Queue, Process
from queue import Empty

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent
from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, \
    CAMERA_QUEUE_NAME, SATELITE_QUEUE_NAME, ORBIT_DRAWER_QUEUE_NAME, OPTICS_CONTROL_QUEUE_NAME


class Camera(BaseCustomProcess):
    """Симулятор камеры"""
    log_prefix = "[CAMERA]"
    event_source_name = CAMERA_QUEUE_NAME
    events_q_name = event_source_name

    def __init__(self,
                 queues_dir: QueuesDirectory,
                 log_level: int):
        super().__init__(
            log_prefix=Camera.log_prefix,
            queues_dir=queues_dir,
            events_q_name=Camera.events_q_name,
            event_source_name=Camera.event_source_name,
            log_level=log_level)
        self._log_message(LOG_INFO, "симулятор камеры создан")

    def _check_control_q(self):
        """ Проверка наличия управляющий команд  """
        try:
            request: ControlEvent = self._control_q.get_nowait()
            self._log_message(
                LOG_DEBUG, f"проверяем запрос {request}")
            if not isinstance(request, ControlEvent):
                return
            if request.operation == 'stop':
                self._quit = True
        except Empty:
            # никаких команд не поступило, ну и ладно
            pass

    def _check_events_q(self):
        """ Проверка наличия команд """
        while True:
            try:
                event: Event = self._events_q.get_nowait()

                if not isinstance(event, Event):
                    return
                
                match event.operation:
                    case 'request_photo':
                        request = Event(
                            source=self._event_source_name,
                            destination=SATELITE_QUEUE_NAME,
                            operation="post_camera_coords",
                            parameters=None)
                        sat_q: Queue = self._queues_dir.get_queue(SATELITE_QUEUE_NAME)
                        sat_q.put(request)
                        self._log_message(LOG_DEBUG, "запрашиваем координаты снимка")
                    case 'camera_update':
                        q: Queue = self._queues_dir.get_queue(OPTICS_CONTROL_QUEUE_NAME)
                        lat, lon = event.parameters
                        q.put(
                            Event(
                                source=self._event_source_name, 
                                destination=OPTICS_CONTROL_QUEUE_NAME, 
                                operation='post_photo', 
                                parameters=(lat, lon)))
                        self._log_message(LOG_DEBUG, f"создаем снимок ({lat}, {lon})")
            except Empty:
                break

    def run(self):
        while self._quit is False:
            self._check_events_q()
            self._check_control_q()
    

    def stop(self):
        self._control_q.put(ControlEvent(operation="stop"))