'use client';

import React, { useState } from 'react';
import { ArrowDownUp, Zap, Clock, ChevronDown, ChevronUp, Sparkles, Check } from 'lucide-react';
import { CandidateRoute } from '../../types/api';

interface RouteComparisonMatrixProps {
  routes: CandidateRoute[];
  onSelectRoute?: (routeId: string) => void;
}

export function RouteComparisonMatrix({ routes, onSelectRoute }: RouteComparisonMatrixProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!routes || routes.length < 2) return null;

  // Find fastest route
  const sortedByDuration = [...routes].sort(
    (a, b) => a.total_duration_minutes - b.total_duration_minutes
  );
  const fastestRoute = sortedByDuration[0];
  const slowestRoute = sortedByDuration[sortedByDuration.length - 1];
  const timeDifferenceMins = slowestRoute.total_duration_minutes - fastestRoute.total_duration_minutes;

  const formatDuration = (mins: number) => {
    const hours = Math.floor(mins / 60);
    const minutes = mins % 60;
    if (hours === 0) return `${minutes}m`;
    if (minutes === 0) return `${hours}h`;
    return `${hours}h ${minutes}m`;
  };

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-cream-300 p-4 sm:p-5 shadow-sm space-y-3">
      {/* Top Bar Summary */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-terracotta/10 text-terracotta flex items-center justify-center flex-shrink-0">
            <ArrowDownUp className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-sm text-espresso-900 flex items-center gap-2">
              <span>Route Comparison</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-cream-100 text-espresso-700 font-bold border border-cream-300">
                {routes.length} options evaluated
              </span>
            </div>
            <p className="text-xs text-espresso-600 mt-0.5">
              {timeDifferenceMins > 0 ? (
                <>
                  Fastest option saves <strong className="text-terracotta font-bold">{formatDuration(timeDifferenceMins)}</strong> over alternative routing.
                </>
              ) : (
                'All discovered routes have similar travel duration.'
              )}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-cream-50 hover:bg-cream-100 text-espresso-800 border border-cream-300 transition-colors self-start sm:self-auto"
        >
          <span>{isExpanded ? 'Hide Comparison Table' : 'Compare All Routes'}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Expanded Table */}
      {isExpanded && (
        <div className="pt-3 border-t border-cream-200 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-cream-200 text-espresso-500 font-semibold text-[10px] uppercase tracking-wider">
                <th className="py-2 pr-3">Route</th>
                <th className="py-2 px-3">Departure</th>
                <th className="py-2 px-3">Arrival</th>
                <th className="py-2 px-3">Duration</th>
                <th className="py-2 px-3">Transfers</th>
                <th className="py-2 px-3">Interchange</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cream-100">
              {routes.map((r, idx) => {
                const isFastest = r.route_id === fastestRoute.route_id;
                const intermediateHub =
                  r.transfer_count === 1 && r.legs.length >= 2 ? r.legs[0].destination_code : 'None';

                return (
                  <tr
                    key={r.route_id}
                    onClick={() => onSelectRoute?.(r.route_id)}
                    className="hover:bg-cream-50 transition-colors cursor-pointer group"
                  >
                    <td className="py-2.5 pr-3 font-semibold text-espresso-900">
                      <div className="flex items-center gap-1.5">
                        <span>Option {idx + 1}</span>
                        {idx === 0 && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-espresso-900 text-cream-100 font-bold">
                            Rec
                          </span>
                        )}
                        {isFastest && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-terracotta text-white font-bold flex items-center gap-0.5">
                            <Zap className="w-2.5 h-2.5" />
                            Fastest
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-medium text-espresso-800">
                      {formatTime(r.legs[0].departure_time)} ({r.legs[0].origin_code})
                    </td>
                    <td className="py-2.5 px-3 font-medium text-espresso-800">
                      {formatTime(r.legs[r.legs.length - 1].arrival_time)} ({r.legs[r.legs.length - 1].destination_code})
                    </td>
                    <td className="py-2.5 px-3 font-bold font-mono text-espresso-900">
                      {formatDuration(r.total_duration_minutes)}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          r.is_direct
                            ? 'bg-olive/15 text-olive'
                            : 'bg-terracotta/10 text-terracotta'
                        }`}
                      >
                        {r.is_direct ? 'Direct' : '1 Change'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-espresso-700">
                      {intermediateHub}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

