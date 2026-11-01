'use client';

import React, { useState, useEffect } from 'react';
import {
  Train,
  Clock,
  ShieldCheck,
  MapPin,
  ArrowRight,
  AlertCircle,
  Loader2,
  Calendar,
  Layers,
  FileText,
  X,
} from 'lucide-react';
import { TrainScheduleResponse } from '../../types/api';
import { getTrainSchedule } from '../../services/api';

interface TrainScheduleViewProps {
  trainNumber: string;
  onClose?: () => void;
}

const WEEKDAYS = [
  { day: 0, label: 'Mon' },
  { day: 1, label: 'Tue' },
  { day: 2, label: 'Wed' },
  { day: 3, label: 'Thu' },
  { day: 4, label: 'Fri' },
  { day: 5, label: 'Sat' },
  { day: 6, label: 'Sun' },
];

export function TrainScheduleView({ trainNumber, onClose }: TrainScheduleViewProps) {
  const [scheduleData, setScheduleData] = useState<TrainScheduleResponse | null>(null);
  const [onlyCommercial, setOnlyCommercial] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!trainNumber) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    getTrainSchedule(trainNumber, onlyCommercial)
      .then((data) => {
        if (isMounted) {
          setScheduleData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load train schedule');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [trainNumber, onlyCommercial]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-cream-300 p-8 text-center space-y-3 shadow-sm animate-fade-in">
        <Loader2 className="w-8 h-8 animate-spin text-terracotta mx-auto" />
        <div className="font-display font-bold text-lg text-espresso-900">
          Loading Official Schedule for Train #{trainNumber}...
        </div>
        <p className="text-xs text-espresso-600">
          Querying verified Trains at a Glance (TAG) timetable and station halt sequences.
        </p>
      </div>
    );
  }

  if (error || !scheduleData) {
    return (
      <div className="bg-white rounded-2xl border border-red-200 p-6 shadow-sm space-y-3">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-6 h-6 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-display text-base font-bold text-red-900">
              Timetable Schedule Unavailable
            </h3>
            <p className="text-xs text-red-700 mt-1">
              {error || `No verified schedule records found for train #${trainNumber}.`}
            </p>
            <div className="mt-3 p-3 bg-red-50 rounded-xl text-xs text-red-800 border border-red-100">
              <span className="font-semibold">Zero-Fabrication Policy:</span> TripWiser never invents missing train halts, operating days, or timings. Only officially compiled and verified schedules from Trains at a Glance (TAG 2024–2026) are rendered.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { train, stops, total_stops, commercial_stops_count } = scheduleData;
  const runningDaySet = new Set(train.runs_on_days || []);

  const formatTime = (timeStr?: string | null) => {
    if (!timeStr) return '--:--';
    return timeStr.slice(0, 5);
  };

  return (
    <div id="train-schedule-view" className="space-y-5 animate-fade-in">
      {/* Train Header Banner */}
      <div className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cream-200 pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-espresso-900 text-cream-100 font-mono">
                #{train.number}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-olive/15 text-olive flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Verified TAG Timetable</span>
              </span>
              {train.table_reference && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cream-200 text-espresso-800">
                  {train.table_reference}
                </span>
              )}
            </div>

            <h1 className="font-display text-2xl sm:text-3xl font-bold text-espresso-900">
              {train.name}
            </h1>
            <div className="text-xs text-espresso-600 mt-1 flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-espresso-800">{train.origin_name} ({train.origin_code})</span>
              <ArrowRight className="w-3.5 h-3.5 text-espresso-400" />
              <span className="font-semibold text-espresso-800">{train.destination_name} ({train.destination_code})</span>
            </div>
          </div>

          <div className="flex items-center sm:flex-col sm:items-end justify-between gap-3 text-xs text-espresso-600 pt-2 sm:pt-0">
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="order-last sm:order-first inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-espresso-600 hover:text-espresso-900 bg-cream-200/70 hover:bg-cream-300 transition-colors"
                title="Close timetable view"
              >
                <X className="w-3.5 h-3.5" />
                <span>Close</span>
              </button>
            )}
            <div>
              <span className="text-[10px] uppercase font-bold text-espresso-500">Total Distance</span>
              <div className="font-display text-lg font-bold text-espresso-900">
                {Math.round(train.distance_km)} km
              </div>
            </div>
            <div className="sm:mt-1">
              <span className="text-[10px] uppercase font-bold text-espresso-500">Commercial Stops</span>
              <div className="font-semibold text-espresso-800">
                {commercial_stops_count} Halts
              </div>
            </div>
          </div>
        </div>

        {/* Operating Days Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block mb-1.5">
              Operating Running Days ({train.frequency_description})
            </span>
            <div className="flex items-center gap-1.5 flex-wrap">
              {WEEKDAYS.map((w) => {
                const isActive = runningDaySet.has(w.day);
                return (
                  <div
                    key={w.day}
                    data-testid="running-day-chip"
                    data-active={isActive ? 'true' : 'false'}
                    title={isActive ? `Runs on ${w.label}` : `Does not run on ${w.label}`}
                    className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                      isActive
                        ? 'bg-espresso-900 text-cream-100 shadow-sm ring-1 ring-espresso-900'
                        : 'bg-cream-100 text-espresso-400 border border-cream-200 opacity-60'
                    }`}
                  >
                    {w.label}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Stoppage Filter Toggle */}
          <div className="flex items-center gap-1.5 bg-cream-100 p-1 rounded-xl border border-cream-300 self-start sm:self-auto text-xs">
            <button
              type="button"
              id="commercial-stops-toggle"
              onClick={() => setOnlyCommercial(true)}
              className={`px-3 py-1 rounded-lg font-semibold transition-all ${
                onlyCommercial
                  ? 'bg-white text-espresso-900 shadow-sm font-bold'
                  : 'text-espresso-600 hover:text-espresso-900'
              }`}
            >
              Commercial Halts ({commercial_stops_count})
            </button>
            <button
              type="button"
              id="all-stops-toggle"
              onClick={() => setOnlyCommercial(false)}
              className={`px-3 py-1 rounded-lg font-semibold transition-all ${
                !onlyCommercial
                  ? 'bg-white text-espresso-900 shadow-sm font-bold'
                  : 'text-espresso-600 hover:text-espresso-900'
              }`}
            >
              All Stops ({total_stops})
            </button>
          </div>
        </div>
      </div>

      {/* Stoppage Timetable Timeline Table */}
      <div className="bg-white rounded-2xl border border-cream-300 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-cream-200 bg-cream-50/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-terracotta" />
            <h3 className="font-display font-bold text-sm text-espresso-900">
              Complete Station Stoppage Itinerary ({stops.length} stations displayed)
            </h3>
          </div>
          <span className="text-[11px] text-espresso-500">
            Timetable verified • Platforms confirmed at station
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-cream-100/60 text-[10px] uppercase font-bold text-espresso-600 border-b border-cream-200">
                <th className="py-2.5 pl-4 font-semibold">#</th>
                <th className="py-2.5 font-semibold">Station</th>
                <th className="py-2.5 font-semibold">Arrival</th>
                <th className="py-2.5 font-semibold">Departure</th>
                <th className="py-2.5 font-semibold text-center">Halt</th>
                <th className="py-2.5 font-semibold text-center">Day</th>
                <th className="py-2.5 pr-4 font-semibold text-right">Distance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cream-200/60">
              {stops.map((stop, idx) => {
                const isOrigin = idx === 0;
                const isDest = idx === stops.length - 1;

                return (
                  <tr
                    key={`${stop.station_code}-${stop.stop_sequence}`}
                    className={`hover:bg-cream-50/80 transition-colors ${
                      isOrigin || isDest ? 'bg-cream-50/40 font-semibold' : ''
                    }`}
                  >
                    <td className="py-2.5 pl-4 text-espresso-500 font-mono text-[11px]">
                      {stop.stop_sequence}
                    </td>

                    <td className="py-2.5">
                      <div className="font-bold text-espresso-900">
                        {stop.station_name}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="font-mono text-[10px] text-terracotta font-semibold bg-terracotta/10 px-1 rounded">
                          {stop.station_code}
                        </span>
                        {isOrigin && (
                          <span className="text-[9px] font-bold text-olive uppercase tracking-wider">
                            Origin
                          </span>
                        )}
                        {isDest && (
                          <span className="text-[9px] font-bold text-terracotta uppercase tracking-wider">
                            Destination
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-2.5 font-mono text-espresso-800">
                      {isOrigin ? (
                        <span className="text-espresso-400 font-sans italic">Starts</span>
                      ) : (
                        formatTime(stop.arrival_time)
                      )}
                    </td>

                    <td className="py-2.5 font-mono text-espresso-800">
                      {isDest ? (
                        <span className="text-espresso-400 font-sans italic">Terminates</span>
                      ) : (
                        formatTime(stop.departure_time)
                      )}
                    </td>

                    <td className="py-2.5 text-center">
                      {isOrigin || isDest ? (
                        <span className="text-espresso-400">--</span>
                      ) : stop.halt_minutes > 0 ? (
                        <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-terracotta/10 text-terracotta">
                          {stop.halt_minutes} min
                        </span>
                      ) : (
                        <span className="text-espresso-400 text-[10px]">Pass</span>
                      )}
                    </td>

                    <td className="py-2.5 text-center font-mono text-espresso-700">
                      Day {stop.day_offset + 1}
                    </td>

                    <td className="py-2.5 pr-4 text-right font-mono text-espresso-700">
                      {Math.round(stop.distance_km)} km
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
