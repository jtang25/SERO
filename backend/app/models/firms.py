from sqlalchemy import Column, BigInteger, Text, DateTime, Float
from ..db import Base


class FirmsDetection(Base):
    __tablename__ = "firms_detections"

    id = Column(BigInteger, primary_key=True, index=True)

    # e.g. "VIIRS_SNPP_NRT"
    src = Column(Text, nullable=False)

    acq_time = Column(DateTime(timezone=True), index=True, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    brightness = Column(Float)
    confidence = Column(Text)
    frp = Column(Float)
