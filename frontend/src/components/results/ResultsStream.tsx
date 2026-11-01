'use client';

import React, { useState } from 'react';
import { Train, AlertCircle, ArrowRight, Calendar, Compass, RefreshCw } from 'lucide-react';
import { RouteSearchResponse, CandidateRoute } from '../../types/api';
import { RouteCard } from './RouteCard';
import { SortingFilterBar, SortMode } from './SortingFilterBar';
import { RouteComparisonMatrix } from './RouteComparisonMatrix';
import { NearbyAlternativesBanner } from './NearbyAlternativesBanner';
import { JourneyDetailsModal } from './JourneyDetailsModal';
import { InterchangeHubsCard } from '../network/InterchangeHubsCard';

interface ResultsStreamProps {
  data: RouteSearchResponse | null;
  isLoading: boolean;
  error: Error | null;
  currentSort: SortMode;
  onSortChange: (sort: SortMode) => void;
  onSelectCorridor?: (originCode: string, destCode: string) => void;
}

export function ResultsStream({
  data,
  isLoading,
  error,
  currentSort,
  onSortChange,
  onSelectCorridor,
}: ResultsStreamProps) {
  const [activeModalRoute, setActiveModalRoute] = useState<CandidateRoute | null>(null);

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-10 bg-cream-200 rounded-xl w-3/4 max-w-sm" />
        <div className="h-64 bg-white rounded-2xl border border-cream-300 p-6 space-y-4">
          <div className="h-6 bg-cream-200 rounded w-1/3" />
          <div className="h-28 bg-cream-100 rounded-xl" />
          <div className="h-10 bg-cream-200 rounded" />
        </div>
        <div className="h-64 bg-white rounded-2xl border border-cream-300 p-6 space-y-4">
          <div className="h-6 bg-cream-200 rounded w-1/3" />
          <div className="h-28 bg-cream-100 rounded-xl" />
          <div className="h-10 bg-cream-200 rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-2xl p-8 border border-terracotta/30 text-center shadow-sm space-y-3">
        <div className="w-12 h-12 rounded-2xl bg-terracotta/10 text-terracotta flex items-center justify-center mx-auto">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h3 className="font-display text-lg font-bold text-espresso-900">
          Route Search Error
        </h3>
        <p className="text-sm text-espresso-700 max-w-md mx-auto">
          {error.message || 'Unable to retrieve railway routes for this query.'}
        </p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const {
    query,
    origin_station,
    destination_station,
    total_routes_found,
    direct_routes_count,
    transfer_routes_count,
    no_route_reason,
    sorting_note,
    routes,
  } = data;

  // Empty State with specific diagnostic guidance
  if (total_routes_found === 0 || routes.length === 0) {
    let title = 'No Direct or Connecting Trains Found';
    let explanation =
      'No scheduled railway services match the criteria between these two stations on the selected date.';

    if (no_route_reason === 'SAME_ORIGIN_DESTINATION') {
      title = 'Identical Stations Selected';
      explanation = 'Origin and destination stations must be different.';
    } else if (no_route_reason === 'NO_RUNNING_DAYS_MATCH') {
      title = 'Train Does Not Run On This Date';
      explanation =
        'Direct trains exist on this route, but none operate on the selected day of the week. Try changing the journey date.';
    } else if (no_route_reason === 'TRANSFER_BUFFER_VIOLATION') {
      title = 'Connecting Trains Exceed Transfer Window';
      explanation =
        'Connecting trains exist at intermediate hubs, but the transfer layover buffer was either under 30 minutes (unsafe connection) or over 6 hours.';
    } else if (no_route_reason === 'STATION_NOT_FOUND') {
      title = 'Station Not Found in Master';
      explanation = 'One or both station codes could not be located in the railway dataset.';
    }

    return (
      <div className="space-y-4">
        {/* Nearby Alternate Stations Opportunity even when no route found */}
        {onSelectCorridor && (
          <NearbyAlternativesBanner
            currentOriginCode={query.origin}
            currentDestinationCode={query.destination}
            onSelectAlternative={(orig, dest) => onSelectCorridor(orig, dest)}
          />
        )}

        <div className="bg-white rounded-2xl p-8 border border-cream-300 shadow-sm text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-cream-100 text-espresso-700 flex items-center justify-center mx-auto">
            <Compass className="w-6 h-6 text-terracotta" />
          </div>

          <div>
            <h3 className="font-display text-xl font-bold text-espresso-900 mb-1">
              {title}
            </h3>
            <p className="text-sm text-espresso-600 max-w-md mx-auto leading-relaxed">
              {explanation}
            </p>
          </div>

          {/* Suggestion to test compiled real corridors */}
          {onSelectCorridor && (
            <div className="pt-4 border-t border-cream-200 max-w-lg mx-auto">
              <span className="text-xs font-semibold text-espresso-700 block mb-2">
                Try searching a verified railway corridor in the local dataset:
              </span>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => onSelectCorridor('BCT', 'NDLS')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-cream-100 hover:bg-terracotta hover:text-white text-espresso-800 transition-colors"
                >
                  Mumbai (BCT) ➔ Delhi (NDLS)
                </button>
                <button
                  type="button"
                  onClick={() => onSelectCorridor('NDLS', 'BPL')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-cream-100 hover:bg-terracotta hover:text-white text-espresso-800 transition-colors"
                >
                  Delhi (NDLS) ➔ Bhopal (BPL)
                </button>
                <button
                  type="button"
                  onClick={() => onSelectCorridor('NDLS', 'HWH')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-cream-100 hover:bg-terracotta hover:text-white text-espresso-800 transition-colors"
                >
                  Delhi (NDLS) ➔ Kolkata (HWH)
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  const handleSelectRouteFromMatrix = (routeId: string) => {
    const el = document.getElementById(`route-card-${routeId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  return (
    <div className="space-y-6">
      {/* Route Results Header Ribbon */}
      <div className="bg-cream-50 rounded-2xl p-5 border border-cream-300 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-display text-xl font-bold text-espresso-900">
                {origin_station?.name || query.origin} ({query.origin})
              </span>
              <ArrowRight className="w-5 h-5 text-terracotta flex-shrink-0" />
              <span className="font-display text-xl font-bold text-espresso-900">
                {destination_station?.name || query.destination} ({query.destination})
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs text-espresso-600 mt-1 flex-wrap">
              <span className="flex items-center gap-1 font-medium">
                <Calendar className="w-3.5 h-3.5 text-espresso-500" />
                <span>
                  {new Date(query.journey_date).toLocaleDateString('en-IN', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </span>
              </span>
              <span>•</span>
              <span className="font-semibold text-espresso-800">
                {direct_routes_count} Direct, {transfer_routes_count} Connecting
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            <span className="px-2.5 py-1 rounded-md bg-olive/15 text-olive font-bold text-xs uppercase tracking-wider">
              Timetable Confirmed
            </span>
          </div>
        </div>
      </div>

      {/* Corridor Interchange Junctions Discovery (TW-112) */}
      <InterchangeHubsCard
        originCode={query.origin}
        destinationCode={query.destination}
      />

      {/* Nearby Metropolitan Twin Stations Banner */}
      {onSelectCorridor && (
        <NearbyAlternativesBanner
          currentOriginCode={query.origin}
          currentDestinationCode={query.destination}
          onSelectAlternative={(orig, dest) => onSelectCorridor(orig, dest)}
        />
      )}

      {/* Route Comparison Matrix (when >= 2 routes exist) */}
      {routes.length >= 2 && (
        <RouteComparisonMatrix
          routes={routes}
          onSelectRoute={handleSelectRouteFromMatrix}
        />
      )}

      {/* Sorting & Filter Strip */}
      <SortingFilterBar
        currentSort={currentSort}
        onSortChange={onSortChange}
        sortingNote={sorting_note}
        totalRoutes={total_routes_found}
      />

      {/* Candidate Route Cards */}
      <div className="space-y-4">
        {routes.map((route, idx) => (
          <RouteCard
            key={route.route_id}
            route={route}
            isRecommended={idx === 0 && currentSort === 'recommended'}
            onOpenDetails={(r) => setActiveModalRoute(r)}
          />
        ))}
      </div>

      {/* Full Journey Details Modal */}
      <JourneyDetailsModal
        route={activeModalRoute}
        isOpen={Boolean(activeModalRoute)}
        onClose={() => setActiveModalRoute(null)}
        isRecommended={
          Boolean(activeModalRoute) &&
          routes[0]?.route_id === activeModalRoute?.route_id &&
          currentSort === 'recommended'
        }
      />
    </div>
  );
}
