from abc import abstractmethod
from multiprocessing import Process, Queue
from queue import Empty

from src.system.event_types import Event, ControlEvent
from src.system.queues_dir import QueuesDirectory
from src.system.config import DEFAULT_LOG_LEVEL, CRITICALITY_STR, LOG_DEBUG

class BaseCustomProcess(Process):
    def __init__(
        self,
        log_prefix: str,
        queues_dir: QueuesDirectory,
        events_q_name: str,
        event_source_name: str,
        log_level: int = DEFAULT_LOG_LEVEL,
    ):
        super().__init__()

        self._queues_dir = queues_dir
        self._events_q = Queue()
        self._events_q_name = events_q_name
        self._event_source_name = event_source_name
        self.log_prefix = log_prefix
        queues_dir.register(queue=self._events_q, name=self._events_q_name)

        self.log_level = log_level
        self._control_q = Queue()

        self._quit = False
    
    def _log_message(self, criticality: int, message: str):
        """_log_message печатает сообщение заданного уровня критичности

        Args:
            criticality (int): уровень критичности
            message (str): текст сообщения
        """
        if criticality <= self.log_level:
            print(f"[{CRITICALITY_STR[criticality]}]{self.log_prefix} {message}")
    


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


    @abstractmethod
    def _check_events_q(self):
        pass

    @abstractmethod
    def run(self):
        pass

    def stop(self):
        self._control_q.put(ControlEvent(operation="stop"))