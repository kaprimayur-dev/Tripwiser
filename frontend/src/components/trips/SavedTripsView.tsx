'use client';

import React, { useState, useEffect } from 'react';
import {
  Bookmark,
  Clock,
  Train,
  ArrowRight,
  Trash2,
  Share2,
  RefreshCw,
  Check,
  Calendar,
  AlertCircle,
  ShieldCheck,
  Compass,
} from 'lucide-react';
import {
  getSavedTrips,
  removeSavedTrip,
  subscribeSavedTrips,
  SavedTrip,
} from '../../lib/savedTrips';
import { buildShareableJourneyUrl, copyToClipboard } from '../../lib/shareUrl';

interface SavedTripsViewProps {
  onRecheckTrip: (trip: SavedTrip) => void;
  onNavigateSearch: () => void;
}

export function SavedTripsView({ onRecheckTrip, onNavigateSearch }: SavedTripsViewProps) {
  const [trips, setTrips] = useState<SavedTrip[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    setTrips(getSavedTrips());
    const unsubscribe = subscribeSavedTrips(() => {
      setTrips(getSavedTrips());
    });
    return unsubscribe;
  }, []);

  const handleRemove = (id: string) => {
    removeSavedTrip(id);
  };

  const handleShare = async (trip: SavedTrip) => {
    const url = buildShareableJourneyUrl({
      originCode: trip.originCode,
      destinationCode: trip.destinationCode,
      journeyDate: trip.journeyDate,
      maxTransfers: trip.maxTransfers,
      routeId: trip.routeId,
    });

    const success = await copyToClipboard(url);
    if (success) {
      setCopiedId(trip.id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const formatDuration = (mins: number) => {
    const hours = Math.floor(mins / 60);
    const minutes = mins % 60;
    if (hours === 0) return `${minutes}m`;
    if (minutes === 0) return `${hours}h`;
    return `${hours}h ${minutes}m`;
  };

  const formatDate = (dateStr: string) => {
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
        return d.toLocaleDateString('en-IN', {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        });
      }
      return dateStr;
    } catch {
      return dateStr;
    }
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return '';
    }
  };

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="bg-white rounded-2xl p-6 sm:p-7 border border-cream-300 shadow-md">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-espresso-900 text-cream-100 flex items-center justify-center shadow-sm">
              <Bookmark className="w-6 h-6 text-terracotta fill-terracotta" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-display text-2xl font-bold text-espresso-900">
                  My Saved Journeys
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cream-200 text-espresso-800 border border-cream-300">
                  {trips.length} Saved
                </span>
              </div>
              <p className="text-xs text-espresso-600 mt-0.5">
                Saved itineraries stored locally in your browser for quick comparison and revisit
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onNavigateSearch}
            className="px-4 py-2 rounded-xl bg-terracotta hover:bg-terracotta/90 text-white text-xs font-bold transition-all shadow-sm self-start sm:self-auto"
          >
            + Search New Journey
          </button>
        </div>

        {/* Timetable Recalculation Note */}
        <div className="mt-4 pt-4 border-t border-cream-200 flex items-start gap-2.5 text-xs text-espresso-700 bg-cream-50 p-3 rounded-xl border border-cream-200">
          <ShieldCheck className="w-4 h-4 text-olive flex-shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            Saved trips capture published railway timetable connections. Train operating days and schedules
            are verified against compiled timetable records. Click <strong>Check Current Schedule</strong> to
            re-query the route with current operating calendars.
          </p>
        </div>
      </div>

      {/* Trips List or Empty State */}
      {trips.length === 0 ? (
        <div className="bg-white rounded-2xl p-10 border border-cream-300 shadow-sm text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-cream-100 text-espresso-600 flex items-center justify-center mx-auto">
            <Bookmark className="w-7 h-7 text-espresso-400" />
          </div>
          <div>
            <h3 className="font-display text-lg font-bold text-espresso-900">
              No Saved Journeys Yet
            </h3>
            <p className="text-xs text-espresso-600 max-w-md mx-auto mt-1 leading-relaxed">
              When searching for train routes, tap the <strong>Save</strong> button on any route card
              or journey details screen to pin it here for easy access.
            </p>
          </div>
          <button
            type="button"
            id="btn-discover-routes-empty"
            onClick={onNavigateSearch}
            className="px-5 py-2.5 rounded-xl bg-espresso-900 text-cream-100 text-xs font-bold hover:bg-espresso-800 transition-colors shadow-sm inline-flex items-center gap-2"
          >
            <Compass className="w-4 h-4 text-terracotta" />
            <span>Discover Railway Routes</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {trips.map((trip) => (
            <div
              key={trip.id}
              id={`saved-trip-card-${trip.id}`}
              className="bg-white rounded-2xl border border-cream-300 hover:border-espresso-500 shadow-sm transition-all p-5 sm:p-6 space-y-4"
            >
              {/* Trip Header & Tags */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-display text-lg font-bold text-espresso-900">
                    {trip.originName} ({trip.originCode})
                  </span>
                  <ArrowRight className="w-4 h-4 text-terracotta flex-shrink-0" />
                  <span className="font-display text-lg font-bold text-espresso-900">
                    {trip.destinationName} ({trip.destinationCode})
                  </span>
                </div>

                <div className="flex items-center gap-1.5 flex-wrap">
                  {trip.isDirect ? (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-olive/15 text-olive">
                      DIRECT SERVICE
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-terracotta/10 text-terracotta">
                      {trip.transferCount} TRANSFER{trip.transferCount > 1 ? 'S' : ''}
                    </span>
                  )}

                  {trip.overallTransferRisk && (
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-cream-100 text-espresso-800 border border-cream-300">
                      {trip.overallTransferRisk.replace('_', ' ')}
                    </span>
                  )}
                </div>
              </div>

              {/* Train Summary & Timetable Line */}
              <div>
                <div className="text-sm font-semibold text-espresso-800">
                  {trip.trainSummary}
                </div>
                <div className="flex items-center gap-3 text-xs text-espresso-600 mt-1 flex-wrap">
                  <span className="flex items-center gap-1 font-medium">
                    <Calendar className="w-3.5 h-3.5 text-espresso-500" />
                    <span>Search Date: {formatDate(trip.journeyDate)}</span>
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1 font-mono font-bold text-terracotta">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{formatDuration(trip.totalDurationMinutes)} Total</span>
                  </span>
                  <span>•</span>
                  <span>
                    {formatDuration(trip.totalTravelTimeMinutes)} on train
                    {trip.totalWaitTimeMinutes > 0 && `, ${formatDuration(trip.totalWaitTimeMinutes)} wait`}
                  </span>
                </div>
              </div>

              {/* Departure & Arrival Snapshot */}
              {trip.departureTime && trip.arrivalTime && (
                <div className="bg-cream-50 rounded-xl p-3 border border-cream-200 flex items-center justify-between text-xs">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-espresso-500 block">Boarding</span>
                    <span className="font-bold text-sm text-espresso-900 font-mono">
                      {formatTime(trip.departureTime)}
                    </span>
                  </div>
                  <div className="text-center text-espresso-500 text-[11px] font-medium">
                    {trip.isDirect ? 'Non-stop route' : `${trip.transferCount} connection`}
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] uppercase font-bold text-espresso-500 block">Arrival</span>
                    <span className="font-bold text-sm text-espresso-900 font-mono">
                      {formatTime(trip.arrivalTime)}
                    </span>
                  </div>
                </div>
              )}

              {/* Action Controls */}
              <div className="pt-3 border-t border-cream-200 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
                <button
                  type="button"
                  id={`btn-recheck-trip-${trip.id}`}
                  onClick={() => onRecheckTrip(trip)}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-xs font-bold transition-colors shadow-sm"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-terracotta" />
                  <span>Check Current Schedule &amp; Search</span>
                </button>

                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <button
                    type="button"
                    id={`btn-share-saved-trip-${trip.id}`}
                    onClick={() => handleShare(trip)}
                    className="p-2 rounded-xl border border-cream-300 bg-white hover:bg-cream-100 text-espresso-700 text-xs font-semibold flex items-center gap-1 transition-colors"
                    title="Copy shareable link"
                  >
                    {copiedId === trip.id ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-olive" />
                        <span className="text-olive font-bold text-[11px]">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Share2 className="w-3.5 h-3.5 text-espresso-600" />
                        <span className="text-[11px]">Share</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    id={`btn-remove-saved-trip-${trip.id}`}
                    onClick={() => handleRemove(trip.id)}
                    className="p-2 rounded-xl border border-red-200 bg-red-50 hover:bg-red-100 text-red-700 text-xs font-semibold flex items-center gap-1 transition-colors"
                    title="Remove from saved trips"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-600" />
                    <span className="text-[11px]">Remove</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

