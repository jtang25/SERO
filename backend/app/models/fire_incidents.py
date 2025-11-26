from sqlalchemy import Column, BigInteger, Text, DateTime, Float
from ..db import Base


class FireIncident(Base):
    __tablename__ = "fire_incidents"

    id = Column(BigInteger, primary_key=True, index=True)
    incident_number = Column(Text, unique=True, index=True, nullable=False)

    call_type = Column(Text)
    call_description = Column(Text)
    priority = Column(Text)

    # Dispatch / incident timestamp
    ts = Column(DateTime(timezone=True), index=True, nullable=False)

    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
