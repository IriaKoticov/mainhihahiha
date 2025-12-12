import numpy as np
import urllib.request
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle



from multiprocessing import Queue, Process
from queue import Empty
from time import sleep
from mpl_toolkits.mplot3d import Axes3D
from PIL import Image

from src.system.custom_process import BaseCustomProcess
from src.system.queues_dir import QueuesDirectory
from src.system.event_types import Event, ControlEvent
from src.satellite_control_system.restricted_zone import RestrictedZone
from src.system.config import CRITICALITY_STR, LOG_DEBUG, \
    LOG_ERROR, LOG_INFO, DEFAULT_LOG_LEVEL, \
    ORBIT_DRAWER_QUEUE_NAME, SATELITE_QUEUE_NAME


class OrbitDrawer(BaseCustomProcess):
    log_prefix = "[DRAWER]"
    event_source_name = ORBIT_DRAWER_QUEUE_NAME
    events_q_name = event_source_name

    """ Класс для вывода рисунка орбиты спутника """
    def __init__(
        self,
        queues_dir : QueuesDirectory,
        log_level : int = DEFAULT_LOG_LEVEL
    ):
        super().__init__(
            log_prefix=OrbitDrawer.log_prefix,
            queues_dir=queues_dir,
            events_q_name=OrbitDrawer.events_q_name,
            event_source_name=OrbitDrawer.event_source_name,
            log_level=log_level)

        # Set up figure
        self._num_frames = 50
        self._positions = []
        self._fig, self._ax = plt.subplots(figsize=(10, 5))

        world_map_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Equirectangular_projection_SW.jpg/1920px-Equirectangular_projection_SW.jpg"
        world_map_path = "./src/satellite_simulator/Earth.jpg"

        try:
            with urllib.request.urlopen(world_map_url) as url_obj:
                world_map = np.array(Image.open(url_obj))
        except Exception as e:
            self._log_message(LOG_INFO, "Не удалось скачать карту земли по ссылке, загружаю локальную копию.")
            world_map = np.array(Image.open(world_map_path))

        self._ax.imshow(world_map, extent=[-180, 180, -90, 90])
        self._trajectory, =  self._ax.plot([], [], 'ro-', markersize=7, linewidth=5)

        self._camera_coords = []
        self._photos, = self._ax.plot([], [], marker='*', markersize=15, linestyle='None', c='yellow')

        self._restricted_zone_patches = {}

        self._log_message(LOG_INFO, f"отрисовщик создан")


    def _check_events_q(self):
        while True:
            try:
                event: Event = self._events_q.get_nowait()

                if not isinstance(event, Event):
                    return

                match(event.operation):
                    case 'update_orbit_data':
                        lat, lon = event.parameters
                        self._append_positions(lat, lon)
                    case 'update_photo_map':
                        lat, lon = event.parameters
                        self._append_photos(lat, lon)
                    case 'draw_restricted_zone':
                        zone : RestrictedZone = event.parameters
                        self._append_restricted_zones(zone)
                    case 'clear_restricted_zone':
                        zone_id : int = event.parameters
                        self._remove_restricted_zone(zone_id)

            except Empty:
                break


    def _append_positions(self, lat, lon):
        if self._positions and abs(lon - self._positions[-1][0]) > 180:
            self._positions.clear()
        self._positions.append((lon, lat))
        lons, lats = zip(*self._positions)
        self._trajectory.set_data(lons, lats)


    def _append_photos(self, lat, lon):
        self._camera_coords.append((lon, lat))
        lons, lats = zip(*self._camera_coords)
        self._photos.set_data(lons, lats)

    def _append_restricted_zones(self, zone: RestrictedZone):
        width = np.abs(zone.lon_top_right - zone.lon_bot_left)
        height = np.abs(zone.lat_bot_left - zone.lat_top_right)

        rect = Rectangle(
            (zone.lon_bot_left, zone.lat_bot_left),
            width,
            height,
            linewidth=2,
            edgecolor='darkred',
            facecolor='red',
            alpha=0.3
        )
        self._ax.add_patch(rect)
        self._restricted_zone_patches[zone.zone_id] = rect
        self._fig.canvas.draw_idle()  # Update canvas

    def _remove_restricted_zone(self, zone_id: int):
        zone_rect = self._restricted_zone_patches.get(zone_id)
        if zone_rect is None:
            return False

        zone_rect.remove()
        del self._restricted_zone_patches[zone_id]


    def run(self):
        def init():
            self._trajectory.set_data([], [])
            self._photos.set_data([], [])
            # self._restricted_zones.set_data([], [])
            return self._trajectory, self._photos


        def update(frame):
            q = self._queues_dir.get_queue(SATELITE_QUEUE_NAME)
            q.put(
                Event(
                    source=self._event_source_name,
                    destination=SATELITE_QUEUE_NAME,
                    operation="send_data",
                    parameters=None
                )
            )
            return self._trajectory, self._photos

        self._ani = animation.FuncAnimation(self._fig, update,  init_func=init, blit=False, interval=200, cache_frame_data=False,)
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.title("Real-time Satellite Ground Track")
        plt.ion()

        while self._quit is False:
            self._check_events_q()
            self._check_control_q()
            plt.pause(0.1)
            sleep(0.15)
