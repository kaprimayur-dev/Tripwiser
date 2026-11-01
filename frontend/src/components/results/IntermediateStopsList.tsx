'use client';

import React, { useState, useEffect } from 'react';
import { Clock, MapPin, AlertCircle, Loader2, ShieldCheck } from 'lucide-react';
import { ScheduleStop } from '../../types/api';
import { getIntermediateStops } from '../../services/api';

interface IntermediateStopsListProps {
  trainNumber: string;
  fromCode: string;
  toCode: string;
  initialStops?: ScheduleStop[] | null;
}

export function IntermediateStopsList({
  trainNumber,
  fromCode,
  toCode,
  initialStops,
}: IntermediateStopsListProps) {
  const [stops, setStops] = useState<ScheduleStop[] | null>(initialStops || null);
  const [loading, setLoading] = useState<boolean>(!initialStops);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialStops && initialStops.length > 0) {
      setStops(initialStops);
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    getIntermediateStops(trainNumber, fromCode, toCode, true)
      .then((res) => {
        if (isMounted) {
          setStops(res.stops);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load intermediate halts');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [trainNumber, fromCode, toCode, initialStops]);

  if (loading) {
    return (
      <div className="py-4 px-3 flex items-center justify-center gap-2 text-xs text-espresso-600 bg-cream-50/50 rounded-xl border border-cream-200">
        <Loader2 className="w-4 h-4 animate-spin text-terracotta" />
        <span>Loading intermediate scheduled halts for #{trainNumber}...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-3 px-3 flex items-center gap-2 text-xs text-red-700 bg-red-50 rounded-xl border border-red-200">
        <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  if (!stops || stops.length === 0) {
    return (
      <div className="py-3 px-4 text-xs text-espresso-600 bg-cream-50 rounded-xl border border-cream-200 flex items-center justify-between">
        <span className="font-medium text-espresso-800">
          Non-stop direct leg: No intermediate scheduled halts recorded between {fromCode} and {toCode}.
        </span>
        <span className="inline-flex items-center gap-1 text-[11px] text-olive font-semibold">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Non-stop</span>
        </span>
      </div>
    );
  }

  const formatTime = (timeStr?: string | null) => {
    if (!timeStr) return '--:--';
    // e.g. "07:32:00" -> "07:32"
    return timeStr.slice(0, 5);
  };

  return (
    <div data-testid="intermediate-stops-list" className="mt-2 bg-cream-50/60 rounded-xl border border-cream-200 p-3.5 space-y-2.5 animate-fade-in text-xs">
      <div className="flex items-center justify-between border-b border-cream-200 pb-2">
        <span className="font-bold text-espresso-800 tracking-wide uppercase text-[11px]">
          Scheduled Intermediate Halts ({stops.length})
        </span>
        <span className="text-[10px] text-espresso-500">
          Timetable verified • Platforms confirmed at station
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[10px] uppercase font-bold text-espresso-500 border-b border-cream-200">
              <th className="pb-1.5 pl-1 font-semibold">#</th>
              <th className="pb-1.5 font-semibold">Station</th>
              <th className="pb-1.5 font-semibold">Arr</th>
              <th className="pb-1.5 font-semibold">Dep</th>
              <th className="pb-1.5 font-semibold text-center">Halt</th>
              <th className="pb-1.5 pr-1 font-semibold text-right">Distance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-cream-200/60 font-sans">
            {stops.map((stop, idx) => (
              <tr key={`${stop.station_code}-${stop.stop_sequence}`} className="hover:bg-cream-100/50 transition-colors">
                <td className="py-1.5 pl-1 text-[11px] text-espresso-500 font-mono">
                  {idx + 1}
                </td>
                <td className="py-1.5">
                  <div className="font-semibold text-espresso-900">
                    {stop.station_name}
                  </div>
                  <span className="font-mono text-[10px] text-espresso-500 uppercase">
                    {stop.station_code}
                  </span>
                </td>
                <td className="py-1.5 font-mono text-espresso-700">
                  {formatTime(stop.arrival_time)}
                </td>
                <td className="py-1.5 font-mono text-espresso-700">
                  {formatTime(stop.departure_time)}
                </td>
                <td className="py-1.5 text-center">
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-cream-200 text-espresso-800">
                    {stop.halt_minutes > 0 ? `${stop.halt_minutes}m` : 'Halt'}
                  </span>
                </td>
                <td className="py-1.5 pr-1 text-right font-mono text-espresso-600">
                  {stop.distance_km > 0 ? `${Math.round(stop.distance_km)} km` : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
