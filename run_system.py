#!/usr/bin/env python3
""" Главный модуль запуска всей системы управления спутником """
import sys
import os
import time
import signal

# Добавляем пути для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.system.queues_dir import QueuesDirectory
from src.system.system_wrapper import SystemComponentsContainer
from src.satellite_simulator.satellite import Satellite
from src.satellite_simulator.orbit_drawer import OrbitDrawer
from src.satellite_simulator.camera import Camera
from src.satellite_control_system.orbit_control import OrbitControl
from src.satellite_control_system.optics_control import OpticsControl
from src.satellite_control_system.security_monitor import SecurityMonitor
from src.satellite_control_system.restricted_zone import RestrictedZone
from src.client.auth import authorize, AuthError
from src.client.command_processor import CommandInterpreter, UserContext, parse_program
from src.client.logger import setup_logger
from src.system.config import DEFAULT_LOG_LEVEL
from src.system.event_types import Event


class SatelliteControlSystem:
    """Основной класс управления всей системой спутника"""

    def __init__(self, log_level=DEFAULT_LOG_LEVEL):
        self.log_level = log_level
        self.log = setup_logger()
        self.queues_dir = None
        self.container = None
        self.components = []
        self.running = False
        self.user = None
        self.role = None

    def authenticate_user(self):
        """Аутентификация пользователя"""
        try:
            login = input("Логин: ").strip()
            password = input("Пароль: ").strip()

            self.role = authorize(login, password)
            self.user = login

            # Преобразование роли в читаемый вид
            role_names = {1: "клиент", 2: "VIP", 3: "администратор"}
            role_name = role_names.get(self.role, "неизвестная роль")

            self.log.info(f"Авторизация успешна! Пользователь: {login}, Роль: {role_name}")
            return True

        except AuthError as e:
            self.log.error(f"Ошибка авторизации: {e}")
            return False
        except Exception as e:
            self.log.error(f"Ошибка: {e}")
            return False

    def setup_components(self):
        """Настройка всех компонентов системы"""
        self.log.info("\nИнициализация системы управления спутником...")

        # Создаем каталог очередей
        self.queues_dir = QueuesDirectory()

        # 1. Монитор безопасности
        security_monitor = SecurityMonitor(
            queues_dir=self.queues_dir,
            log_level=self.log_level
        )
        self.components.append(security_monitor)

        # 2. Спутник
        satellite = Satellite(
            altitude=700000,
            position_angle=0.0,
            inclination=0.1,
            raan=0.0,
            queues_dir=self.queues_dir,
            log_level=self.log_level
        )
        self.components.append(satellite)

        # 3. Визуализатор орбиты
        orbit_drawer = OrbitDrawer(
            queues_dir=self.queues_dir,
            log_level=self.log_level
        )
        self.components.append(orbit_drawer)

        # 4. Камера
        camera = Camera(
            queues_dir=self.queues_dir,
            log_level=self.log_level
        )
        self.components.append(camera)

        # 5. Управление орбитой
        orbit_control = OrbitControl(
            queues_dir=self.queues_dir,
            log_level=self.log_level
        )
        self.components.append(orbit_control)

        # 6. Управление оптикой
        optics_control = OpticsControl(
            queues_dir=self.queues_dir,
            log_level=self.log_level
        )
        self.components.append(optics_control)

        # Создаем контейнер для управления компонентами
        self.container = SystemComponentsContainer(
            components=self.components,
            log_level=self.log_level
        )

        self.log.info("Все компоненты системы инициализированы")

    def _load_default_zones(self):
        """Загружает предустановленные запретные зоны в систему"""
        try:
            self.log.info("Загрузка предустановленных запретных зон...")

            # Создаем предустановленные запретные зоны
            default_zones = [
                RestrictedZone(
                    zone_id=1001,
                    lat_bot_left=-40.0,
                    lon_bot_left=-30.0,
                    lat_top_right=-10.0,
                    lon_top_right=-10.0,
                    description="",
                    severity_level=2
                ),
                RestrictedZone(
                    zone_id=1002,
                    lat_bot_left=50.0,
                    lon_bot_left=60.0,
                    lat_top_right=55.0,
                    lon_top_right=70.0,
                    description="",
                    severity_level=1
                ),
                RestrictedZone(
                    zone_id=1003,
                    lat_bot_left=-20.0,
                    lon_bot_left=-60.0,
                    lat_top_right=-10.0,
                    lon_top_right=-40.0,
                    description="",
                    severity_level=3
                )
            ]

            security_queue_names = [
                "security",

            ]

            security_q = None
            for queue_name in security_queue_names:
                try:
                    security_q = self.queues_dir.get_queue(queue_name)
                    if security_q:
                        self.log.info(f"Найдена очередь SecurityMonitor: {queue_name}")
                        break
                except:
                    continue

            if not security_q:
                self.log.error("Не найдена очередь SecurityMonitor ни под одним из имен")
                return

            # Отправляем каждую зону в SecurityMonitor
            for zone in default_zones:
                event = Event(
                    source="system_init",
                    destination="security_monitor",
                    operation='add_restricted_zone',
                    parameters=zone,
                    extra_parameters={
                        "auto_generated": True,
                        "description": zone.description,
                        "user": "system"
                    }
                )
                security_q.put(event)


        except Exception as e:
            self.log.error(f"Ошибка загрузки предустановленных зон: {e}")
            import traceback
            traceback.print_exc()

    def start_system(self):
        """Запуск системы"""
        self.log.info("=" * 60)
        self.log.info("ЗАПУСК СИСТЕМЫ УПРАВЛЕНИЯ СПУТНИКОМ")
        self.log.info("=" * 60)

        # Настройка обработчика Ctrl+C
        signal.signal(signal.SIGINT, lambda sig, frame: self._signal_handler(sig, frame))

        # Запускаем все компоненты
        self.container.start()
        self.running = True

        # Даем время на инициализацию всех компонентов
        self.log.info("Ожидание инициализации компонентов...")
        time.sleep(3)

        # Загружаем предустановленные запретные зоны
        self._load_default_zones()

        self.log.info("Система успешно запущена и готова к работе")

    def _signal_handler(self, sig, frame):
        """Обработчик сигнала Ctrl+C"""
        self.log.info("\nПолучен сигнал завершения (Ctrl+C)")
        self.stop_system()
        sys.exit(0)

    def stop_system(self):
        """Остановка системы"""
        self.log.info("Остановка системы...")
        self.running = False

        if self.container and hasattr(self.container, 'stop'):
            try:
                self.container.stop()
                if hasattr(self.container, 'clean'):
                    self.container.clean()
            except Exception as e:
                self.log.error(f"Ошибка при остановке контейнера: {e}")

        self.log.info("Система остановлена")

    def execute_program(self, commands):
        """Выполнение программы управления"""
        if not commands:
            self.log.warning("Нет команд для выполнения")
            return

        self.log.info("=" * 60)
        self.log.info("ВЫПОЛНЕНИЕ ПРОГРАММЫ")
        self.log.info("=" * 60)

        # Создаем контекст пользователя
        user_context = UserContext(
            username=self.user,
            role=self.role
        )

        # Создаем интерпретатор команд
        interpreter = CommandInterpreter(
            user_context=user_context,
            logger=self.log,
            queues_dir=self.queues_dir
        )

        # Выполняем программу
        interpreter.execute_program(commands)

    def run(self):
        """Основной метод запуска системы"""
        try:
            # 1. Аутентификация пользователя
            if not self.authenticate_user():
                return

            # 2. Настраиваем компоненты системы
            self.setup_components()

            # 3. Запускаем систему
            self.start_system()

            # 4. Загружаем программу пользователя
            program_file = "program.txt"
            if not os.path.exists(program_file):
                self.log.warning(f"Файл программы '{program_file}' не найден")
                program_file = input("Введите путь к файлу программы: ").strip()

            commands = parse_program(program_file)
            self.log.info(f"Загружена программа: {len(commands)} команд")

            if commands:
                # 5. Выполняем программу
                self.execute_program(commands)

            while self.running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            self.log.info("Завершение работы по запросу пользователя")
        except Exception as e:
            self.log.error(f"Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_system()


def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Система управления спутником')
    parser.add_argument('--log-level', type=int, default=DEFAULT_LOG_LEVEL,
                        help='Уровень логирования (0-3)')
    parser.add_argument('--program', type=str, default='program.txt',
                        help='Путь к файлу программы')

    args = parser.parse_args()

    # Создаем систему
    system = SatelliteControlSystem(log_level=args.log_level)

    # Запускаем систему
    system.run()


if __name__ == "__main__":
    main()