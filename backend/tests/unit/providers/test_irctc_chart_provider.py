import datetime
import json
import pytest
import httpx

from app.domain.providers.vacancy_provider import ProviderVacancyStatusCode
from app.infrastructure.providers.irctc_chart_provider import IRCTCEnterpriseChartProvider


@pytest.mark.asyncio
async def test_irctc_provider_unconfigured_fails_closed():
    """Adheres to anti-scraping: unconfigured provider safely returns BLOCKED_NO_CREDENTIALS."""
    provider = IRCTCEnterpriseChartProvider()
    assert provider.is_configured is False

    res = await provider.fetch_chart_vacancies(
        train_number="12002",
        travel_date=datetime.date(2026, 11, 4),
    )
    assert res.status == ProviderVacancyStatusCode.BLOCKED_NO_CREDENTIALS
    assert len(res.vacancies) == 0
    assert "not configured" in res.message


@pytest.mark.asyncio
async def test_irctc_provider_handles_auth_failure():
    def mock_handler(request: httpx.Request):
        return httpx.Response(401, json={"error": "Invalid API token"})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.AsyncClient(transport=transport)

    provider = IRCTCEnterpriseChartProvider(
        api_key="invalid_token",
        partner_id="PARTNER_123",
        http_client=client,
    )
    assert provider.is_configured is True

    res = await provider.fetch_chart_vacancies(
        train_number="12002",
        travel_date=datetime.date(2026, 11, 4),
    )
    assert res.status == ProviderVacancyStatusCode.AUTH_REQUIRED
    assert "rejected" in res.message


@pytest.mark.asyncio
async def test_irctc_provider_parses_prs_vacancies():
    sample_payload = {
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
                "expires_at": "2026-11-04T18:00:00Z",
            },
            {
                "coach": "B3",
                "berth": 21,
                "berth_type": "MB",
                "travel_class": "3A",
                "from_station": "JHS",
                "to_station": "BPL",
                "from_seq": 52,
                "to_seq": 87,
                "expires_at": "2026-11-04T18:00:00Z",
            },
        ],
    }

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json=sample_payload)

    transport = httpx.MockTransport(mock_handler)
    client = httpx.AsyncClient(transport=transport)

    provider = IRCTCEnterpriseChartProvider(
        api_key="valid_token",
        partner_id="PARTNER_OK",
        http_client=client,
    )

    res = await provider.fetch_chart_vacancies(
        train_number="12002",
        travel_date=datetime.date(2026, 11, 4),
    )

    assert res.status == ProviderVacancyStatusCode.SUCCESS
    assert len(res.vacancies) == 2
    assert res.raw_payload_sha256 is not None

    v1 = res.vacancies[0]
    assert v1.coach == "B2"
    assert v1.berth_number == 43
    assert v1.from_station_code == "GWL"
    assert v1.to_station_code == "JHS"
    assert v1.from_sequence == 42
    assert v1.to_sequence == 52

    v2 = res.vacancies[1]
    assert v2.coach == "B3"
    assert v2.berth_number == 21
    assert v2.from_station_code == "JHS"
    assert v2.to_station_code == "BPL"

