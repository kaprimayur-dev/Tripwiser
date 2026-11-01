import pytest
import datetime
from pydantic import ValidationError
from app.domain.models.availability import AvailabilityStatusCode, AvailabilityResult


def test_availability_status_enum_all_approved_states():
    approved_states = [
        "AVAILABLE",
        "RAC",
        "WAITLIST",
        "NOT_AVAILABLE",
        "CHARTING_PENDING",
        "PROVIDER_ERROR",
        "STALE",
    ]
    for state_str in approved_states:
        enum_val = AvailabilityStatusCode(state_str)
        assert enum_val.value == state_str

    assert len(AvailabilityStatusCode) == 7


def test_availability_result_valid():
    now = datetime.datetime.now()
    res = AvailabilityResult(
        status=AvailabilityStatusCode.AVAILABLE,
        available_count=24,
        quota="GN",
        travel_class="3A",
        fare=750.0,
        checked_at=now,
        source="mock"
    )
    assert res.status == AvailabilityStatusCode.AVAILABLE
    assert res.available_count == 24
    assert res.fare == 750.0
    assert res.checked_at == now


def test_availability_result_invalid_status_enum():
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        AvailabilityResult(
            status="CONFIRMED",  # Not in AvailabilityStatusCode
            available_count=24,
            fare=750.0,
            checked_at=now
        )
    assert any("status" in err["loc"] for err in exc_info.value.errors())


def test_availability_result_negative_fare():
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        AvailabilityResult(
            status=AvailabilityStatusCode.AVAILABLE,
            available_count=10,
            fare=-50.0,  # Negative fare
            checked_at=now
        )
    assert any("fare" in err["loc"] for err in exc_info.value.errors())


def test_availability_result_negative_available_count():
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        AvailabilityResult(
            status=AvailabilityStatusCode.AVAILABLE,
            available_count=-5,  # Negative count
            fare=500.0,
            checked_at=now
        )
    assert any("available_count" in err["loc"] for err in exc_info.value.errors())


def test_availability_result_negative_waitlist_count():
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        AvailabilityResult(
            status=AvailabilityStatusCode.WAITLIST,
            waitlist_count=-1,  # Negative count
            fare=500.0,
            checked_at=now
        )
    assert any("waitlist_count" in err["loc"] for err in exc_info.value.errors())


def test_availability_result_empty_quota():
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        AvailabilityResult(
            status=AvailabilityStatusCode.AVAILABLE,
            quota="",
            fare=500.0,
            checked_at=now
        )
    assert any("quota" in err["loc"] for err in exc_info.value.errors())
