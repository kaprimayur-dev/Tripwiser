'use client';

import React, { useState } from 'react';
import {
  X,
  Train,
  Clock,
  ShieldCheck,
  MapPin,
  ArrowRight,
  Share2,
  Printer,
  Check,
  AlertCircle,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { CandidateRoute, JourneyLeg } from '../../types/api';
import { TransferAdvisoryBadge } from './TransferAdvisoryBadge';
import { IntermediateStopsList } from './IntermediateStopsList';

interface JourneyDetailsModalProps {
  route: CandidateRoute | null;
  isOpen: boolean;
  onClose: () => void;
  isRecommended?: boolean;
}

export function JourneyDetailsModal({
  route,
  isOpen,
  onClose,
  isRecommended = false,
}: JourneyDetailsModalProps) {
  const [copied, setCopied] = useState(false);
  const [expandedLegs, setExpandedLegs] = useState<Record<number, boolean>>({});

  const toggleLeg = (idx: number) => {
    setExpandedLegs((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  if (!isOpen || !route) return null;

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
      return d.toLocaleDateString('en-IN', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
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

  const intermediateHubs = route.legs.slice(0, -1).map((leg) => leg.destination_code);
  const intermediateHub = intermediateHubs.join(', ');

  const totalDistance = route.legs.reduce((acc, leg) => acc + (leg.distance_km || 0), 0);
  const totalTravelMins =
    route.total_travel_time_minutes !== undefined && route.total_travel_time_minutes > 0
      ? route.total_travel_time_minutes
      : route.legs.reduce((acc, l) => acc + (l.duration_minutes || 0), 0);
  const totalWaitMins =
    route.total_wait_time_minutes !== undefined
      ? route.total_wait_time_minutes
      : Math.max(0, route.total_duration_minutes - totalTravelMins);
  const travelPct =
    route.total_duration_minutes > 0
      ? Math.min(100, Math.max(0, Math.round((totalTravelMins / route.total_duration_minutes) * 100)))
      : 100;
  const waitPct = 100 - travelPct;

  const handleCopy = () => {
    const lines = [
      `TripWiser Itinerary: ${firstLeg.origin_code} ➔ ${lastLeg.destination_code}`,
      `Total Duration: ${formatDuration(route.total_duration_minutes)} (${totalDistance} km)`,
      `Departure: ${formatDate(firstLeg.departure_time)} at ${formatTime(firstLeg.departure_time)} (${firstLeg.origin_code})`,
      `Arrival: ${formatDate(lastLeg.arrival_time)} at ${formatTime(lastLeg.arrival_time)} (${lastLeg.destination_code})`,
      `Transfers: ${route.transfer_count === 0 ? 'Direct service' : `${route.transfer_count} Transfer(s) at ${intermediateHub}`}`,
      '',
      ...route.legs.map(
        (leg, idx) =>
          `Leg ${idx + 1}: Train #${leg.train_number} (${leg.train_name})\n` +
          `  Departs: ${leg.origin_code} at ${formatTime(leg.departure_time)} (${formatDate(leg.departure_time)})\n` +
          `  Arrives: ${leg.destination_code} at ${formatTime(leg.arrival_time)} (${formatDate(leg.arrival_time)})\n` +
          `  Duration: ${formatDuration(leg.duration_minutes)} | Distance: ${leg.distance_km} km`
      ),
      '',
      'Generated via TripWiser — Verified Timetable Intelligence.',
    ];

    navigator.clipboard.writeText(lines.join('\n')).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-espresso-900/65 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl max-w-2xl w-full border border-cream-300 shadow-2xl relative max-h-[92vh] flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="p-5 sm:p-6 border-b border-cream-200 bg-cream-50 flex items-start justify-between gap-4 flex-shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              {isRecommended && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-espresso-900 text-cream-100 shadow-sm">
                  <Sparkles className="w-3 h-3 text-terracotta" />
                  <span>RECOMMENDED ROUTE</span>
                </span>
              )}
              {route.is_direct ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-olive/15 text-olive">
                  DIRECT ROUTE
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-terracotta/10 text-terracotta">
                  1 TRANSFER VIA {intermediateHub}
                </span>
              )}
              <span className="inline-flex items-center gap-1 text-[11px] text-olive font-semibold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Timetable Confirmed</span>
              </span>
            </div>

            <h2 className="font-display text-xl sm:text-2xl font-bold text-espresso-900">
              {firstLeg.origin_code} ➔ {lastLeg.destination_code} Journey Details
            </h2>
            <p className="text-xs text-espresso-600 mt-0.5">
              Verified train schedule and connection window
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full text-espresso-500 hover:text-espresso-900 hover:bg-cream-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-5 sm:p-6 space-y-5 overflow-y-auto flex-1">
          {/* Key Metrics Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-cream-50 rounded-xl p-3 border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                Total Duration
              </span>
              <div className="font-display text-lg font-bold text-espresso-900 mt-0.5">
                {formatDuration(route.total_duration_minutes)}
              </div>
            </div>

            <div className="bg-cream-50 rounded-xl p-3 border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                Aboard Trains
              </span>
              <div className="font-display text-lg font-bold text-olive mt-0.5">
                {formatDuration(totalTravelMins)}
              </div>
              <span className="text-[10px] text-espresso-600 block">{travelPct}% of journey</span>
            </div>

            <div className="bg-cream-50 rounded-xl p-3 border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                Transfer Waiting
              </span>
              <div className="font-display text-lg font-bold text-terracotta mt-0.5">
                {formatDuration(totalWaitMins)}
              </div>
              <span className="text-[10px] text-espresso-600 block">{waitPct}% of journey</span>
            </div>

            <div className="bg-cream-50 rounded-xl p-3 border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                Legs &amp; Transfers
              </span>
              <div className="font-display text-base font-bold text-espresso-800 mt-0.5">
                {route.legs.length} Train{route.legs.length > 1 ? 's' : ''}
              </div>
              <span className="text-[10px] text-espresso-600 block">
                {route.transfer_count === 0 ? 'Direct service' : `${route.transfer_count} transfer${route.transfer_count > 1 ? 's' : ''}`}
              </span>
            </div>
          </div>

          {/* Journey Reliability & Timetable Insights Section */}
          <div className="bg-cream-50 rounded-xl p-4 border border-cream-300 space-y-2">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <h3 className="text-xs font-bold uppercase tracking-wider text-espresso-700 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-terracotta" />
                <span>Journey Reliability &amp; Timetable Insights</span>
              </h3>
              {route.overall_transfer_risk && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cream-200 text-espresso-800 border border-cream-300">
                  Overall Risk: {route.overall_transfer_risk.replace('_', ' ')}
                </span>
              )}
            </div>
            {route.insights && route.insights.length > 0 ? (
              <ul className="text-xs text-espresso-700 space-y-1 list-disc list-inside">
                {route.insights.map((insight, i) => (
                  <li key={i}>{insight}</li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-espresso-600">Calculated from published Indian Railways timetable stops.</p>
            )}
            <p className="text-[11px] text-espresso-500 pt-2 border-t border-cream-200">
              * Feasibility is computed strictly from published timetable stop schedules. Live delays, platform allocation, and walking speeds vary; connections are not guaranteed.
            </p>
          </div>

          {/* Leg-by-leg Timeline */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-espresso-700">
              Leg-By-Leg Route Breakdown
            </h3>

            {route.legs.map((leg: JourneyLeg, idx: number) => {
              const layoverMins = route.transfer_durations_minutes?.[idx];

              return (
                <React.Fragment key={`${leg.train_number}-${idx}`}>
                  {/* Leg Card */}
                  <div className="bg-white rounded-xl border border-cream-300 shadow-sm p-4 space-y-3">
                    {/* Header */}
                    <div className="flex items-center justify-between gap-3 pb-2.5 border-b border-cream-200">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-md bg-espresso-900 text-cream-100 flex items-center justify-center text-xs font-bold font-mono">
                          {idx + 1}
                        </span>
                        <div>
                          <div className="font-semibold text-sm text-espresso-900">
                            {leg.train_name}
                          </div>
                          <div className="text-[11px] text-espresso-600 font-mono">
                            Train #{leg.train_number}
                          </div>
                        </div>
                      </div>

                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cream-100 text-espresso-800 border border-cream-300">
                        {formatDuration(leg.duration_minutes)}
                      </span>
                    </div>

                    {/* Departure & Arrival Grid */}
                    <div className="grid grid-cols-2 gap-4 text-xs">
                      <div>
                        <span className="text-[10px] uppercase font-bold text-espresso-500">
                          Boarding
                        </span>
                        <div className="font-display text-base font-bold text-espresso-900">
                          {formatTime(leg.departure_time)}
                        </div>
                        <div className="font-semibold text-espresso-800">
                          Station: <span className="font-mono text-terracotta">{leg.origin_code}</span>
                        </div>
                        <div className="text-[11px] text-espresso-600">
                          {formatDate(leg.departure_time)}
                        </div>
                      </div>

                      <div className="text-right">
                        <span className="text-[10px] uppercase font-bold text-espresso-500">
                          Arrival
                        </span>
                        <div className="font-display text-base font-bold text-espresso-900">
                          {formatTime(leg.arrival_time)}
                        </div>
                        <div className="font-semibold text-espresso-800">
                          Station: <span className="font-mono text-terracotta">{leg.destination_code}</span>
                        </div>
                        <div className="text-[11px] text-espresso-600">
                          {formatDate(leg.arrival_time)}
                        </div>
                      </div>
                    </div>

                    {/* Intermediate Halts Toggle */}
                    <div className="pt-2 border-t border-cream-200">
                      <button
                        type="button"
                        data-testid="modal-toggle-intermediate-stops"
                        onClick={() => toggleLeg(idx)}
                        className="inline-flex items-center gap-1.5 text-xs font-bold text-terracotta hover:text-terracotta/80 transition-colors"
                      >
                        <span>
                          {expandedLegs[idx]
                            ? 'Hide Intermediate Halts'
                            : `View Intermediate Halts (${leg.intermediate_stop_count !== undefined ? `${leg.intermediate_stop_count} stops` : 'Expand'})`}
                        </span>
                        {expandedLegs[idx] ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>

                      {expandedLegs[idx] && (
                        <div className="mt-2">
                          <IntermediateStopsList
                            trainNumber={leg.train_number}
                            fromCode={leg.origin_code}
                            toCode={leg.destination_code}
                          />
                        </div>
                      )}
                    </div>

                    {/* Platform & Station Guidance */}
                    <div className="pt-2 border-t border-cream-200 flex items-start gap-2 text-[11px] text-espresso-600">
                      <AlertCircle className="w-3.5 h-3.5 text-olive flex-shrink-0 mt-0.5" />
                      <span>
                        <strong>Station Platform Policy:</strong> Platforms in Indian Railways are allocated dynamically on the day of departure via station display boards. Check station electronic indicators upon arrival for cross-platform transfers and foot overbridge routes.
                      </span>
                    </div>
                  </div>

                  {/* Transfer Layover Node if there is a next leg */}
                  {layoverMins !== undefined && (
                    <div className="p-4 bg-cream-50 rounded-xl border border-cream-300 space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-terracotta" />
                          <span className="font-semibold text-xs text-espresso-900">
                            Interchange at Station <strong className="font-mono text-terracotta">{leg.destination_code}</strong>
                          </span>
                        </div>
                        <TransferAdvisoryBadge
                          transferMinutes={layoverMins}
                          transferStationCode={leg.destination_code}
                          riskLevel={route.layovers?.[idx]?.risk_level}
                          riskDescription={route.layovers?.[idx]?.risk_description}
                          variant="compact"
                        />
                      </div>
                      <p className="text-[11px] text-espresso-600 leading-relaxed">
                        Layover window: <strong>{formatDuration(layoverMins)}</strong>. Next connecting train (Leg {idx + 2}) departs from this station at <strong>{formatTime(route.legs[idx + 1].departure_time)}</strong>. Navigate cross-platform transfers via foot overbridges; station waiting lounges and refreshment facilities are recommended during extended connections.
                      </p>
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="p-4 sm:p-5 border-t border-cream-200 bg-cream-50 flex items-center justify-between gap-3 flex-shrink-0">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="px-3.5 py-2 rounded-xl border border-cream-300 bg-white hover:bg-cream-100 text-espresso-800 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-olive" />
                  <span className="text-olive">Copied!</span>
                </>
              ) : (
                <>
                  <Share2 className="w-3.5 h-3.5 text-espresso-600" />
                  <span>Copy Itinerary</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handlePrint}
              className="px-3.5 py-2 rounded-xl border border-cream-300 bg-white hover:bg-cream-100 text-espresso-800 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm hidden sm:inline-flex"
            >
              <Printer className="w-3.5 h-3.5 text-espresso-600" />
              <span>Print Itinerary</span>
            </button>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 bg-espresso-900 text-cream-100 rounded-xl text-xs font-semibold hover:bg-espresso-800 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

