from src.system.event_types import Event
from src.system.security_monitor import BaseSecurityMonitor
from src.system.security_policy_type import SecurityPolicy
from src.system.config import LOG_DEBUG, LOG_ERROR, LOG_INFO, OPTICS_CONTROL_QUEUE_NAME, ORBIT_DRAWER_QUEUE_NAME


class MySecurityMonitor(BaseSecurityMonitor):
    """ класс монитора безопасности """

    def __init__(self, queues_dir, log_level, policies):
        super().__init__(queues_dir, log_level)
        self._security_policies = []
        self._init_security_policies(policies)
    

    def _init_security_policies(self, policies):
        """ инициализация политик безопасности """
        self._security_policies = policies
        self._log_message(LOG_INFO, f"изменение политик безопасности: {self._security_policies}")


    def _check_event(self, event: Event):
        """ проверка входящих событий """
        self._log_message(
            LOG_DEBUG, f"проверка события {event}, по умолчанию выполнение запрещено")

        authorized = False
        request = SecurityPolicy(
            source=event.source,
            destination=event.destination,
            operation=event.operation)

        if request in self._security_policies:
            self._log_message(
                LOG_DEBUG, "событие разрешено политиками, выполняем")
            authorized = True

        if authorized is False:
            self._log_message(LOG_ERROR, f"событие не разрешено политиками безопасности! {event}")
        return authorized