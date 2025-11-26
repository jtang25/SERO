from sqlalchemy import Column, Integer, Float
from ..db import Base


class GridCell(Base):
    __tablename__ = "grid_cells"

    id = Column(Integer, primary_key=True, index=True)

    # Logical ID for the cell (row * n_lon + col); kept unique
    cell_id = Column(Integer, unique=True, index=True, nullable=False)

    centroid_lat = Column(Float, nullable=False)
    centroid_lon = Column(Float, nullable=False)
