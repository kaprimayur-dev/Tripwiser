'use client';

import React, { useState, useEffect } from 'react';
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
  Bookmark,
  Link,
  Info,
} from 'lucide-react';
import { CandidateRoute, JourneyLeg } from '../../types/api';
import { TransferAdvisoryBadge } from './TransferAdvisoryBadge';
import { IntermediateStopsList } from './IntermediateStopsList';
import {
  isTripSaved,
  saveTrip,
  removeSavedTrip,
  buildTripId,
  subscribeSavedTrips,
  SavedTrip,
} from '../../lib/savedTrips';
import { buildShareableJourneyUrl, copyToClipboard } from '../../lib/shareUrl';

interface JourneyDetailsModalProps {
  route: CandidateRoute | null;
  isOpen: boolean;
  onClose: () => void;
  journeyDate?: string;
  isRecommended?: boolean;
}

export function JourneyDetailsModal({
  route,
  isOpen,
  onClose,
  journeyDate,
  isRecommended = false,
}: JourneyDetailsModalProps) {
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedItinerary, setCopiedItinerary] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [expandedLegs, setExpandedLegs] = useState<Record<number, boolean>>({});

  const firstLeg = route?.legs?.[0];
  const lastLeg = route?.legs ? route.legs[route.legs.length - 1] : undefined;

  const effectiveDate = journeyDate || (firstLeg ? firstLeg.departure_time.split('T')[0] : '');
  const tripId =
    firstLeg && lastLeg && route
      ? buildTripId(firstLeg.origin_code, lastLeg.destination_code, effectiveDate, route.route_id)
      : '';

  useEffect(() => {
    if (tripId) {
      setIsSaved(isTripSaved(tripId));
      const unsubscribe = subscribeSavedTrips(() => {
        setIsSaved(isTripSaved(tripId));
      });
      return unsubscribe;
    }
  }, [tripId]);

  if (!isOpen || !route || !firstLeg || !lastLeg) return null;

  const toggleLeg = (idx: number) => {
    setExpandedLegs((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  const handleToggleSave = () => {
    if (isSaved) {
      removeSavedTrip(tripId);
      setIsSaved(false);
    } else {
      const trainSummary = route.is_direct
        ? `${firstLeg.train_name} (#${firstLeg.train_number})`
        : route.legs.map((l) => `${l.train_name} (#${l.train_number})`).join(' ➔ ');

      const savedData: SavedTrip = {
        id: tripId,
        savedAt: new Date().toISOString(),
        originCode: firstLeg.origin_code,
        originName: firstLeg.origin_code,
        destinationCode: lastLeg.destination_code,
        destinationName: lastLeg.destination_code,
        journeyDate: effectiveDate,
        maxTransfers: route.transfer_count,
        totalDurationMinutes: route.total_duration_minutes,
        totalTravelTimeMinutes: route.total_travel_time_minutes || route.total_duration_minutes,
        totalWaitTimeMinutes: route.total_wait_time_minutes || 0,
        transferCount: route.transfer_count,
        isDirect: route.is_direct,
        trainSummary,
        trainNumbers: route.legs.map((l) => l.train_number),
        departureTime: firstLeg.departure_time,
        arrivalTime: lastLeg.arrival_time,
        overallTransferRisk: route.overall_transfer_risk || null,
        routeId: route.route_id,
      };

      saveTrip(savedData);
      setIsSaved(true);
    }
  };

  const handleShareLink = async () => {
    const url = buildShareableJourneyUrl({
      originCode: firstLeg.origin_code,
      destinationCode: lastLeg.destination_code,
      journeyDate: effectiveDate,
      maxTransfers: route.transfer_count,
      routeId: route.route_id,
    });

    const success = await copyToClipboard(url);
    if (success) {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

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

  const handleCopyItinerary = async () => {
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

    const success = await copyToClipboard(lines.join('\n'));
    if (success) {
      setCopiedItinerary(true);
      setTimeout(() => setCopiedItinerary(false), 2500);
    }
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
                  DIRECT SERVICE
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-terracotta/10 text-terracotta">
                  {route.transfer_count} TRANSFER{route.transfer_count > 1 ? 'S' : ''} VIA {intermediateHub}
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

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              id="modal-btn-toggle-save"
              onClick={handleToggleSave}
              className={`p-2 rounded-xl text-xs font-semibold border transition-all flex items-center gap-1 ${
                isSaved
                  ? 'bg-terracotta text-white border-terracotta shadow-2xs'
                  : 'bg-white hover:bg-cream-100 text-espresso-700 border-cream-300'
              }`}
              title={isSaved ? 'Remove from My Trips' : 'Save to My Trips'}
            >
              <Bookmark className={`w-4 h-4 ${isSaved ? 'fill-white text-white' : 'text-espresso-600'}`} />
            </button>

            <button
              type="button"
              id="modal-close-button"
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white hover:bg-cream-100 border border-cream-300 flex items-center justify-center text-espresso-700 transition-colors"
              title="Close modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-5 sm:p-6 overflow-y-auto space-y-6 flex-1">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-cream-50 p-3.5 rounded-xl border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                Total Duration
              </span>
              <span className="font-display text-lg font-bold text-espresso-900 block mt-0.5">
                {formatDuration(route.total_duration_minutes)}
              </span>
              <span className="text-[11px] text-espresso-600 block mt-0.5">
                {totalDistance} km total
              </span>
            </div>

            <div className="bg-cream-50 p-3.5 rounded-xl border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                Aboard Trains
              </span>
              <span className="font-display text-lg font-bold text-olive block mt-0.5">
                {formatDuration(totalTravelMins)}
              </span>
              <span className="text-[11px] text-espresso-600 block mt-0.5">
                {travelPct}% of journey
              </span>
            </div>

            <div className="bg-cream-50 p-3.5 rounded-xl border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                Transfer Waiting
              </span>
              <span className="font-display text-lg font-bold text-terracotta block mt-0.5">
                {formatDuration(totalWaitMins)}
              </span>
              <span className="text-[11px] text-espresso-600 block mt-0.5">
                {waitPct}% of journey
              </span>
            </div>

            <div className="bg-cream-50 p-3.5 rounded-xl border border-cream-300">
              <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                Legs &amp; Transfers
              </span>
              <span className="font-display text-lg font-bold text-espresso-900 block mt-0.5">
                {route.legs.length} Train{route.legs.length > 1 ? 's' : ''}
              </span>
              <span className="text-[11px] text-espresso-600 block mt-0.5">
                {route.transfer_count === 0 ? 'Direct service' : `${route.transfer_count} transfer`}
              </span>
            </div>
          </div>

          {/* Journey Reliability & Timetable Insights Section */}
          <div className="bg-cream-100/70 rounded-xl p-4 border border-cream-200 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-espresso-900 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-terracotta" />
                <span>Journey Reliability &amp; Timetable Insights</span>
              </span>
              {route.overall_transfer_risk && (
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-cream-200 text-espresso-900 border border-cream-300">
                  Overall Risk: {route.overall_transfer_risk.replace('_', ' ')}
                </span>
              )}
            </div>

            {/* Insight List */}
            {route.insights && route.insights.length > 0 && (
              <ul className="text-xs text-espresso-800 space-y-1.5 list-disc list-inside">
                {route.insights.map((insight, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {insight}
                  </li>
                ))}
              </ul>
            )}

            {/* Explicit Timetable Disclaimer */}
            <div className="pt-2 border-t border-cream-200/70 flex items-start gap-2 text-[11px] text-espresso-600">
              <Info className="w-3.5 h-3.5 text-espresso-500 flex-shrink-0 mt-0.5" />
              <p className="leading-relaxed">
                All metrics and connection classifications are calculated strictly from published timetable data.
                They do not represent live tracking, historical punctuality, or delay probabilities.
                Allow adequate buffer for train delays and platform transfers.
              </p>
            </div>
          </div>

          {/* Chronological Leg Breakdown */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-espresso-600">
              Complete Travel Itinerary
            </h3>

            {route.legs.map((leg, idx) => {
              const isFirst = idx === 0;
              const isLast = idx === route.legs.length - 1;
              const layoverDur = route.transfer_durations_minutes?.[idx];
              const layoverObj = route.layovers?.[idx];
              const isLegExpanded = Boolean(expandedLegs[idx]);

              return (
                <React.Fragment key={idx}>
                  {/* Leg Box */}
                  <div className="border border-cream-300 rounded-xl p-4 bg-white shadow-2xs space-y-3">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-espresso-900 text-cream-100 flex items-center justify-center text-xs font-bold font-mono">
                          {idx + 1}
                        </span>
                        <div>
                          <div className="font-bold text-sm text-espresso-900">
                            {leg.train_name}
                          </div>
                          <div className="text-[11px] text-espresso-600">
                            Train #{leg.train_number} • {leg.distance_km} km • {formatDuration(leg.duration_minutes)}
                          </div>
                        </div>
                      </div>

                      {leg.frequency_description && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cream-100 text-espresso-800">
                          {leg.frequency_description}
                        </span>
                      )}
                    </div>

                    {/* Timeline stops for this leg */}
                    <div className="grid grid-cols-2 gap-4 bg-cream-50 p-3 rounded-lg text-xs">
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                          Board
                        </span>
                        <span className="font-display text-base font-bold text-espresso-900 block">
                          {formatTime(leg.departure_time)}
                        </span>
                        <span className="font-bold text-espresso-800 block">
                          Station {leg.origin_code}
                        </span>
                        <span className="text-[10px] text-espresso-500 block">
                          {formatDate(leg.departure_time)}
                        </span>
                      </div>

                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                          Deboard
                        </span>
                        <span className="font-display text-base font-bold text-espresso-900 block">
                          {formatTime(leg.arrival_time)}
                        </span>
                        <span className="font-bold text-espresso-800 block">
                          Station {leg.destination_code}
                        </span>
                        <span className="text-[10px] text-espresso-500 block">
                          {formatDate(leg.arrival_time)}
                        </span>
                      </div>
                    </div>

                    {/* Intermediate Stops Trigger */}
                    <div>
                      <button
                        type="button"
                        onClick={() => toggleLeg(idx)}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-espresso-700 hover:text-terracotta transition-colors"
                      >
                        <span>
                          {isLegExpanded ? 'Hide' : 'View'}{' '}
                          {leg.intermediate_stop_count !== undefined && leg.intermediate_stop_count > 0
                            ? `${leg.intermediate_stop_count} intermediate halts`
                            : 'intermediate stops'}
                        </span>
                        {isLegExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>

                      {isLegExpanded && (
                        <div className="mt-3 pt-3 border-t border-cream-200">
                          <IntermediateStopsList
                            trainNumber={leg.train_number}
                            fromCode={leg.origin_code}
                            toCode={leg.destination_code}
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Transfer Layover Connector */}
                  {layoverDur !== undefined && (
                    <div className="my-2 p-3 bg-cream-100 rounded-xl border border-cream-300 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-terracotta" />
                        <div>
                          <span className="text-xs font-bold text-espresso-900">
                            Transfer at {leg.destination_code} ({formatDuration(layoverDur)} layover)
                          </span>
                          <span className="text-[11px] text-espresso-600 block">
                            Change from Train #{leg.train_number} to Train #{route.legs[idx + 1].train_number}
                          </span>
                        </div>
                      </div>

                      <TransferAdvisoryBadge
                        transferMinutes={layoverDur}
                        transferStationCode={leg.destination_code}
                        riskLevel={layoverObj?.risk_level}
                        riskDescription={layoverObj?.risk_description}
                        variant="detailed"
                      />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="p-4 sm:p-5 border-t border-cream-200 bg-cream-50 flex items-center justify-between gap-3 flex-shrink-0 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              id="modal-btn-share-link"
              onClick={handleShareLink}
              className="px-3.5 py-2 rounded-xl border border-cream-300 bg-white hover:bg-cream-100 text-espresso-800 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
              title="Copy shareable link"
            >
              {copiedLink ? (
                <>
                  <Check className="w-3.5 h-3.5 text-olive" />
                  <span className="text-olive font-bold">Link Copied!</span>
                </>
              ) : (
                <>
                  <Link className="w-3.5 h-3.5 text-espresso-600" />
                  <span>Share Link</span>
                </>
              )}
            </button>

            <button
              type="button"
              id="modal-btn-copy-itinerary"
              onClick={handleCopyItinerary}
              className="px-3.5 py-2 rounded-xl border border-cream-300 bg-white hover:bg-cream-100 text-espresso-800 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
              title="Copy plain text itinerary"
            >
              {copiedItinerary ? (
                <>
                  <Check className="w-3.5 h-3.5 text-olive" />
                  <span className="text-olive font-bold">Itinerary Copied!</span>
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
              <span>Print</span>
            </button>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 bg-espresso-900 text-cream-100 rounded-xl text-xs font-semibold hover:bg-espresso-800 transition-colors ml-auto"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
