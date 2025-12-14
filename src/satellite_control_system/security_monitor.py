# Новый файл: src/satellite_control_system/security_monitor.py
"""Монитор безопасности с проверкой запретных зон"""
from multiprocessing import Queue
from time import sleep
from queue import Empty

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent
from src.system.config import LOG_ERROR, LOG_DEBUG, LOG_INFO, DEFAULT_LOG_LEVEL, \
    SECURITY_MONITOR_QUEUE_NAME, ORBIT_DRAWER_QUEUE_NAME, OPTICS_CONTROL_QUEUE_NAME
from src.system.security_policy_type import SecurityPolicy
from src.satellite_control_system.restricted_zone import RestrictedZone


class SecurityMonitor(BaseCustomProcess):
    """Монитор безопасности с проверкой запретных зон"""

    log_prefix = "[SECURITY]"
    event_source_name = SECURITY_MONITOR_QUEUE_NAME
    events_q_name = event_source_name

    def __init__(self, queues_dir: QueuesDirectory, log_level: int = DEFAULT_LOG_LEVEL):
        super().__init__(
            log_prefix=self.log_prefix,
            queues_dir=queues_dir,
            events_q_name=self.events_q_name,
            event_source_name=self.event_source_name,
            log_level=log_level
        )

        # Политики безопасности
        self._security_policies = [
            SecurityPolicy(source="*", destination="*", operation="*"),
        ]

        # Запретные зоны
        self._restricted_zones = {}

        # Счетчик нарушений
        self._violations = {}

        # Интервал обновления
        self._recalc_interval_sec = 0.1

        self._log_message(LOG_INFO, "Монитор безопасности создан")

    def _check_event(self, event: Event) -> bool:
        """Проверка события на соответствие политикам безопасности"""
        # Проверяем только операции съемки на наличие в запретных зонах
        if event.destination == ORBIT_DRAWER_QUEUE_NAME and event.operation == 'update_photo_map':
            if event.parameters and isinstance(event.parameters, (tuple, list)) and len(event.parameters) >= 2:
                lat, lon = event.parameters[0], event.parameters[1]

                for zone in self._restricted_zones.values():
                    if zone.contains(lat, lon):
                        user = event.extra_parameters.get('user', 'unknown') if event.extra_parameters else 'unknown'
                        self._log_message(LOG_ERROR,
                                          f"НАРУШЕНИЕ: Пользователь {user} сделал снимок в запретной зоне {zone.zone_id}")
                        return False

        return True

    def _proceed(self, event: Event):
        """Обработка разрешенного события"""
        # Обработка команд управления зонами
        if event.operation == 'add_restricted_zone':
            zone = event.parameters
            if isinstance(zone, RestrictedZone):
                self._restricted_zones[zone.zone_id] = zone
                self._log_message(LOG_INFO, f"Добавлена запретная зона {zone.zone_id}")

                # Отправка зоны в отрисовщик
                q: Queue = self._queues_dir.get_queue(ORBIT_DRAWER_QUEUE_NAME)
                if q:
                    q.put(Event(
                        source=self._event_source_name,
                        destination=ORBIT_DRAWER_QUEUE_NAME,
                        operation='draw_restricted_zone',
                        parameters=zone
                    ))

        elif event.operation == 'remove_restricted_zone':
            zone_id = event.parameters
            if zone_id in self._restricted_zones:
                del self._restricted_zones[zone_id]
                self._log_message(LOG_INFO, f"Удалена запретная зона {zone_id}")

                # Удаление зоны из отрисовщика
                q: Queue = self._queues_dir.get_queue(ORBIT_DRAWER_QUEUE_NAME)
                if q:
                    q.put(Event(
                        source=self._event_source_name,
                        destination=ORBIT_DRAWER_QUEUE_NAME,
                        operation='clear_restricted_zone',
                        parameters=zone_id
                    ))

        else:
            # Стандартная обработка
            destination_q = self._queues_dir.get_queue(event.destination)
            if destination_q is None:
                self._log_message(LOG_ERROR, f"Получатель не найден: {event.destination}")
            else:
                destination_q.put(event)
                self._log_message(LOG_DEBUG, f"Событие отправлено: {event.operation}")

    def _check_events_q(self):
        """Проверка входящих событий"""
        while True:
            try:
                event: Event = self._events_q.get_nowait()

                if not isinstance(event, Event):
                    continue

                self._log_message(LOG_DEBUG, f"Получено событие: {event.operation}")

                if self._check_event(event):
                    self._proceed(event)

            except Empty:
                break

    def run(self):
        """Основной цикл монитора безопасности"""
        self._log_message(LOG_INFO, "Монитор безопасности запущен")

        while not self._quit:
            self._check_events_q()
            self._check_control_q()
            sleep(self._recalc_interval_sec)

    def stop(self):
        """Остановка монитора"""
        self._quit = True