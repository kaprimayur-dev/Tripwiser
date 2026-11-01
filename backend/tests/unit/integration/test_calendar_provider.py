"""
Unit tests for CalendarProvider implementations:
DictCalendarProvider, FixtureCalendarProvider, JsonCalendarProvider, CompositeCalendarProvider.
"""

import json
from pathlib import Path
import pytest

from app.infrastructure.integration.calendar_provider import (
    DictCalendarProvider,
    FixtureCalendarProvider,
    JsonCalendarProvider,
    CompositeCalendarProvider,
)


class TestCalendarProviders:
    def test_dict_calendar_provider(self):
        mapping = {"12001": [0, 1, 2, 3, 4, 5, 6], "12301": [0, 1, 2, 3, 4, 5]}
        provider = DictCalendarProvider(mapping)

        assert provider.get_running_days("12001") == (0, 1, 2, 3, 4, 5, 6)
        assert provider.get_running_days("12301") == (0, 1, 2, 3, 4, 5)
        assert provider.get_running_days("99999") is None
        assert provider.get_running_days(" 12001 ") == (0, 1, 2, 3, 4, 5, 6)

    def test_json_calendar_provider_structured_envelope(self, tmp_path):
        cal_file = tmp_path / "calendars.json"
        data = {
            "source": "Official Railway Board",
            "license": "GODL",
            "version": "2.0.0",
            "calendars": {
                "12615": [0, 1, 2, 3, 4, 5, 6],
                "12431": [1, 3, 4],
                "99998": [7, 8, -1],  # Invalid days should be filtered out
            },
        }
        cal_file.write_text(json.dumps(data), encoding="utf-8")

        provider = JsonCalendarProvider(cal_file)
        assert provider.total_trains == 2
        assert provider.metadata["source"] == "Official Railway Board"
        assert provider.metadata["license"] == "GODL"
        assert provider.metadata["version"] == "2.0.0"
        assert provider.get_running_days("12615") == (0, 1, 2, 3, 4, 5, 6)
        assert provider.get_running_days("12431") == (1, 3, 4)
        assert provider.get_running_days("99998") is None  # no valid days

    def test_json_calendar_provider_missing_file(self, tmp_path):
        missing_file = tmp_path / "does_not_exist.json"
        provider = JsonCalendarProvider(missing_file)
        assert provider.total_trains == 0
        assert provider.get_running_days("12001") is None

    def test_composite_calendar_provider_priority_chain(self):
        prov1 = DictCalendarProvider({"12001": [0, 1], "12002": [2, 3]})
        prov2 = DictCalendarProvider({"12001": [4, 5, 6], "12003": [0, 1, 2, 3, 4, 5, 6]})

        composite = CompositeCalendarProvider([prov1, prov2])

        # Priority: prov1 takes precedence over prov2 for 12001
        assert composite.get_running_days("12001") == (0, 1)
        # 12002 resolved from prov1
        assert composite.get_running_days("12002") == (2, 3)
        # 12003 falls back to prov2
        assert composite.get_running_days("12003") == (0, 1, 2, 3, 4, 5, 6)
        # Unknown train returns None
        assert composite.get_running_days("99999") is None

    def test_composite_calendar_provider_empty(self):
        composite = CompositeCalendarProvider([])
        assert composite.get_running_days("12001") is None
