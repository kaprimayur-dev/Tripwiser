'use client';

import React, { useState, useEffect } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Clock,
  Train,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  FileText,
  Bookmark,
  Share2,
  Check,
  Info,
  Compass,
} from 'lucide-react';
import { CandidateRoute } from '../../types/api';
import { TransitTimeline } from './TransitTimeline';
import { TransferAdvisoryBadge } from './TransferAdvisoryBadge';
import {
  isTripSaved,
  saveTrip,
  removeSavedTrip,
  buildTripId,
  subscribeSavedTrips,
  SavedTrip,
} from '../../lib/savedTrips';
import {
  addRouteToJourneyPlan,
  buildPlanId,
  isRouteInPlan,
  subscribeJourneyPlans,
} from '../../lib/journeyPlans';
import { buildShareableJourneyUrl, copyToClipboard } from '../../lib/shareUrl';

interface RouteCardProps {
  route: CandidateRoute;
  journeyDate?: string;
  isRecommended?: boolean;
  onOpenDetails?: (route: CandidateRoute) => void;
  onOpenPlanWorkspace?: () => void;
}

export function RouteCard({
  route,
  journeyDate,
  isRecommended = false,
  onOpenDetails,
  onOpenPlanWorkspace,
}: RouteCardProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(isRecommended);
  const [isSaved, setIsSaved] = useState<boolean>(false);
  const [isInPlan, setIsInPlan] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const firstLeg = route.legs[0];
  const lastLeg = route.legs[route.legs.length - 1];

  // Derive active date from firstLeg departure if not passed
  const effectiveDate = journeyDate || firstLeg.departure_time.split('T')[0];
  const tripId = buildTripId(
    firstLeg.origin_code,
    lastLeg.destination_code,
    effectiveDate,
    route.route_id
  );
  const planId = buildPlanId(firstLeg.origin_code, lastLeg.destination_code, effectiveDate);

  useEffect(() => {
    setIsSaved(isTripSaved(tripId));
    setIsInPlan(isRouteInPlan(planId, route.route_id));

    const unsubscribe1 = subscribeSavedTrips(() => {
      setIsSaved(isTripSaved(tripId));
    });
    const unsubscribe2 = subscribeJourneyPlans(() => {
      setIsInPlan(isRouteInPlan(planId, route.route_id));
    });

    return () => {
      unsubscribe1();
      unsubscribe2();
    };
  }, [tripId, planId, route.route_id]);

  const handleAddToPlan = () => {
    if (isInPlan) {
      if (onOpenPlanWorkspace) {
        onOpenPlanWorkspace();
      }
      return;
    }
    addRouteToJourneyPlan(
      firstLeg.origin_code,
      firstLeg.origin_code,
      lastLeg.destination_code,
      lastLeg.destination_code,
      effectiveDate,
      route.transfer_count,
      route
    );
    setIsInPlan(true);
    setIsSaved(true);
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
      addRouteToJourneyPlan(
        firstLeg.origin_code,
        firstLeg.origin_code,
        lastLeg.destination_code,
        lastLeg.destination_code,
        effectiveDate,
        route.transfer_count,
        route
      );
      setIsSaved(true);
      setIsInPlan(true);
    }
  };

  const handleShare = async () => {
    const url = buildShareableJourneyUrl({
      originCode: firstLeg.origin_code,
      destinationCode: lastLeg.destination_code,
      journeyDate: effectiveDate,
      maxTransfers: route.transfer_count,
      routeId: route.route_id,
    });

    const success = await copyToClipboard(url);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
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

  // Find intermediate hubs
  const intermediateHubs = route.legs.slice(0, -1).map((leg) => leg.destination_code);
  const intermediateHub = intermediateHubs.join(', ');
  const layoverMinutes = route.transfer_durations_minutes?.[0];

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

  // Determine card border styling based on route type
  const cardBorderClass = isRecommended
    ? 'border-terracotta/50 shadow-md ring-1 ring-terracotta/25'
    : route.is_direct
    ? 'border-olive/40 hover:border-olive shadow-sm'
    : route.transfer_count === 1
    ? 'border-cream-300 hover:border-terracotta/60 shadow-sm'
    : 'border-cream-300 hover:border-espresso-600 shadow-sm';

  return (
    <div
      id={`route-card-${route.route_id}`}
      className={`bg-white rounded-2xl border transition-all duration-200 overflow-hidden ${cardBorderClass}`}
    >
      <div className="p-5 sm:p-6 space-y-4">
        {/* Top Badges, Transfer Advisory & Action Buttons */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {isRecommended && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-espresso-900 text-cream-100 shadow-sm">
                <Sparkles className="w-3.5 h-3.5 text-terracotta" />
                <span>RECOMMENDED ROUTE</span>
              </span>
            )}

            {route.is_direct ? (
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-olive/15 text-olive border border-olive/30">
                DIRECT SERVICE
              </span>
            ) : route.transfer_count === 1 ? (
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-terracotta/10 text-terracotta border border-terracotta/20">
                1 TRANSFER VIA {intermediateHub}
              </span>
            ) : (
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-espresso-800 text-cream-100 border border-espresso-900">
                {route.transfer_count} TRANSFERS VIA {intermediateHub}
              </span>
            )}

            {!route.is_direct && route.transfer_durations_minutes && route.transfer_durations_minutes.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                {route.transfer_durations_minutes.map((dur, i) => (
                  <TransferAdvisoryBadge
                    key={i}
                    transferMinutes={dur}
                    transferStationCode={intermediateHubs[i]}
                    riskLevel={route.layovers?.[i]?.risk_level}
                    riskDescription={route.layovers?.[i]?.risk_description}
                    variant="compact"
                  />
                ))}
              </div>
            )}
          </div>

          {/* Plan, Save & Share Action Buttons */}
          <div className="flex items-center gap-1.5 ml-auto">
            <button
              type="button"
              id={`btn-plan-route-${route.route_id}`}
              onClick={handleAddToPlan}
              className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold border transition-all flex items-center gap-1.5 ${
                isInPlan
                  ? 'bg-olive text-white border-olive shadow-2xs font-bold'
                  : 'bg-cream-100 hover:bg-cream-200 text-espresso-800 border-cream-300'
              }`}
              title={isInPlan ? 'Already in Journey Plan — Click to view workspace' : 'Add this option to Journey Plan'}
            >
              <Compass className={`w-3.5 h-3.5 ${isInPlan ? 'text-white' : 'text-terracotta'}`} />
              <span className="text-[11px]">{isInPlan ? 'In Plan' : 'Add to Plan'}</span>
            </button>

            <button
              type="button"
              id={`btn-share-route-${route.route_id}`}
              onClick={handleShare}
              className={`p-2 rounded-xl text-xs font-semibold border transition-all flex items-center gap-1 ${
                copied
                  ? 'bg-olive text-white border-olive'
                  : 'bg-cream-50 hover:bg-cream-100 text-espresso-700 border-cream-300'
              }`}
              title="Share shareable journey link"
              aria-label="Share journey link"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span className="text-[11px] font-bold">Copied!</span>
                </>
              ) : (
                <>
                  <Share2 className="w-3.5 h-3.5 text-espresso-600" />
                  <span className="hidden sm:inline text-[11px]">Share</span>
                </>
              )}
            </button>

            <button
              type="button"
              id={`btn-save-route-${route.route_id}`}
              onClick={handleToggleSave}
              className={`p-2 rounded-xl text-xs font-semibold border transition-all flex items-center gap-1 ${
                isSaved
                  ? 'bg-terracotta text-white border-terracotta shadow-2xs'
                  : 'bg-cream-50 hover:bg-cream-100 text-espresso-700 border-cream-300'
              }`}
              title={isSaved ? 'Remove from My Trips' : 'Save journey to My Trips'}
              aria-label={isSaved ? 'Remove from My Trips' : 'Save journey to My Trips'}
            >
              <Bookmark className={`w-3.5 h-3.5 ${isSaved ? 'fill-white text-white' : 'text-espresso-600'}`} />
              <span className="hidden sm:inline text-[11px]">{isSaved ? 'Saved' : 'Save'}</span>
            </button>
          </div>
        </div>

        {/* Train Overview Banner */}
        <div>
          <h3 className="font-display text-lg font-bold text-espresso-900 leading-snug">
            {route.is_direct
              ? `${firstLeg.train_name} (#${firstLeg.train_number})`
              : route.transfer_count === 1
              ? `Coordinated Route: ${firstLeg.train_name} ➔ ${lastLeg.train_name}`
              : `Multi-Leg Journey: ${route.legs.map((l) => l.train_name).join(' ➔ ')}`}
          </h3>
          <p className="text-xs text-espresso-600 mt-0.5">
            {route.is_direct
              ? `Direct service from ${firstLeg.origin_code} to ${lastLeg.destination_code}`
              : route.transfer_count === 1
              ? `Change trains at ${intermediateHub} (${layoverMinutes || 0}m layover)`
              : `Transfers at ${intermediateHubs.map((h, i) => `${h} (${route.transfer_durations_minutes[i]}m)`).join(', ')}`}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {firstLeg.frequency_description && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-cream-200 text-espresso-800">
                {firstLeg.frequency_description}
              </span>
            )}
            {route.is_direct && firstLeg.intermediate_stop_count !== undefined && firstLeg.intermediate_stop_count > 0 && (
              <span className="text-[11px] text-espresso-600 font-medium">
                • {firstLeg.intermediate_stop_count} intermediate halts
              </span>
            )}
          </div>
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

            <span className="text-[11px] text-espresso-600 mt-1 font-medium text-center">
              {route.is_direct
                ? `${firstLeg.distance_km} km direct`
                : `${layoverMinutes || 0}m layover at ${intermediateHub}`}
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

        {/* Journey Time Breakdown Strip */}
        <div className="bg-cream-100/70 rounded-xl p-3 border border-cream-200 space-y-2">
          <div className="flex items-center justify-between text-xs flex-wrap gap-2">
            <span className="font-bold text-espresso-900 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-terracotta" />
              <span>Journey Time Breakdown:</span>
            </span>
            <div className="flex items-center gap-3 text-[11px] text-espresso-700 font-medium">
              <span>
                <strong className="text-olive font-bold">{formatDuration(totalTravelMins)}</strong> aboard train ({travelPct}%)
              </span>
              {!route.is_direct && (
                <span>
                  • <strong className="text-terracotta font-bold">{formatDuration(totalWaitMins)}</strong> transfer waiting ({waitPct}%)
                </span>
              )}
            </div>
          </div>

          {/* Visual Ratio Bar */}
          {!route.is_direct && (
            <div className="w-full h-1.5 rounded-full bg-cream-300 overflow-hidden flex">
              <div
                className="bg-olive h-full transition-all"
                style={{ width: `${travelPct}%` }}
                title={`Travelling: ${travelPct}%`}
              />
              <div
                className="bg-terracotta h-full transition-all"
                style={{ width: `${waitPct}%` }}
                title={`Waiting: ${waitPct}%`}
              />
            </div>
          )}

          {/* Factual Journey Insights */}
          {route.insights && route.insights.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap pt-1.5 border-t border-cream-200/60 text-[11px]">
              <span className="font-semibold text-espresso-800">Insights:</span>
              {route.insights.map((insight, idx) => (
                <span
                  key={idx}
                  data-testid="journey-insight-pill"
                  className="px-2 py-0.5 rounded bg-white text-espresso-700 font-medium border border-cream-300 shadow-2xs"
                >
                  {insight}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Timetable vs Live Availability Honest Notice */}
        <div className="flex items-center justify-between gap-2 text-[11px] text-espresso-600 bg-cream-50/60 px-3 py-1.5 rounded-lg border border-cream-200/70 flex-wrap">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-olive flex-shrink-0" />
            <span>Scheduled Timetable Records</span>
          </div>
          <div className="flex items-center gap-1 text-espresso-500">
            <Info className="w-3 h-3 text-espresso-400" />
            <span>Live seat status and delay feeds deferred</span>
          </div>
        </div>

        {/* Action Controls: Details Modal and Timeline Toggle */}
        <div className="pt-3 border-t border-cream-200 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2">
          {onOpenDetails && (
            <button
              type="button"
              id={`btn-open-details-${route.route_id}`}
              onClick={() => onOpenDetails(route)}
              className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-espresso-900 text-cream-100 text-xs font-semibold hover:bg-espresso-800 transition-colors shadow-sm min-h-[38px]"
            >
              <FileText className="w-3.5 h-3.5 text-terracotta" />
              <span>Full Journey Details &amp; Itinerary</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-bold text-espresso-800 hover:text-terracotta transition-colors self-center sm:self-auto min-h-[38px]"
          >
            <span>{isExpanded ? 'Hide Leg Timetable' : 'Quick Leg Timetable'}</span>
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>

        {/* Accordion Content */}
        {isExpanded && <TransitTimeline route={route} />}
      </div>
    </div>
  );
}
