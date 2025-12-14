from system.custom_process import BaseCustomProcess
from system.config import DATABASE_QUEUE_NAME, DEFAULT_LOG_LEVEL, LOG_INFO, LOG_ERROR
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event
from queue import Empty
import os
import struct


RECORD_HEADER = struct.Struct("<I")
RECORD_BODY   = struct.Struct("<Idd")


class Database(BaseCustomProcess)
    log_prefix = "[DATABASE]"
    event_source_name = DATABASE_QUEUE_NAME
    events_q_name = event_source_name
    filename = ""
    def __init__(self, filename_f:str, queues_dir: QueuesDirector,log_level: int = DEFAULT_LOG_LEVEL):
        super().__init__(
            log_prefix=Database.log_prefix,
        queues_dir=queues_dir,
        events_q_name=Database.event_source_name,
        event_source_name=Database.event_source_name,
        log_level=log_level
        )
        self.filename = filename_f
        self.i = self._load_last_index()

    def run(self):
        self._log_message(LOG_INFO, f"модуль баз данных активен")

        while self._quit is False:
            try:
                self._check_events_q()
                self._check_control_q()
            except Exception as e:
                self._log_message(LOG_ERROR, f"ошибка модуля баз данных: {e}")



    def _check_events_q(self):
        while True:
            try:
                # Получаем сообщение из очереди
                event: Event = self._events_q.get_nowait()

                # Проверяем, что сообщение принадлежит типу Event (см. файл event_types.py)
                if not isinstance(event, Event):
                    return

                # Проверяем вид операции и обрабатываем
                match event.operation:
                    case 'add_photo':
                        lat, lon = event.parameters
                        self._write(lat, lon)
                        self._log_message(LOG_INFO, f"снимок cохранен ({lat}, {lon})")

            except Empty:
                break

    def _load_last_index(self) -> int:
        if not os.path.exists(self.filename):
            return 0

        last_i = 0
        with open(self.filename, "rb") as f:
            while True:
                header = f.read(RECORD_HEADER.size)
                if not header:
                    break

                (name_len,) = RECORD_HEADER.unpack(header)
                f.read(name_len)  # photo{i}

                body = f.read(RECORD_BODY.size)
                if not body:
                    break

                i, _, _ = RECORD_BODY.unpack(body)
                last_i = i

        return last_i + 1

    def _write(self, lat: float, lon: float):
            name = f"photo{self.i}".encode("utf-8")

            with open(self.filename, "ab") as f:
                f.write(RECORD_HEADER.pack(len(name)))
                f.write(name)
                f.write(RECORD_BODY.pack(self.i, lat, lon))

            print(f"Saved photo{self.i} ({lat}, {lon})")
            self.i += 1
