from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import date, datetime
from app.infrastructure.database.models.base import Base

class ChartVacancyORM(Base):
    __tablename__ = "chart_vacancies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4()
    )
    train_number: Mapped[str] = mapped_column(String(10), ForeignKey("trains.number"), nullable=False)
    chart_date: Mapped[date] = mapped_column(Date, nullable=False)
    coach: Mapped[str] = mapped_column(String(10), nullable=False)
    berth_number: Mapped[int] = mapped_column(Integer, nullable=False)
    berth_type: Mapped[str] = mapped_column(String(10), default="UB", nullable=False)
    travel_class: Mapped[str] = mapped_column(String(10), nullable=False)
    from_station_code: Mapped[str] = mapped_column(String(10), ForeignKey("stations.code"), nullable=False)
    to_station_code: Mapped[str] = mapped_column(String(10), ForeignKey("stations.code"), nullable=False)
    from_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    to_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="chart_feed", nullable=False)
    chart_phase: Mapped[str] = mapped_column(String(50), default="FIRST_CHART", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="VACANT", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
