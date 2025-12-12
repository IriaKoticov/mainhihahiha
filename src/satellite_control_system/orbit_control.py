from multiprocessing import Queue
from queue import Empty

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent
from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, \
    ORBIT_CONTROL_QUEUE_NAME


class OrbitControl(BaseCustomProcess):
    """ Модуль корректировки орбиты """
    log_prefix = "[ORBIT]"
    event_source_name = ORBIT_CONTROL_QUEUE_NAME
    events_q_name = event_source_name

    def __init__(
        self,
        queues_dir: QueuesDirectory,
        log_level: int = DEFAULT_LOG_LEVEL
    ):
        super().__init__(
            log_prefix=OrbitControl.log_prefix,
            queues_dir=queues_dir,
            events_q_name=OrbitControl.event_source_name,
            event_source_name=OrbitControl.event_source_name,
            log_level=log_level)
        
        self._log_message(LOG_INFO, "модуль контроля орбиты создан")

    
    def _check_control_q(self):
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
                    case 'change_orbit':
                        # Извлекаем параметры новой орбиты
                        altitude, raan, inclination = event.parameters
                        self._log_message("Система контроля орбиты получила новые параметры")
                        self._change_orbit(altitude, raan, inclination)
            except Empty:
                break


    def run(self):
        self._log_message(LOG_INFO, f"модуль управления орбитой активен")

        while self._quit is False:
            try:
                self._check_events_q()
                self._check_control_q()
            except Exception as e:
                self._log_message(LOG_ERROR, f"ошибка модуля контроля орбиты: {e}")



    
    def _change_orbit(self, altitude, raan, inclination):
        pass
        # Реализуйте функционал смены орбиты в этом методе
