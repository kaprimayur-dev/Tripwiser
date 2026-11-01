import datetime
from collections import defaultdict
from typing import Optional
from pydantic import ValidationError

from app.domain.models.bachelor import BerthSegment, BachelorSpecialItinerary


class BachelorEngine:
    """
    Core algorithmic engine for discovering and assembling valid, continuous
    berth segments on the same train and journey date.
    """

    def __init__(self, max_segments: int = 4):
        """
        :param max_segments: Maximum number of segments allowed in a single itinerary.
                             Default 4 allows up to 3 berth changes.
        """
        self.max_segments = max_segments

    def discover_itineraries(
        self,
        train_number: str,
        train_name: str,
        origin_code: str,
        destination_code: str,
        origin_sequence: int,
        destination_sequence: int,
        travel_date: datetime.date,
        travel_class: str,
        candidate_vacancies: list[BerthSegment],
    ) -> list[BachelorSpecialItinerary]:
        """
        Finds all valid, continuous paths of vacant berth segments spanning
        from origin_sequence to destination_sequence.
        """
        if origin_sequence >= destination_sequence:
            return []

        # 1. Filter vacancies strictly belonging to this train, date, and sequence window
        filtered: list[BerthSegment] = []
        for v in candidate_vacancies:
            if v.train_number != train_number:
                continue
            if v.date != travel_date:
                continue
            if v.from_sequence < origin_sequence or v.to_sequence > destination_sequence:
                continue
            if v.from_sequence >= v.to_sequence:
                continue
            filtered.append(v)

        if not filtered:
            return []

        # 2. Build adjacency index: from_sequence -> list[BerthSegment]
        adj: dict[int, list[BerthSegment]] = defaultdict(list)
        for seg in filtered:
            adj[seg.from_sequence].append(seg)

        # 3. Graph search (DFS) for continuous paths
        valid_paths: list[list[BerthSegment]] = []

        def dfs(curr_seq: int, path: list[BerthSegment]):
            if curr_seq == destination_sequence:
                if path:
                    valid_paths.append(list(path))
                return

            if len(path) >= self.max_segments:
                return

            for nxt in adj.get(curr_seq, []):
                # Continuity verification
                if path:
                    prev = path[-1]
                    if prev.to_sequence != nxt.from_sequence:
                        continue
                    if prev.to_station_code != nxt.from_station_code:
                        continue
                else:
                    # First segment must originate at requested origin
                    if nxt.from_station_code != origin_code:
                        continue
                    if nxt.from_sequence != origin_sequence:
                        continue

                path.append(nxt)
                dfs(nxt.to_sequence, path)
                path.pop()

        dfs(origin_sequence, [])

        # 4. Construct and validate domain itineraries
        itineraries: list[BachelorSpecialItinerary] = []
        seen_keys: set[str] = set()

        for path in valid_paths:
            # Check destination matches on final segment
            if path[-1].to_station_code != destination_code:
                continue
            if path[-1].to_sequence != destination_sequence:
                continue

            # Create path signature for deduplication
            sig = "|".join(
                f"{s.coach}-{s.berth_number}-{s.from_sequence}-{s.to_sequence}"
                for s in path
            )
            if sig in seen_keys:
                continue
            seen_keys.add(sig)

            try:
                itin = BachelorSpecialItinerary(
                    train_number=train_number,
                    train_name=train_name,
                    origin_code=origin_code,
                    destination_code=destination_code,
                    travel_date=travel_date,
                    travel_class=travel_class,
                    segments=path,
                    total_segment_count=len(path),
                    is_continuous=True,
                )
                itineraries.append(itin)
            except ValidationError:
                # Discard any segment combinations that fail strict domain validation
                continue

        # 5. Rank itineraries
        return self._rank_itineraries(itineraries)

    def _rank_itineraries(
        self, itineraries: list[BachelorSpecialItinerary]
    ) -> list[BachelorSpecialItinerary]:
        """
        Ranking criteria:
        1. Fewest segment handoffs (total_segment_count ascending)
        2. Coach consistency (fewest distinct coaches)
        3. Coach and berth ordering
        """
        def rank_key(itin: BachelorSpecialItinerary):
            distinct_coaches = len({s.coach for s in itin.segments})
            berth_changes = itin.total_segment_count - 1
            return (berth_changes, distinct_coaches)

        return sorted(itineraries, key=rank_key)

