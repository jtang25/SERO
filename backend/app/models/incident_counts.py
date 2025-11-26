from sqlalchemy import Column, BigInteger, Integer, DateTime, UniqueConstraint
from ..db import Base


class IncidentCount(Base):
    __tablename__ = "incident_counts"

    id = Column(BigInteger, primary_key=True, index=True)

    cell_id = Column(Integer, nullable=False, index=True)
    bucket_start = Column(DateTime(timezone=True), nullable=False, index=True)

    fire_count = Column(Integer, nullable=False, default=0)
    police_count = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint(
            "cell_id",
            "bucket_start",
            name="uc_incident_counts_cell_bucket",
        ),
    )
