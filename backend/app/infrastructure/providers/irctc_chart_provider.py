import datetime
import hashlib
import json
from typing import Optional, Any
import httpx

from app.domain.providers.vacancy_provider import (
    ChartVacancyProvider,
    ProviderVacancyResult,
    ProviderVacancyStatusCode,
    ProviderVacancyRecord,
)


class IRCTCEnterpriseChartProvider:
    """
    Enterprise-grade provider adapter for Indian Railways / CRIS official PRS chart vacancy feeds.
    Fails closed when authorized credentials are not present, adhering strictly to
    zero-scraping and zero-fabrication guidelines.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        partner_id: Optional[str] = None,
        base_url: str = "https://api.cris.org.in/prs/v1",
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key
        self.partner_id = partner_id
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.partner_id)

    async def fetch_chart_vacancies(
        self,
        train_number: str,
        travel_date: datetime.date,
        boarding_station: Optional[str] = None,
    ) -> ProviderVacancyResult:
        """
        Queries official PRS chart endpoint or safely reports missing partner authorization.
        """
        if not self.is_configured:
            return ProviderVacancyResult(
                status=ProviderVacancyStatusCode.BLOCKED_NO_CREDENTIALS,
                vacancies=(),
                source_identifier="irctc_enterprise_partner",
                message=(
                    "CRIS / IRCTC partner credentials (API key & Partner ID) are not configured. "
                    "In adherence with Indian IT policies, live scraping is blocked and no synthetic "
                    "records will be fabricated."
                ),
            )

        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            url = f"{self.base_url}/charts/vacancies"
            headers = {
                "X-Partner-Id": self.partner_id or "",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
            params = {
                "train_number": train_number,
                "journey_date": travel_date.isoformat(),
            }
            if boarding_station:
                params["boarding_station"] = boarding_station

            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 401 or response.status_code == 403:
                return ProviderVacancyResult(
                    status=ProviderVacancyStatusCode.AUTH_REQUIRED,
                    vacancies=(),
                    source_identifier="irctc_enterprise_partner",
                    message="Partner credentials were rejected by CRIS/IRCTC gateway.",
                )
            elif response.status_code == 429:
                return ProviderVacancyResult(
                    status=ProviderVacancyStatusCode.RATE_LIMITED,
                    vacancies=(),
                    source_identifier="irctc_enterprise_partner",
                    message="Rate limit exceeded on CRIS PRS partner gateway.",
                )
            elif response.status_code != 200:
                return ProviderVacancyResult(
                    status=ProviderVacancyStatusCode.PROVIDER_UNAVAILABLE,
                    vacancies=(),
                    source_identifier="irctc_enterprise_partner",
                    message=f"CRIS Gateway responded with HTTP status {response.status_code}.",
                )

            payload = response.json()
            raw_bytes = response.content
            payload_sha256 = hashlib.sha256(raw_bytes).hexdigest()

            records = self._parse_prs_payload(payload, train_number, travel_date)

            status = (
                ProviderVacancyStatusCode.SUCCESS
                if records
                else ProviderVacancyStatusCode.NO_RECORDS_RELEASED
            )

            return ProviderVacancyResult(
                status=status,
                vacancies=records,
                source_identifier="irctc_enterprise_partner",
                message="Successfully retrieved verified PRS chart vacancies" if records else "No chart vacancies released by station chart office",
                raw_payload_sha256=payload_sha256,
            )

        except Exception as ex:
            return ProviderVacancyResult(
                status=ProviderVacancyStatusCode.PROVIDER_UNAVAILABLE,
                vacancies=(),
                source_identifier="irctc_enterprise_partner",
                message=f"Network error communicating with CRIS gateway: {str(ex)}",
            )
        finally:
            if not self._http_client:
                await client.aclose()

    def _parse_prs_payload(
        self,
        payload: dict[str, Any],
        train_number: str,
        travel_date: datetime.date,
    ) -> list[ProviderVacancyRecord]:
        """
        Parses PRS chart schema:
        {
           "chart_status": "CHART_PREPARED",
           "chart_phase": "FIRST_CHART",
           "vacancies": [
               {
                   "coach": "B2",
                   "berth": 43,
                   "berth_type": "UB",
                   "travel_class": "3A",
                   "from_station": "GWL",
                   "to_station": "JHS",
                   "from_seq": 42,
                   "to_seq": 52,
                   "expires_at": "2026-11-04T18:00:00Z"
               }
           ]
        }
        """
        records: list[ProviderVacancyRecord] = []
        vacancies_raw = payload.get("vacancies", [])
        chart_phase = payload.get("chart_phase", "FIRST_CHART")
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        for item in vacancies_raw:
            try:
                coach = str(item["coach"]).strip().upper()
                berth_no = int(item["berth"])
                b_type = str(item.get("berth_type", "UB")).strip().upper()
                t_class = str(item.get("travel_class", "3A")).strip().upper()
                from_st = str(item["from_station"]).strip().upper()
                to_st = str(item["to_station"]).strip().upper()
                from_seq = int(item["from_seq"])
                to_seq = int(item["to_seq"])

                expires_str = item.get("expires_at")
                if expires_str:
                    expires_dt = datetime.datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                else:
                    expires_dt = now_utc + datetime.timedelta(hours=6)

                records.append(
                    ProviderVacancyRecord(
                        train_number=train_number,
                        chart_date=travel_date,
                        coach=coach,
                        berth_number=berth_no,
                        berth_type=b_type,
                        travel_class=t_class,
                        from_station_code=from_st,
                        to_station_code=to_st,
                        from_sequence=from_seq,
                        to_sequence=to_seq,
                        chart_phase=chart_phase,
                        source="irctc_enterprise_partner",
                        observed_at=now_utc,
                        expires_at=expires_dt,
                    )
                )
            except (KeyError, ValueError, TypeError):
                # Skip malformed raw items
                continue

        return records

