from multiprocessing import Queue
from queue import Empty
from time import sleep
from typing import Optional, Tuple

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent
from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, \
    OPTICS_CONTROL_QUEUE_NAME, ORBIT_DRAWER_QUEUE_NAME, \
    SECURITY_MONITOR_QUEUE_NAME, CAMERA_QUEUE_NAME


class OpticsControl(BaseCustomProcess):
    """ Модуль управления оптической аппаратурой """
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

        self._photo_queue = []  # Очередь запросов на съемку
        self._photo_interval = 2.0  # Интервал между съемками (сек)
        self._last_photo_time = 0.0
        self._is_busy = False  # Флаг занятости камеры

        self._log_message(LOG_INFO, f"модуль управления оптикой создан")

    def _check_events_q(self):
        """ Метод проверяет наличие сообщений для данного компонента системы """
        while True:
            try:
                # Получаем сообщение из очереди
                event: Event = self._events_q.get_nowait()

                # Проверяем, что сообщение принадлежит типу Event (см. файл event_types.py)
                if not isinstance(event, Event):
                    continue

                # Проверяем вид операции и обрабатываем
                match event.operation:
                    case 'request_photo':
                        self._handle_photo_request(event)
                    case 'post_photo':
                        self._handle_post_photo(event)
                    case 'set_photo_interval':
                        self._handle_set_interval(event)
                    case 'get_status':
                        self._handle_get_status(event)
                    case _:
                        self._log_message(LOG_DEBUG, f"неизвестная операция: {event.operation}")

            except Empty:
                break

    def _check_control_q(self):
        """ Проверка управляющих команд """
        try:
            request: ControlEvent = self._control_q.get_nowait()
            self._log_message(LOG_DEBUG, f"проверяем управляющую команду: {request}")
            if not isinstance(request, ControlEvent):
                return

            match request.operation:
                case 'stop':
                    self._quit = True
                    self._log_message(LOG_INFO, "получена команда остановки")
                case 'pause':
                    self._is_busy = True
                    self._log_message(LOG_INFO, "работа приостановлена")
                case 'resume':
                    self._is_busy = False
                    self._log_message(LOG_INFO, "работа возобновлена")
                case 'clear_queue':
                    self._photo_queue.clear()
                    self._log_message(LOG_INFO, "очередь съемок очищена")
        except Empty:
            pass

    def run(self):
        self._log_message(LOG_INFO, f"модуль управления оптикой активен")

        import time
        self._last_photo_time = time.time()

        while self._quit is False:
            try:
                # Проверяем входящие сообщения
                self._check_events_q()
                self._check_control_q()

                # Обрабатываем очередь съемок, если не заняты
                if not self._is_busy and self._photo_queue:
                    current_time = time.time()
                    if current_time - self._last_photo_time >= self._photo_interval:
                        self._process_next_photo_request()

                # Небольшая пауза, чтобы не нагружать процессор
                sleep(0.1)

            except Exception as e:
                self._log_message(LOG_ERROR, f"ошибка системы контроля оптики: {e}")
                sleep(1)  # Пауза при ошибке

    def _handle_photo_request(self, event: Event):
        """Обработка запроса на съемку"""
        self._log_message(LOG_INFO, f"получен запрос на съемку от {event.source}")

        # Добавляем в очередь с приоритетом
        priority = 1  # По умолчанию обычный приоритет
        if event.extra_parameters and 'priority' in event.extra_parameters:
            priority = event.extra_parameters['priority']

        self._photo_queue.append({
            'source': event.source,
            'timestamp': event.parameters if event.parameters else None,
            'priority': priority,
            'signature': event.signature
        })

        # Сортируем по приоритету (высокий приоритет первый)
        self._photo_queue.sort(key=lambda x: x['priority'], reverse=True)

        self._log_message(LOG_DEBUG, f"запрос добавлен в очередь. Размер очереди: {len(self._photo_queue)}")

    def _handle_post_photo(self, event: Event):
        """Обработка готового снимка от камеры"""
        if event.parameters:
            lat, lon = event.parameters

            # Отправляем через монитор безопасности для проверки
            q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
            q.put(
                Event(
                    source=self._event_source_name,
                    destination=ORBIT_DRAWER_QUEUE_NAME,  # Важно: destination = ORBIT_DRAWER_QUEUE_NAME
                    operation='update_photo_map',
                    parameters=(lat, lon),
                    extra_parameters=event.extra_parameters,
                    signature=event.signature
                )
            )
            self._log_message(LOG_DEBUG, f"отправлен снимок для отображения ({lat}, {lon})")

    def _handle_set_interval(self, event: Event):
        """Установка интервала между съемками"""
        if event.parameters and isinstance(event.parameters, (int, float)):
            new_interval = float(event.parameters)
            if 0.5 <= new_interval <= 30.0:  # Разумные пределы
                old_interval = self._photo_interval
                self._photo_interval = new_interval
                self._log_message(LOG_INFO,
                                  f"интервал съемки изменен: {old_interval:.1f} -> {new_interval:.1f} сек")
            else:
                self._log_message(LOG_ERROR,
                                  f"некорректный интервал: {new_interval}. Допустимо: 0.5-30.0 сек")

    def _handle_get_status(self, event: Event):
        """Отправка статуса модуля"""
        status_event = Event(
            source=self._event_source_name,
            destination=event.source if event.source else "unknown",
            operation='optics_status',
            parameters={
                'queue_size': len(self._photo_queue),
                'is_busy': self._is_busy,
                'photo_interval': self._photo_interval,
                'last_photo_time': self._last_photo_time
            },
            signature=f"status_{self._event_source_name}"
        )

        # Отправляем ответ отправителю
        if event.source:
            try:
                q: Queue = self._queues_dir.get_queue(event.source)
                if q:
                    q.put(status_event)
                    self._log_message(LOG_DEBUG, f"отправлен статус {event.source}")
            except:
                self._log_message(LOG_ERROR, f"не удалось отправить статус {event.source}")

    def _process_next_photo_request(self):
        """Обработка следующего запроса в очереди"""
        if not self._photo_queue:
            return

        # Берем запрос с наивысшим приоритетом
        request = self._photo_queue.pop(0)

        import time
        self._last_photo_time = time.time()

        self._log_message(LOG_INFO,
                          f"обрабатываю запрос на съемку от {request['source']} (приоритет: {request['priority']})")

        # Отправляем запрос камере через монитор безопасности
        q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        q.put(
            Event(
                source=self._event_source_name,
                destination=CAMERA_QUEUE_NAME,
                operation='request_photo',
                parameters=request.get('timestamp'),
                extra_parameters={'priority': request['priority']},
                signature=request.get('signature')
            )
        )
        self._log_message(LOG_DEBUG, "запрос на снимок отправлен камере")

    def _send_photo_request(self):
        """Отправляет запрос камере на создание снимка через монитор безопасности"""
        # Этот метод оставлен для обратной совместимости
        q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        q.put(
            Event(
                source=self._event_source_name,
                destination=CAMERA_QUEUE_NAME,
                operation='request_photo',
                parameters=None
            )
        )
        self._log_message(LOG_DEBUG, "запрос на снимок отправлен камере (устаревший метод)")