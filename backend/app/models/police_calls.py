from sqlalchemy import Column, BigInteger, Text, DateTime, Float
from ..db import Base


class PoliceCall(Base):
    __tablename__ = "police_calls"

    id = Column(BigInteger, primary_key=True, index=True)
    cad_event_number = Column(Text, unique=True, index=True, nullable=False)

    initial_call_type = Column(Text)
    final_call_type = Column(Text)
    priority = Column(Text)

    # Event / clearance timestamp
    ts = Column(DateTime(timezone=True), index=True, nullable=False)

    beat = Column(Text, index=True)

    # Optional – you can keep these null and later fill from beat centroids
    latitude = Column(Float)
    longitude = Column(Float)
