from sqlalchemy import String, Integer, Time, Numeric, ForeignKey, UniqueConstraint, ARRAY, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import time, datetime
from typing import Optional, List
from app.infrastructure.database.models.base import Base

class TrainORM(Base):
    __tablename__ = "trains"

    number: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    origin_code: Mapped[str] = mapped_column(String(10), ForeignKey("stations.code"), nullable=False)
    destination_code: Mapped[str] = mapped_column(String(10), ForeignKey("stations.code"), nullable=False)
    runs_on_days: Mapped[List[int]] = mapped_column(ARRAY(Integer), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    schedules: Mapped[List["ScheduleORM"]] = relationship(
        "ScheduleORM",
        back_populates="train",
        cascade="all, delete-orphan",
        order_by="ScheduleORM.stop_sequence"
    )

class ScheduleORM(Base):
    __tablename__ = "train_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    train_number: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("trains.number", ondelete="CASCADE"),
        nullable=False
    )
    station_code: Mapped[str] = mapped_column(String(10), ForeignKey("stations.code"), nullable=False)
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    departure_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    day_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    distance_km: Mapped[float] = mapped_column(Numeric(7, 2), default=0.0, nullable=False)

    train: Mapped["TrainORM"] = relationship("TrainORM", back_populates="schedules")

    __table_args__ = (
        UniqueConstraint("train_number", "stop_sequence", name="uq_train_stop_sequence"),
    )
