from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Optional, Protocol, Sequence


class ProviderVacancyStatusCode(str, Enum):
    SUCCESS = "SUCCESS"
    NO_RECORDS_RELEASED = "NO_RECORDS_RELEASED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    BLOCKED_NO_CREDENTIALS = "BLOCKED_NO_CREDENTIALS"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"


@dataclass(frozen=True)
class ProviderVacancyRecord:
    """Raw or parsed vacancy record directly yielded by an external provider or dump."""
    train_number: str
    chart_date: datetime.date
    coach: str
    berth_number: int
    berth_type: str
    travel_class: str
    from_station_code: str
    to_station_code: str
    from_sequence: int
    to_sequence: int
    chart_phase: str = "FIRST_CHART"
    source: str = "irctc_prs_chart"
    observed_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    expires_at: Optional[datetime.datetime] = None


@dataclass(frozen=True)
class ProviderVacancyResult:
    """Standardized response from any chart vacancy provider."""
    status: ProviderVacancyStatusCode
    vacancies: Sequence[ProviderVacancyRecord] = ()
    source_identifier: str = "irctc_prs_chart"
    message: str = ""
    raw_payload_sha256: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == ProviderVacancyStatusCode.SUCCESS


class ChartVacancyProvider(Protocol):
    """Protocol for fetching real-time or snapshot chart vacancies from an authorized source."""

    async def fetch_chart_vacancies(
        self,
        train_number: str,
        travel_date: datetime.date,
        boarding_station: Optional[str] = None,
    ) -> ProviderVacancyResult:
        """Fetch verified chart vacancies for a train run."""
        ...

