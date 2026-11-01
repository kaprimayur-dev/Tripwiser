'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowLeftRight,
  Clock,
  Calendar,
  ShieldCheck,
  AlertCircle,
  ArrowRight,
  Search,
  Layers,
  ChevronRight,
  Filter,
} from 'lucide-react';
import { Station, TrainComparisonItem, TrainComparisonResponse } from '../../types/api';
import { compareTrains } from '../../services/api';
import { StationAutocomplete } from '../search/StationAutocomplete';

interface TrainCompareViewProps {
  initialOrigin?: Station | null;
  initialDestination?: Station | null;
  onInspectTrain?: (trainNumber: string) => void;
  onSwitchToConnecting?: (origin: Station, destination: Station) => void;
}

type CompareSort = 'fastest' | 'earliest' | 'stops';

export function TrainCompareView({
  initialOrigin,
  initialDestination,
  onInspectTrain,
  onSwitchToConnecting,
}: TrainCompareViewProps) {
  const [origin, setOrigin] = useState<Station | null>(initialOrigin || null);
  const [destination, setDestination] = useState<Station | null>(initialDestination || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comparisonData, setComparisonData] = useState<TrainComparisonResponse | null>(null);
  const [sortOrder, setSortOrder] = useState<CompareSort>('fastest');
  const [validationError, setValidationError] = useState<string | null>(null);

  const executeCompare = async (origCode: string, destCode: string) => {
    if (origCode === destCode) {
      setValidationError('Origin and destination stations cannot be identical.');
      setComparisonData(null);
      return;
    }
    setValidationError(null);
    setLoading(true);
    setError(null);

    try {
      const data = await compareTrains(origCode, destCode);
      setComparisonData(data);
    } catch (err: any) {
      setError(err instanceof Error ? err.message : String(err));
      setComparisonData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (origin && destination) {
      executeCompare(origin.code, destination.code);
    }
  }, []);

  const handleCompareSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!origin || !destination) {
      setValidationError('Please select both origin and destination stations.');
      return;
    }
    executeCompare(origin.code, destination.code);
  };

  const handleSwapStations = () => {
    const prevOrig = origin;
    setOrigin(destination);
    setDestination(prevOrig);
    if (destination && prevOrig) {
      executeCompare(destination.code, prevOrig.code);
    }
  };

  const sortedTrains = useMemo(() => {
    if (!comparisonData?.trains) return [];
    const list = [...comparisonData.trains];
    if (sortOrder === 'fastest') {
      list.sort((a, b) => {
        const da = a.scheduled_duration_minutes ?? 999999;
        const db = b.scheduled_duration_minutes ?? 999999;
        return da - db;
      });
    } else if (sortOrder === 'earliest') {
      list.sort((a, b) => (a.departure_time || '99:99').localeCompare(b.departure_time || '99:99'));
    } else if (sortOrder === 'stops') {
      list.sort((a, b) => a.intermediate_stops_count - b.intermediate_stops_count);
    }
    return list;
  }, [comparisonData, sortOrder]);

  return (
    <div className="space-y-6 animate-fade-in" id="train-compare-view">
      {/* Search Header Form */}
      <form
        onSubmit={handleCompareSubmit}
        className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-cream-200 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <ArrowLeftRight className="w-5 h-5 text-terracotta" />
              <h2 className="font-display text-lg sm:text-xl font-bold text-espresso-900">
                Compare Direct Trains
              </h2>
            </div>
            <p className="text-xs text-espresso-600 mt-0.5">
              Select two stations to inspect all direct railway services, scheduled travel times, stop counts, and operating frequencies.
            </p>
          </div>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-olive/15 text-olive self-start sm:self-auto">
            <ShieldCheck className="w-3 h-3" />
            <span>Timetable Intelligence</span>
          </span>
        </div>

        {/* Station Autocompletes */}
        <div className="grid grid-cols-1 sm:grid-cols-[1fr,auto,1fr] items-end gap-3">
          <div>
            <StationAutocomplete
              id="compare-origin-autocomplete"
              label="Origin Station"
              placeholder="Search origin (e.g. NDLS, New Delhi)..."
              value={origin}
              onChange={setOrigin}
            />
          </div>

          <div className="flex justify-center pb-0.5 sm:pb-1">
            <button
              type="button"
              id="btn-swap-compare-stations"
              onClick={handleSwapStations}
              className="p-2.5 rounded-xl border border-cream-300 bg-cream-100 hover:bg-cream-200 text-espresso-700 transition-colors"
              title="Swap stations"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          <div>
            <StationAutocomplete
              id="compare-dest-autocomplete"
              label="Destination Station"
              placeholder="Search destination (e.g. BPL, Bhopal)..."
              value={destination}
              onChange={setDestination}
            />
          </div>
        </div>

        {/* Validation & Error Notices */}
        {validationError && (
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-end pt-2 border-t border-cream-200">
          <button
            type="submit"
            id="btn-execute-compare"
            disabled={loading}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-xs sm:text-sm font-semibold transition-colors shadow-sm disabled:opacity-50"
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-cream-200 border-t-transparent rounded-full animate-spin" />
                <span>Comparing...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Compare Direct Services</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Results Header & Sorting Bar */}
      {comparisonData && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-cream-50 p-4 rounded-xl border border-cream-300">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-display font-bold text-base sm:text-lg text-espresso-900">
                  {comparisonData.origin_name} ({comparisonData.origin_code})
                </span>
                <ArrowRight className="w-4 h-4 text-espresso-400" />
                <span className="font-display font-bold text-base sm:text-lg text-espresso-900">
                  {comparisonData.destination_name} ({comparisonData.destination_code})
                </span>
              </div>
              <p className="text-xs text-espresso-600 mt-0.5">
                {comparisonData.total_trains}{' '}
                {comparisonData.total_trains === 1 ? 'direct train' : 'direct trains'} found in verified compiled timetable.
              </p>
            </div>

            {/* Sort Controls */}
            {comparisonData.total_trains > 0 && (
              <div className="flex items-center gap-1 bg-cream-200/80 p-1 rounded-lg border border-cream-300 text-xs self-start sm:self-auto">
                <span className="px-2 text-espresso-500 flex items-center gap-1 font-semibold">
                  <Filter className="w-3 h-3" /> Sort:
                </span>
                <button
                  type="button"
                  id="sort-fastest"
                  onClick={() => setSortOrder('fastest')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                    sortOrder === 'fastest' ? 'bg-white text-espresso-900 shadow-sm' : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  Fastest
                </button>
                <button
                  type="button"
                  id="sort-earliest"
                  onClick={() => setSortOrder('earliest')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                    sortOrder === 'earliest' ? 'bg-white text-espresso-900 shadow-sm' : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  Earliest
                </button>
                <button
                  type="button"
                  id="sort-stops"
                  onClick={() => setSortOrder('stops')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                    sortOrder === 'stops' ? 'bg-white text-espresso-900 shadow-sm' : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  Fewest Stops
                </button>
              </div>
            )}
          </div>

          {/* Empty State */}
          {comparisonData.total_trains === 0 ? (
            <div className="p-8 text-center rounded-2xl bg-white border border-cream-300 shadow-sm space-y-4">
              <AlertCircle className="w-10 h-10 text-espresso-300 mx-auto" />
              <div>
                <h3 className="font-display text-lg font-bold text-espresso-900">
                  No Direct Trains Recorded
                </h3>
                <p className="text-xs sm:text-sm text-espresso-600 max-w-md mx-auto mt-1">
                  There are no compiled direct train services operating between{' '}
                  <span className="font-semibold text-espresso-800">{comparisonData.origin_code}</span> and{' '}
                  <span className="font-semibold text-espresso-800">{comparisonData.destination_code}</span> in the static timetable dataset.
                </p>
              </div>

              {onSwitchToConnecting && origin && destination && (
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => onSwitchToConnecting(origin, destination)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-xs font-semibold shadow-sm transition-colors"
                  >
                    <span>Discover Connecting Routes with Transfers</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Cards List */
            <div className="grid grid-cols-1 gap-3.5">
              {sortedTrains.map((t, idx) => (
                <div
                  key={t.number}
                  className="bg-white rounded-2xl border border-cream-300 shadow-sm p-4 sm:p-5 hover:border-terracotta/40 transition-all space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-cream-200 pb-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-espresso-900 text-cream-100">
                        #{t.number}
                      </span>
                      <h3 className="font-display text-base sm:text-lg font-bold text-espresso-900">
                        {t.name}
                      </h3>
                      {t.table_reference && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-cream-200 text-espresso-700">
                          {t.table_reference}
                        </span>
                      )}
                      {idx === 0 && sortOrder === 'fastest' && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-olive/15 text-olive">
                          Fastest Service
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 text-xs text-espresso-600">
                      <Calendar className="w-3.5 h-3.5 text-espresso-400" />
                      <span className="font-medium">{t.frequency_description}</span>
                    </div>
                  </div>

                  {/* Timetable Timing Strip */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-cream-50/70 p-3.5 rounded-xl border border-cream-200">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                        Departure ({comparisonData.origin_code})
                      </span>
                      <div className="font-display text-base font-bold text-espresso-900 mt-0.5">
                        {t.departure_time ? t.departure_time.slice(0, 5) : '--:--'}
                      </div>
                    </div>

                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                        Arrival ({comparisonData.destination_code})
                      </span>
                      <div className="font-display text-base font-bold text-espresso-900 mt-0.5 flex items-center gap-1">
                        <span>{t.arrival_time ? t.arrival_time.slice(0, 5) : '--:--'}</span>
                        {t.day_offset_difference > 0 && (
                          <span className="text-[10px] font-bold text-terracotta">
                            (+{t.day_offset_difference}d)
                          </span>
                        )}
                      </div>
                    </div>

                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                        Scheduled Duration
                      </span>
                      <div className="font-display text-base font-bold text-espresso-900 mt-0.5 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-espresso-500" />
                        <span>{t.duration_formatted}</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                        Recorded Stops
                      </span>
                      <div className="font-display text-base font-bold text-espresso-900 mt-0.5">
                        {t.intermediate_stops_count} intermediate
                      </div>
                    </div>
                  </div>

                  {/* Actions & Disclaimer */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 text-[11px] text-espresso-500">
                    <div>
                      <span>Route endpoints: </span>
                      <span className="font-semibold text-espresso-700">
                        {t.origin_name} ({t.origin_code}) ➔ {t.destination_name} ({t.destination_code})
                      </span>
                    </div>

                    {onInspectTrain && (
                      <button
                        type="button"
                        onClick={() => onInspectTrain(t.number)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cream-200 hover:bg-cream-300 text-espresso-800 text-xs font-semibold transition-colors self-end sm:self-auto"
                      >
                        <Layers className="w-3.5 h-3.5 text-espresso-600" />
                        <span>Inspect Full Timetable</span>
                        <ChevronRight className="w-3.5 h-3.5 text-espresso-500" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Honest Disclaimer Banner */}
          <div className="p-3.5 bg-cream-100 rounded-xl border border-cream-300 text-xs text-espresso-600 flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-olive flex-shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              <span className="font-semibold text-espresso-900">Timetable Foundation Guarantee:</span>{' '}
              {comparisonData.disclaimer} Travel durations are calculated directly from published schedule timings and day offsets.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
