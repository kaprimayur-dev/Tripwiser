from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, Union
import json


class CalendarProvider(Protocol):
    """Protocol for resolving verified running calendar for train numbers."""

    def get_running_days(self, train_number: str) -> tuple[int, ...] | None:
        """Returns tuple of days of week (0=Mon, 6=Sun) on which train operates, or None if unknown."""
        ...


class DictCalendarProvider:
    """In-memory dictionary-backed running calendar provider."""

    def __init__(self, mapping: Mapping[str, Sequence[int]]):
        self._mapping: dict[str, tuple[int, ...]] = {
            str(k).strip(): tuple(int(d) for d in v) for k, v in mapping.items()
        }

    def get_running_days(self, train_number: str) -> tuple[int, ...] | None:
        return self._mapping.get(str(train_number).strip())


class FixtureCalendarProvider:
    """Extracts verified running calendar from bootstrap_railway_data.json."""

    def __init__(self, fixture_path: Union[str, Path]):
        self._mapping: dict[str, tuple[int, ...]] = {}
        path = Path(fixture_path)
        if path.exists() and path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for t in data.get("trains", []):
                num = str(t.get("number") or "").strip()
                days = t.get("runs_on_days")
                if num and days:
                    self._mapping[num] = tuple(int(d) for d in days)

    def get_running_days(self, train_number: str) -> tuple[int, ...] | None:
        return self._mapping.get(str(train_number).strip())


class JsonCalendarProvider:
    """
    Verified running calendar provider backed by an external structured JSON file.
    
    Supports metadata extraction (source, license, version), train-specific provenance inspection,
    and validates that running days fall strictly within 0 (Monday) to 6 (Sunday).
    """

    def __init__(self, json_path: Union[str, Path]):
        self._path = Path(json_path)
        self._mapping: dict[str, tuple[int, ...]] = {}
        self._provenance_by_train: dict[str, dict[str, Any]] = {}
        self._metadata: dict[str, str] = {
            "source": "UNKNOWN",
            "license": "UNKNOWN",
            "version": "1.0.0",
        }
        self._load()

    def _load(self) -> None:
        if not self._path.exists() or not self._path.is_file():
            return

        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Check for structured envelope
            if "calendars" in data and isinstance(data["calendars"], dict):
                self._metadata["source"] = str(data.get("source", "Official Indian Railways Publications"))
                self._metadata["license"] = str(data.get("license", "Government Open Data License - India (GODL)"))
                self._metadata["version"] = str(data.get("version", "1.0.0"))
                if "audit_status" in data:
                    self._metadata["audit_status"] = str(data["audit_status"])
                if "audit_policy" in data:
                    self._metadata["audit_policy"] = str(data["audit_policy"])
                raw_calendars = data["calendars"]
            else:
                raw_calendars = data

            for num, val in raw_calendars.items():
                clean_num = str(num).strip()
                days = None
                if isinstance(val, dict):
                    days = val.get("runs_on_days")
                    self._provenance_by_train[clean_num] = val
                elif isinstance(val, (list, tuple)):
                    days = val

                if isinstance(days, (list, tuple)):
                    valid_days = [int(d) for d in days if 0 <= int(d) <= 6]
                    if valid_days:
                        self._mapping[clean_num] = tuple(sorted(set(valid_days)))

    @property
    def metadata(self) -> dict[str, str]:
        return dict(self._metadata)

    @property
    def total_trains(self) -> int:
        return len(self._mapping)

    def get_running_days(self, train_number: str) -> tuple[int, ...] | None:
        return self._mapping.get(str(train_number).strip())

    def get_provenance(self, train_number: str) -> dict[str, Any] | None:
        return self._provenance_by_train.get(str(train_number).strip())



class CompositeCalendarProvider:
    """
    Chained composite calendar provider evaluating multiple providers in priority order.
    """

    def __init__(self, providers: Sequence[CalendarProvider]):
        self._providers = list(providers)

    @property
    def providers(self) -> tuple[CalendarProvider, ...]:
        return tuple(self._providers)

    def get_running_days(self, train_number: str) -> tuple[int, ...] | None:
        clean_num = str(train_number).strip()
        for provider in self._providers:
            days = provider.get_running_days(clean_num)
            if days is not None and len(days) > 0:
                return days
        return None


