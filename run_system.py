#!/usr/bin/env python3
"""Главный модуль запуска всей системы управления спутником"""

import asyncio
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
from src.client.auth import authorize, AuthError
from src.client.command_processor import CommandInterpreter, UserContext, parse_program
from src.client.logger import setup_logger
from src.system.config import DEFAULT_LOG_LEVEL
from src.system.queues_dir import QueuesDirectory
from src.system.system_wrapper import SystemComponentsContainer


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

            self.log.info(
                f"Авторизация успешна! Пользователь: {login}, Роль: {role_name}"
            )
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

        # 1. Монитор безопасности (первым!)
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
            log_level=self.log_level,
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
            queues_dir=self.queues_dir, log_level=self.log_level
        )
        self.components.append(orbit_control)

        # 6. Управление оптикой
        optics_control = OpticsControl(
            queues_dir=self.queues_dir, log_level=self.log_level
        )
        self.components.append(optics_control)

        # Создаем контейнер для управления компонентами
        self.container = SystemComponentsContainer(
            components=self.components, log_level=self.log_level
        )

        self.log.info("Все компоненты системы инициализированы")

    def start_system(self):
        """Запуск системы"""
        self.log.info("=" * 60)
        self.log.info("ЗАПУСК СИСТЕМЫ УПРАВЛЕНИЯ СПУТНИКОМ")
        self.log.info("=" * 60)

        # Настройка обработчика Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)

        # Запускаем все компоненты
        self.container.start()
        self.running = True

        # Задержка для стабилизации
        time.sleep(1)

        self.log.info("Система успешно запущена и готова к работе")

    def stop_system(self):
        """Остановка системы"""
        self.log.info("Остановка системы...")
        self.running = False

        if self.container:
            self.container.stop()
            self.container.clean()

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

            # 4. Загружаем программу
            program_file = "program.txt"
            if not os.path.exists(program_file):
                self.log.warning(f"Файл программы '{program_file}' не найден")
                program_file = input("Введите путь к файлу программы: ").strip()

            commands = parse_program(program_file)
            self.log.info(f"Загружена программа: {len(commands)} команд")

            if commands:
                # 5. Выполняем программу
                self.execute_program(commands)

            # 6. Ожидаем завершения работы
            self.log.info("Система работает. Нажмите Ctrl+C для остановки.")
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

    parser = argparse.ArgumentParser(description="Система управления спутником")
    parser.add_argument(
        "--log-level",
        type=int,
        default=DEFAULT_LOG_LEVEL,
        help="Уровень логирования (0-3)",
    )
    parser.add_argument(
        "--program", type=str, default="program.txt", help="Путь к файлу программы"
    )

    args = parser.parse_args()

    # Создаем систему
    system = SatelliteControlSystem(log_level=args.log_level)

    # Запускаем систему
    system.run()


if __name__ == "__main__":
    main()
