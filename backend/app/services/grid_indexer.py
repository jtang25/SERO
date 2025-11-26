import numpy as np

class GridIndexer:
    def __init__(self, min_lat, max_lat, min_lon, max_lon, dlat, dlon):
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.min_lon = min_lon
        self.max_lon = max_lon
        self.dlat = dlat
        self.dlon = dlon
        self.n_lat = int(np.ceil((max_lat - min_lat) / dlat))
        self.n_lon = int(np.ceil((max_lon - min_lon) / dlon))

    def latlon_to_cell(self, lat, lon):
        i = int((lat - self.min_lat) / self.dlat)
        j = int((lon - self.min_lon) / self.dlon)
        if not (0 <= i < self.n_lat and 0 <= j < self.n_lon):
            return None
        return i * self.n_lon + j

    def cell_to_centroid(self, cell_id):
        i, j = divmod(cell_id, self.n_lon)
        lat = self.min_lat + (i + 0.5) * self.dlat
        lon = self.min_lon + (j + 0.5) * self.dlon
        return lat, lon
