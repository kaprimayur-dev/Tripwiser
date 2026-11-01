/**
 * API Types for TripWiser Frontend mirroring backend domain contracts.
 */

export interface Station {
  code: string;
  name: string;
  city?: string | null;
  state?: string | null;
  zone?: string | null;
  latitude: number;
  longitude: number;
}

export interface NearbyStationItem {
  station: Station;
  distance_km: number;
}

export interface StationCoverage {
  has_timetable_coverage: boolean;
  total_compiled_trains: number;
  originating_trains_count: number;
  terminating_trains_count: number;
  coverage_status: string;
  coverage_note: string;
}

export interface StationDetail extends Station {
  timetable_coverage: StationCoverage;
}

export interface Availability {
  status: string;
  available_count?: number | null;
  waitlist_count?: number | null;
  quota?: string | null;
  travel_class?: string | null;
  fare?: number | null;
  source?: string | null;
}

export interface JourneyLeg {
  train_number: string;
  train_name: string;
  origin_code: string;
  destination_code: string;
  departure_time: string; // ISO datetime
  arrival_time: string; // ISO datetime
  duration_minutes: number;
  travel_class?: string | null;
  distance_km: number;
  timetable_status: string; // "TIMETABLE_CONFIRMED"
  availability?: Availability | null;
  runs_on_days?: number[] | null;
  frequency_description?: string | null;
  intermediate_stop_count?: number;
}

export interface CandidateRoute {
  route_id: string;
  is_direct: boolean;
  transfer_count: number;
  total_duration_minutes: number;
  total_fare?: number | null;
  transfer_durations_minutes: number[];
  score: number;
  legs: JourneyLeg[];
}

export interface RouteSearchQuery {
  origin: string;
  destination: string;
  journey_date: string;
  max_transfers: number;
  sort_by: string;
}

export interface RouteSearchResponse {
  query: RouteSearchQuery;
  origin_station?: Station | null;
  destination_station?: Station | null;
  total_routes_found: number;
  direct_routes_count: number;
  transfer_routes_count: number;
  timetable_status: string;
  fare_status: string;
  availability_status: string;
  sorting_applied: string;
  sorting_note?: string | null;
  no_route_reason?: string | null;
  routes: CandidateRoute[];
}

export interface BerthSegment {
  segment_id: string;
  train_number: string;
  date: string;
  coach: string;
  berth_number: number;
  berth_type: string;
  from_station_code: string;
  to_station_code: string;
  from_sequence: number;
  to_sequence: number;
}

export interface BachelorSpecialItinerary {
  train_number: string;
  train_name: string;
  origin_code: string;
  destination_code: string;
  travel_date: string;
  travel_class: string;
  segments: BerthSegment[];
  total_segment_count: number;
  berth_changes_count: number;
  is_continuous: boolean;
}

export interface BachelorSpecialSearchResponse {
  origin_code: string;
  destination_code: string;
  travel_date: string;
  travel_class?: string | null;
  total_itineraries: number;
  itineraries: BachelorSpecialItinerary[];
  status: string;
  data_source: string;
  is_live_source: boolean;
  provider_status?: string | null;
  chart_policy_notice: string;
}

export interface ScheduleStop {
  stop_sequence: number;
  station_code: string;
  station_name: string;
  arrival_time?: string | null;
  departure_time?: string | null;
  day_offset: number;
  distance_km: number;
  halt_minutes: number;
  is_commercial_halt: boolean;
}

export interface TrainSummary {
  number: string;
  name: string;
  origin_code: string;
  origin_name: string;
  destination_code: string;
  destination_name: string;
  runs_on_days: number[];
  frequency_description: string;
  total_stops: number;
  distance_km: number;
  provenance_tier: string;
}

export interface TrainDetail {
  number: string;
  name: string;
  origin_code: string;
  origin_name: string;
  destination_code: string;
  destination_name: string;
  runs_on_days: number[];
  frequency_description: string;
  total_stops: number;
  distance_km: number;
  source_document?: string | null;
  publication_version?: string | null;
  table_reference?: string | null;
  provenance_tier: string;
}

export interface TrainScheduleResponse {
  train: TrainDetail;
  total_stops: number;
  commercial_stops_count: number;
  stops: ScheduleStop[];
}

export interface IntermediateStopsResponse {
  train_number: string;
  train_name: string;
  from_station_code: string;
  from_station_name: string;
  to_station_code: string;
  to_station_name: string;
  intermediate_stop_count: number;
  stops: ScheduleStop[];
}



