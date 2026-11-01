import pytest
from pydantic import ValidationError
from app.domain.models.station import Station


def test_station_domain_model_valid():
    station = Station(
        code="GWL",
        name="Gwalior Junction",
        latitude=26.2183,
        longitude=78.1828,
        city="Gwalior",
        state="Madhya Pradesh",
        zone="NCR"
    )
    assert station.code == "GWL"
    assert station.name == "Gwalior Junction"
    assert station.latitude == 26.2183
    assert station.longitude == 78.1828
    assert station.city == "Gwalior"


def test_station_domain_model_invalid_latitude_high():
    with pytest.raises(ValidationError) as exc_info:
        Station(
            code="GWL",
            name="Gwalior Junction",
            latitude=95.0,  # Invalid latitude (>90)
            longitude=78.1828
        )
    assert any("latitude" in err["loc"] for err in exc_info.value.errors())


def test_station_domain_model_invalid_latitude_low():
    with pytest.raises(ValidationError) as exc_info:
        Station(
            code="GWL",
            name="Gwalior Junction",
            latitude=-95.0,  # Invalid latitude (<-90)
            longitude=78.1828
        )
    assert any("latitude" in err["loc"] for err in exc_info.value.errors())


def test_station_domain_model_invalid_longitude_high():
    with pytest.raises(ValidationError) as exc_info:
        Station(
            code="GWL",
            name="Gwalior Junction",
            latitude=26.2183,
            longitude=185.0  # Invalid longitude (>180)
        )
    assert any("longitude" in err["loc"] for err in exc_info.value.errors())


def test_station_domain_model_invalid_longitude_low():
    with pytest.raises(ValidationError) as exc_info:
        Station(
            code="GWL",
            name="Gwalior Junction",
            latitude=26.2183,
            longitude=-185.0  # Invalid longitude (<-180)
        )
    assert any("longitude" in err["loc"] for err in exc_info.value.errors())


def test_station_domain_model_empty_code():
    with pytest.raises(ValidationError) as exc_info:
        Station(
            code="   ",
            name="Gwalior Junction",
            latitude=26.2183,
            longitude=78.1828
        )
    assert any("code" in err["loc"] for err in exc_info.value.errors())


def test_station_domain_model_empty_name():
    with pytest.raises(ValidationError) as exc_info:
        Station(
            code="GWL",
            name="",
            latitude=26.2183,
            longitude=78.1828
        )
    assert any("name" in err["loc"] for err in exc_info.value.errors())
