import numpy as np

from multiprocessing import Queue, Process
from queue import Empty
from time import sleep

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent
from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, \
    SATELITE_QUEUE_NAME, CAMERA_QUEUE_NAME, ORBIT_DRAWER_QUEUE_NAME



G = 6.67430e-11  # Gravitational constant (m^3 kg^-1 s^-2)
EARTH_MASS = 5.972e24  # kg
EARTH_RADIUS = 6.371e6  # m

class Satellite(BaseCustomProcess):
    """ Симулятор спутника """
    log_prefix = "[SAT]"
    event_source_name = SATELITE_QUEUE_NAME
    events_q_name = event_source_name
    orbit_change_coef = 1 / 10e5

    def __init__(
        self,
        altitude: float,
        position_angle: float,
        inclination: float,
        raan: float,
        queues_dir: QueuesDirectory,
        log_level: int = DEFAULT_LOG_LEVEL
    ):
        super().__init__(
            log_prefix=Satellite.log_prefix,
            queues_dir=queues_dir,
            events_q_name=Satellite.events_q_name,
            event_source_name=Satellite.event_source_name,
            log_level=log_level)

        self._altitude = altitude
        self._radius = EARTH_RADIUS + altitude
        self._inclination = inclination
        self._raan = raan
        self._position_angle = position_angle
        
        #  Расчет начальной позиции
        self._position = self._compute_position(
            self._radius, 
            self._raan, 
            self._position_angle, 
            self._inclination)

        # Расчет начальной скорости
        self._velocity = self._compute_velocity(
            self._radius, 
            self._raan, 
            self._position_angle, 
            self._inclination)
        
        self._recalc_interval_sec = 0.1 # Время пересчета координат (сек.)
        self._time_speed_sec = 30 # Время пересчета координат (сек.), время прошедшее для спутника
        self._log_message(LOG_INFO, f"симулятор создан")


    def _compute_position(
            self, 
            radius: float, 
            raan: float, 
            position_angle: float, 
            inclination: float):
        # Поворот начальной позиции, RAAN (Right Ascension of Ascending Node)
        cos_raan, sin_raan = np.cos(raan), np.sin(raan)
        return np.array([
            radius * (cos_raan * np.cos(position_angle) - sin_raan * np.sin(position_angle) * np.cos(inclination)),
            radius * (sin_raan * np.cos(position_angle) + cos_raan * np.sin(position_angle) * np.cos(inclination)),
            radius * np.sin(position_angle) * np.sin(inclination)])
    

    def _compute_velocity(
            self,
            radius: float, 
            raan: float, 
            position_angle: float, 
            inclination: float):
        # Поворот начальной позиции, RAAN (Right Ascension of Ascending Node)
        cos_raan, sin_raan = np.cos(raan), np.sin(raan)
        orbital_speed = np.sqrt(G * EARTH_MASS / radius)
        return np.array([
            -orbital_speed * (cos_raan * np.sin(position_angle) + sin_raan * np.cos(position_angle) * np.cos(inclination)),
             orbital_speed * (-sin_raan * np.sin(position_angle) + cos_raan * np.cos(position_angle) * np.cos(inclination)),
             orbital_speed * np.cos(position_angle) * np.sin(inclination)
        ])
    

    def _change_orbit(
            self, 
            new_altitude: float, 
            new_inclination: float,
            new_raan: float):
        """ Меняет орбиту спутника на новую.
            Новая позиция спутника -- ближайшая точка на новой орбите"""

        new_radius = EARTH_RADIUS + new_altitude
        current_pos = self._position

        # Поиск ближайшей позиции на новой траектории
        angles = np.linspace(0, 2 * np.pi, 360)
        positions = np.array([self._compute_position(new_radius, new_raan, a, new_inclination) for a in angles])
        distances = np.linalg.norm(positions - current_pos, axis=1)
        best_idx = np.argmin(distances)
        best_angle = angles[best_idx]
        closest_position = positions[best_idx]

        # Расчет новой скорости
        new_velocity = self._compute_velocity(new_radius, new_raan, best_angle, new_inclination)

        # Сохранение новых параметров
        self._altitude = new_altitude
        self._radius = new_radius
        self._raan = new_raan
        self._inclination = new_inclination
        self._position_angle = best_angle
        self._position = closest_position
        self._velocity = new_velocity
        self._log_message(LOG_INFO, f"орбита изменена: alt={new_altitude}, RAAN={new_raan}, incl={new_inclination}")
        
        return distances[best_idx]


    def _update_position(self, dt):
        """ Обновление позиции и скорости спутника """
        r = np.linalg.norm(self._position)
        acceleration = -G * EARTH_MASS / r**3 * self._position

        # Velocity Verlet itegration
        self._position += self._velocity * dt + 0.5 * acceleration * dt**2
        new_r = np.linalg.norm(self._position)
        new_acceleration = -G * EARTH_MASS / new_r**3 * self._position
        self._velocity += 0.5 * (acceleration + new_acceleration) * dt


    def get_earth_coordinates(self):
        """ Координаты, на которые смотрит камера спутника, направленная в центр земли """
        lat = np.degrees(np.arcsin(self._position[2] / np.linalg.norm(self._position)))
        lon = np.degrees(np.arctan2(self._position[1], self._position[0]))
        return lat, lon


    def _check_events_q(self):
        """ Проверка наличия команд """
        while True:
            try:
                event: Event = self._events_q.get_nowait()

                if not isinstance(event, Event):
                    return
                
                match event.operation:
                    case 'send_data':
                        q: Queue = self._queues_dir.get_queue(ORBIT_DRAWER_QUEUE_NAME)
                        lat, lon = self.get_earth_coordinates()
                        q.put(
                            Event(
                                source=self.event_source_name, 
                                destination=ORBIT_DRAWER_QUEUE_NAME, 
                                operation='update_orbit_data', 
                                parameters=(lat, lon)))
                    case 'change_orbit':
                        new_altitude, new_inclination, new_raan = event.parameters
                        distance = self._change_orbit(new_altitude, new_inclination, new_raan)
                        time_spent = distance * self.orbit_change_coef
                        sleep(time_spent) # переходим к новой орбите
                        self._log_message(LOG_DEBUG, f"произошел переход на новую орбиту, переход занял {time_spent} сек.")
                    case 'post_camera_coords':
                        lat, lon = self.get_earth_coordinates()
                        request = Event(
                            source=self._event_source_name,
                            destination=CAMERA_QUEUE_NAME,
                            operation="camera_update",
                            parameters=(lat, lon))
                        camera_q: Queue = self._queues_dir.get_queue(CAMERA_QUEUE_NAME)
                        camera_q.put(request)
                        self._log_message(LOG_DEBUG, "обработан запрос на снимок")

            except Empty:
                break



    def run(self):
        self._log_message(LOG_INFO, f"старт симуляции спутника")

        while self._quit is False:
            self._update_position(self._time_speed_sec)
            self._check_events_q() # Вызываем метод базового класса для контроля управляющий команд
            self._check_control_q()
            # self._log_message(LOG_DEBUG, f"позиция спутника {self._position}")            
            

            sleep(self._recalc_interval_sec)