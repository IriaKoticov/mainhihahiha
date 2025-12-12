import numpy as np

from time import sleep
from multiprocessing import Queue

from src.satellite_simulator.satellite import Satellite
from src.satellite_simulator.orbit_drawer import OrbitDrawer
from src.satellite_simulator.camera import Camera
from src.example.my_optics_control import MyOpticsControl
from src.system.queues_dir import QueuesDirectory
from src.system.system_wrapper import SystemComponentsContainer
from src.system.event_types import Event, ControlEvent
from src.satellite_control_system.restricted_zone import RestrictedZone
from src.example.my_security_monitor import MySecurityMonitor
from src.system.security_policy_type import SecurityPolicy

from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, OPTICS_CONTROL_QUEUE_NAME, ORBIT_DRAWER_QUEUE_NAME


def setup_system(queues_dir):
    # Симулятор спутника
    sat = Satellite(
        altitude=1000e3,
        position_angle=0,
        inclination=np.pi/3,
        raan=0,
        queues_dir=queues_dir,
        log_level=LOG_DEBUG)

    # Симулятор камеры спутника
    camera = Camera(
        queues_dir=queues_dir,
        log_level=LOG_DEBUG)

    # Отрисовщик
    drawer = OrbitDrawer(
        queues_dir=queues_dir,
        log_level=LOG_DEBUG)
    
    # Модуль контроля оптики (использующий монитор безопасности вместо прямых сообщений)
    optics_control = MyOpticsControl(
        queues_dir=queues_dir,
        log_level=LOG_DEBUG)
    
    return [sat, camera, drawer, optics_control]
    


if __name__ == '__main__':
    # В предыдущем примере события свободно помещались в очереди,
    # также сами модули могли получить любое событие от кого угодно.
    # Однако, кибериммунный подход требует контроля потоком данных между
    # доменами системы. Для этого необходимо реализовать монитор безопасности,
    # который будет содержать в себе политики безопасности.
    # 
    # В папке system уже реализован базовый класс для монитора безопасности
    # и политик безопасности. Каждая политика безопасности содержит в себе 3 параметра
    # Отправитель, получатель и операция. Система должна выполнять только те операции, 
    # которые включены в разрешенные в данных политиках, и только между теми модулями, 
    # которые указаны в этой политике.
    # 
    # В этом примере используется другой модуль контроля потики, который отправляет
    # запросы не напрямую, а через монитор безопасности.

    queues_dir = QueuesDirectory()

    # Пример монитора безопасности реализован в классе MySecurityMonitor
    security_monitor = MySecurityMonitor(queues_dir=queues_dir, log_level=LOG_DEBUG, policies=[])

    
    # Создадим модули системы
    modules = setup_system(queues_dir)
    modules.append(security_monitor)

    system_components = SystemComponentsContainer(
        components=modules,
        log_level=LOG_DEBUG)
    
    # Запустим систему 
    system_components.start()
    sleep(3) # Пусть спутник немного полетает    
    
    camera_q = queues_dir.get_queue("camera")
    # Запросим снимок (запрос будет отклонен)
    camera_q.put(
        Event(
            source=None,
            destination="camera",
            operation="request_photo",
            parameters=None))
    

    sleep(3) # Пусть спутник немного полетает    
    system_components.stop() # Остановим системы
    system_components.clean() # Очистик систему



    # Теперь разрешим отправку операции update_photo_map с помощью политик безопасности
    queues_dir = QueuesDirectory()
    security_monitor = MySecurityMonitor(
        queues_dir=queues_dir, 
        log_level=LOG_DEBUG, 
        policies=[
            SecurityPolicy(
                source=OPTICS_CONTROL_QUEUE_NAME,
                destination=ORBIT_DRAWER_QUEUE_NAME,
                operation='update_photo_map'
            )
        ])
    
    # Создадим модули системы
    modules = setup_system(queues_dir)
    modules.append(security_monitor)

    system_components = SystemComponentsContainer(
        components=modules,
        log_level=LOG_DEBUG)
    
    system_components.start()
    sleep(3)

    # Сделаем снимок. Снимок будет успешно создан.
    camera_q = queues_dir.get_queue("camera")
    camera_q.put(
            Event(
                source=None,
                destination="camera",
                operation="request_photo",
                parameters=None))
    sleep(1)
    camera_q.put(
        Event(
            source=None,
            destination="camera",
            operation="request_photo",
            parameters=None))
    sleep(1)
    camera_q.put(
        Event(
            source=None,
            destination="camera",
            operation="request_photo",
            parameters=None))
    
    sleep(5)
    system_components.stop() # Остановим системы
    system_components.clean() # Очистик систему