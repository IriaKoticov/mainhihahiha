"""Обработчик команд, парсер программ, система прав доступа"""

import time
from dataclasses import dataclass
from typing import List, Tuple

# === КОНСТАНТЫ РОЛЕЙ ===
ROLE_CLIENT = 1
ROLE_VIP = 2
ROLE_ADMIN = 3

# === СИСТЕМА РАЗРЕШЕНИЙ ===
PERMISSIONS = {
    "MAKE PHOTO": {ROLE_CLIENT, ROLE_VIP, ROLE_ADMIN},
    "ORBIT": {ROLE_VIP, ROLE_ADMIN},
    "ADD ZONE": {ROLE_ADMIN},
    "REMOVE ZONE": {ROLE_ADMIN},
}


# === СТРУКТУРЫ ДАННЫХ ===
@dataclass
class Command:
    name: str
    args: Tuple


@dataclass
class UserContext:
    username: str
    role: int


# === ПАРСЕР ПРОГРАММ ===
def parse_program(program_file: str) -> List[Command]:
    """Чтение и разбор программы из файла"""
    commands = []

    try:
        with open(program_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Пропускаем пустые строки и комментарии
                if not line or line.startswith("#"):
                    continue

                # Разбираем команду
                parts = line.split()

                if parts[0] == "ORBIT" and len(parts) == 4:
                    commands.append(
                        Command(name="ORBIT", args=tuple(map(float, parts[1:4])))
                    )

                elif line == "MAKE PHOTO":
                    commands.append(Command(name="MAKE PHOTO", args=()))

                elif parts[0] == "ADD" and parts[1] == "ZONE" and len(parts) == 7:
                    commands.append(
                        Command(
                            name="ADD ZONE",
                            args=(
                                int(parts[2]),
                                float(parts[3]),
                                float(parts[4]),
                                float(parts[5]),
                                float(parts[6]),
                            ),
                        )
                    )

                elif parts[0] == "REMOVE" and parts[1] == "ZONE" and len(parts) == 3:
                    commands.append(Command(name="REMOVE ZONE", args=(int(parts[2]),)))

                else:
                    raise ValueError(f"Ошибка синтаксиса в строке {line_num}: {line}")

    except Exception as e:
        raise ValueError(f"Ошибка чтения файла {program_file}: {e}")

    return commands


# === ПРОВЕРКА ПРАВ ДОСТУПА ===
def check_permission(role: int, command_name: str) -> bool:
    """Проверяет, имеет ли роль право выполнять команду"""
    return role in PERMISSIONS.get(command_name, set())


def get_role_name(role: int) -> str:
    """Преобразует код роли в читаемое название"""
    role_names = {ROLE_CLIENT: "клиент", ROLE_VIP: "VIP", ROLE_ADMIN: "администратор"}
    return role_names.get(role, "неизвестная роль")


# === ИНТЕРПРЕТАТОР КОМАНД ===
class CommandInterpreter:
    """Интерпретатор и исполнитель команд"""

    def __init__(self, user_context: UserContext, logger, queues_dir):
        self.user = user_context
        self.log = logger
        self.queues_dir = queues_dir
        self.command_counter = 0

    def execute_program(self, commands: List[Command]):
        """Выполняет список команд"""
        if not commands:
            self.log.warning("Нет команд для выполнения")
            return

        self.log.info(
            f"Пользователь '{self.user.username}' начинает выполнение программы ({len(commands)} команд)"
        )

        for i, cmd in enumerate(commands, 1):
            self._execute_single_command(cmd, i)

        self.log.info("Программа выполнена успешно")

    def _execute_single_command(self, cmd: Command, sequence_num: int):
        """Выполняет одну команду с проверкой прав и логированием"""
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from src.system.event_types import Event

        self.log.info(f"Команда #{sequence_num}: {cmd.name}")

        # Проверка прав доступа
        if not check_permission(self.user.role, cmd.name):
            self.log.warning(
                f"ОТКАЗ: У пользователя '{self.user.username}' ({get_role_name(self.user.role)}) "
                f"нет прав на выполнение команды '{cmd.name}'"
            )
            return

        try:
            # Выполнение команды
            if cmd.name == "ORBIT":
                self._execute_orbit_command(cmd.args)

            elif cmd.name == "MAKE PHOTO":
                self._execute_photo_command()

            elif cmd.name == "ADD ZONE":
                self._execute_add_zone_command(cmd.args)

            elif cmd.name == "REMOVE ZONE":
                self._execute_remove_zone_command(cmd.args)

            else:
                raise ValueError(f"Неизвестная команда: {cmd.name}")

            self.log.info(f"УСПЕХ: {cmd.name} {cmd.args}")

            # Пауза между командами для стабильности
            self._pause_after_command(cmd.name)

        except Exception as e:
            self.log.error(f"ОШИБКА выполнения команды {cmd.name}: {e}")

    def _execute_orbit_command(self, args):
        """Выполняет команду ORBIT"""
        altitude, raan, inclination = args

        # Валидация параметров
        if not (160000 <= altitude <= 2000000):
            raise ValueError(f"Высота орбиты {altitude} вне диапазона 160000-2000000")

        # Отправка команды в систему
        q = self.queues_dir.get_queue('security')
        if q:
            from src.system.event_types import Event

            q.put(
                Event(
                    source=f"client_{self.user.username}",
                    destination="orbit_control",
                    operation="change_orbit",
                    parameters=(altitude, raan, inclination),
                    signature=f"orbit_{self.user.username}_{self.command_counter}",
                )
            )
            self.command_counter += 1

    def _execute_photo_command(self):
        q = self.queues_dir.get_queue("security")
        if q:
            from src.system.event_types import Event

            q.put(
                Event(
                    source=f"client_{self.user.username}",
                    destination="optics_control",
                    operation="request_photo",
                    parameters=None,
                    extra_parameters={
                        "user": self.user.username,
                        "role": self.user.role,
                        "priority": 1,
                    },
                    signature=f"photo_{self.user.username}_{self.command_counter}",
                )
            )
            self.command_counter += 1

    def _execute_add_zone_command(self, args):
        """Выполняет команду ADD ZONE"""
        zone_id, lat1, lon1, lat2, lon2 = args

        # Импортируем RestrictedZone здесь
        from src.satellite_control_system.restricted_zone import RestrictedZone

        # Создание объекта зоны
        zone = RestrictedZone(
            zone_id=zone_id,
            lat_bot_left=min(lat1, lat2),
            lon_bot_left=min(lon1, lon2),
            lat_top_right=max(lat1, lat2),
            lon_top_right=max(lon1, lon2),
            description=f"Добавлено пользователем {self.user.username}",
            severity_level=3,
        )

        # Отправка команды в систему
        q = self.queues_dir.get_queue("security")
        if q:
            from src.system.event_types import Event

            q.put(
                Event(
                    source=f"client_{self.user.username}",
                    destination="security_monitor",
                    operation="add_restricted_zone",
                    parameters=zone,
                    extra_parameters={
                        "user": self.user.username,
                        "role": self.user.role,
                    },
                    signature=f"addzone_{self.user.username}_{self.command_counter}",
                )
            )
            self.command_counter += 1

    def _execute_remove_zone_command(self, args):
        """Выполняет команду REMOVE ZONE"""
        zone_id = args[0]

        q = self.queues_dir.get_queue("security")
        if q:
            from src.system.event_types import Event

            q.put(
                Event(
                    source=f"client_{self.user.username}",
                    destination="security_monitor",
                    operation="remove_restricted_zone",
                    parameters=zone_id,
                    extra_parameters={
                        "user": self.user.username,
                        "role": self.user.role,
                    },
                    signature=f"removezone_{self.user.username}_{self.command_counter}",
                )
            )
            self.command_counter += 1

    def _pause_after_command(self, command_name: str):
        """Пауза после выполнения команды"""
        if command_name == "ADD ZONE":
            time.sleep(1.5)  # Пауза для отрисовки зоны
        elif command_name == "ORBIT":
            time.sleep(1.0)  # Пауза для изменения орбиты
        elif command_name == "MAKE PHOTO":
            time.sleep(0.5)  # Пауза для съемки
        elif command_name == "REMOVE ZONE":
            time.sleep(0.8)  # Пауза для удаления зоны
