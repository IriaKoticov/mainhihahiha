from dataclasses import dataclass

@dataclass
class RestrictedZone:
    """ Описание зоны на карте, в которой запрещены снимки.
        Имеет прямоугольную форму и задается двумя точками на карте
        
        (lat_bot_left, lon_bot_left) и (lat_top_right, lon_top_right) """
    lat_bot_left : float
    lon_bot_left : float
    lat_top_right : float
    lon_top_right : float

    zone_id : int

    def __init__(self, zone_id, lat_bot_left, lon_bot_left, lat_top_right, lon_top_right):
        if (lat_bot_left >= lat_top_right or lon_bot_left >= lon_top_right):
            raise Exception("Некорректные координаты зоны, первая точка должна быть выше и левее второй.")
        self.zone_id = zone_id
        self.lat_bot_left = lat_bot_left
        self.lon_bot_left = lon_bot_left
        self.lat_top_right = lat_top_right
        self.lon_top_right = lon_top_right

        