'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Clock, Train, ArrowRight, ShieldCheck, Sparkles } from 'lucide-react';
import { CandidateRoute } from '../../types/api';
import { TransitTimeline } from './TransitTimeline';

interface RouteCardProps {
  route: CandidateRoute;
  isRecommended?: boolean;
}

export function RouteCard({ route, isRecommended = false }: RouteCardProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(isRecommended);

  const firstLeg = route.legs[0];
  const lastLeg = route.legs[route.legs.length - 1];

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return isoString;
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  const formatDuration = (mins: number) => {
    const hours = Math.floor(mins / 60);
    const minutes = mins % 60;
    if (hours === 0) return `${minutes}m`;
    if (minutes === 0) return `${hours}h`;
    return `${hours}h ${minutes}m`;
  };

  // Calculate day difference between departure and arrival
  const getDayDifference = () => {
    try {
      const dep = new Date(firstLeg.departure_time);
      const arr = new Date(lastLeg.arrival_time);
      const diffDays = Math.round((arr.getTime() - dep.getTime()) / (1000 * 60 * 60 * 24));
      return diffDays > 0 ? `+${diffDays}d` : null;
    } catch {
      return null;
    }
  };

  const dayDiff = getDayDifference();

  // Find intermediate hub if 1-transfer
  const intermediateHub =
    route.transfer_count === 1 && route.legs.length >= 2 ? route.legs[0].destination_code : null;

  return (
    <div
      className={`bg-white rounded-2xl border transition-all duration-200 overflow-hidden ${
        isRecommended
          ? 'border-terracotta/40 shadow-md ring-1 ring-terracotta/20'
          : 'border-cream-300 hover:border-espresso-500 shadow-sm'
      }`}
    >
      <div className="p-5 sm:p-6 space-y-4">
        {/* Top Badges */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {isRecommended && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-espresso-900 text-cream-100 shadow-sm">
                <Sparkles className="w-3.5 h-3.5 text-terracotta" />
                <span>RECOMMENDED ROUTE</span>
              </span>
            )}

            {route.is_direct ? (
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-olive/15 text-olive">
                DIRECT SERVICE
              </span>
            ) : (
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-terracotta/10 text-terracotta">
                1 TRANSFER VIA {intermediateHub}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1 text-olive font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Timetable Confirmed</span>
            </span>
          </div>
        </div>

        {/* Train Overview Banner */}
        <div>
          <h3 className="font-display text-lg font-bold text-espresso-900 leading-snug">
            {route.is_direct
              ? `${firstLeg.train_name} (#${firstLeg.train_number})`
              : `Coordinated Route: ${firstLeg.train_name} ➔ ${lastLeg.train_name}`}
          </h3>
          <p className="text-xs text-espresso-600 mt-0.5">
            {route.is_direct
              ? `Direct service from ${firstLeg.origin_code} to ${lastLeg.destination_code}`
              : `Change trains at ${intermediateHub} (${route.transfer_durations_minutes[0] || 0}m layover)`}
          </p>
        </div>

        {/* Departure & Arrival Visual Box */}
        <div className="bg-cream-50 rounded-xl p-4 sm:p-5 border border-cream-300 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
          {/* Departure Station */}
          <div className="flex-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
              Boarding
            </span>
            <div className="font-display text-2xl font-bold text-espresso-900 mt-0.5">
              {formatTime(firstLeg.departure_time)}
            </div>
            <div className="font-bold text-sm text-espresso-800 flex items-center gap-1.5 mt-0.5">
              <span>{firstLeg.origin_code}</span>
              <span className="font-normal text-xs text-espresso-600">
                ({formatDate(firstLeg.departure_time)})
              </span>
            </div>
          </div>

          {/* Visual Route Track */}
          <div className="flex-1 flex flex-col items-center justify-center px-2 py-1">
            <span className="text-xs font-bold font-mono text-terracotta mb-1 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              <span>{formatDuration(route.total_duration_minutes)}</span>
            </span>

            {/* Line graphic with nodes */}
            <div className="w-full flex items-center gap-1 max-w-[200px]">
              <span className="w-2.5 h-2.5 rounded-full bg-espresso-900 flex-shrink-0" />
              <div className="h-0.5 bg-terracotta flex-1" />
              {!route.is_direct && (
                <div
                  className="w-3.5 h-3.5 rounded-full bg-white border-2 border-terracotta flex items-center justify-center flex-shrink-0"
                  title={`Transfer at ${intermediateHub}`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-terracotta" />
                </div>
              )}
              {!route.is_direct && <div className="h-0.5 bg-terracotta flex-1" />}
              <span className="w-2.5 h-2.5 rounded-full bg-espresso-900 flex-shrink-0" />
            </div>

            <span className="text-[11px] text-espresso-600 mt-1 font-medium">
              {route.is_direct
                ? `${firstLeg.distance_km} km direct`
                : `${route.transfer_durations_minutes[0] || 0}m layover at ${intermediateHub}`}
            </span>
          </div>

          {/* Arrival Station */}
          <div className="flex-1 sm:text-right">
            <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
              Arrival
            </span>
            <div className="font-display text-2xl font-bold text-espresso-900 mt-0.5 flex items-baseline sm:justify-end gap-1">
              <span>{formatTime(lastLeg.arrival_time)}</span>
              {dayDiff && (
                <span className="text-xs font-bold text-terracotta font-mono">{dayDiff}</span>
              )}
            </div>
            <div className="font-bold text-sm text-espresso-800 flex items-center sm:justify-end gap-1.5 mt-0.5">
              <span>{lastLeg.destination_code}</span>
              <span className="font-normal text-xs text-espresso-600">
                ({formatDate(lastLeg.arrival_time)})
              </span>
            </div>
          </div>
        </div>

        {/* Honest Commercial Data Strip */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-espresso-600 pt-1">
          <div className="flex items-center gap-2">
            <span>Seat Availability:</span>
            <span className="px-2 py-0.5 rounded bg-cream-100 text-espresso-700 font-semibold border border-cream-300">
              Live feed deferred
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span>Commercial Fare:</span>
            <span className="px-2 py-0.5 rounded bg-cream-100 text-espresso-700 font-semibold border border-cream-300">
              Deferred (No verified provider)
            </span>
          </div>
        </div>

        {/* Expand / Collapse Details Drawer Button */}
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full pt-3 border-t border-cream-200 flex items-center justify-center gap-1.5 text-xs font-bold text-espresso-800 hover:text-terracotta transition-colors"
        >
          <span>{isExpanded ? 'Hide Leg Timetable' : 'View Detailed Route Timeline'}</span>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {/* Accordion Content */}
        {isExpanded && <TransitTimeline route={route} />}
      </div>
    </div>
  );
}

