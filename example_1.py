import numpy as np

from time import sleep
from multiprocessing import Queue

from src.satellite_simulator.satellite import Satellite
from src.satellite_simulator.orbit_drawer import OrbitDrawer
from src.satellite_simulator.camera import Camera
from src.satellite_control_system.optics_control import OpticsControl
from src.system.queues_dir import QueuesDirectory
from src.system.system_wrapper import SystemComponentsContainer
from src.system.event_types import Event, ControlEvent
from src.satellite_control_system.restricted_zone import RestrictedZone

from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL


if __name__ == '__main__':
    # Создаем каталог очередей. Тут будут храниться очереди запросов для модулей системы.
    # Каждый модуль имеет свою очередь и работает как независимый процесс параллельно всем
    # остальным модулям. При создании нового модуля в его конструктор помещается ссылка на
    # этот каталог, где он регистрирует свою очередь.
    #
    # В очередь помещаются объекты типа Event (см. файл event_types.py). Используйте только тип
    # Event для реализации функционала системы. Объекты этого типа содержат в себе имена отправителя
    # и получателя, название операции, а также опциональные параметры. В параметрах могут быть как
    # простые типы (строка или число), так и более сложные, например, массивы.
    queues_dir = QueuesDirectory()

    # Создадим модули системы

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

    # Модуль контроля оптики
    optics_control = OpticsControl(
        queues_dir=queues_dir,
        log_level=LOG_DEBUG)

    # SystemComponentsContainer из файла system_wrapper.py получает на вход список созданных компонентов.
    # Это сделано для удобства управления системой, в помощью метода start() можно запустить все блоки
    # системы сразу, с помощью метода stop() остановить работу, а методом clean() удалить все процессы.
    system_components = SystemComponentsContainer(
        components=[
            sat,
            camera,
            optics_control,
            drawer],
        log_level=LOG_DEBUG
    )

    # Запустим систему
    system_components.start()

    # Получим очереди для отправки запросов в модули системы
    sat_q = queues_dir.get_queue("satellite")
    camera_q = queues_dir.get_queue("camera")
    drawer_q = queues_dir.get_queue("orbit_drawer")

    sleep(5)    # Пусть спутник немного полетает

    # Через метод put() можно добавить в очередь событие для обработки.
    # В данном примере показана отрисовка зон с ограничением на работу камеры.
    # Логику работы этих зон необходимо реализовать самостоятельно, функционал
    # их отображения на карте уже реализован в классе OrbirDrawer.
    # В данном примере команды задаются извне системы, поэтому источник указан как None,
    # при использовании их внутри модулей указывайте имя соответствующего модуля.
    # Далее задается получатель, название операции и аргументы. Для работы с зонами ограничений
    # уже реализован класс RestrictedZone, изучите его описание в файле restricted_zone.py
    drawer_q.put(Event(None, 'orbit_drawer', 'draw_restricted_zone', RestrictedZone(1, 10, -10, 20, 20)))
    drawer_q.put(Event(None, 'orbit_drawer', 'draw_restricted_zone', RestrictedZone(2, 50, -100, 80, -60)))

    sleep(5)

    # Так можно задать параметры новой орбиты
    sat_q.put(Event(
        source=None,
        destination="satellite",
        operation='change_orbit',
        parameters=[900e3, np.pi/4, np.pi/3]))

    #  Подождем пока спутник летит на новую орбиту
    sleep(5)

    # Снимем ограничения с одной из зон
    drawer_q.put(Event(None, 'orbit_drawer', 'clear_restricted_zone', 1))


    # Запросим несколько снимков
    for i in range(0, 15):
        camera_q.put(
            Event(
                source=None,
                destination="camera",
                operation="request_photo",
                parameters=None))
        sleep(0.2)

    sleep(10) # Пусть спутник еще немного полетает

    system_components.stop() # Остановим системы
    system_components.clean() # Очистик систему
