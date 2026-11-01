from pathlib import Path
from typing import Mapping, Protocol, Sequence, Union
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

