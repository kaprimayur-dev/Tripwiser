import React from 'react';
import { Train, Clock, ArrowRight, ShieldCheck, MapPin } from 'lucide-react';
import { CandidateRoute, JourneyLeg } from '../../types/api';

interface TransitTimelineProps {
  route: CandidateRoute;
}

export function TransitTimeline({ route }: TransitTimelineProps) {
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

  return (
    <div className="pt-4 pb-2 border-t border-cream-200 space-y-4">
      <div className="text-[11px] font-bold uppercase tracking-wider text-espresso-600">
        Itinerary Schedule &amp; Leg Timetable
      </div>

      <div className="space-y-4">
        {route.legs.map((leg: JourneyLeg, index: number) => {
          const layoverDuration =
            route.transfer_durations_minutes && route.transfer_durations_minutes[index];

          return (
            <React.Fragment key={`${leg.train_number}-${index}`}>
              {/* Leg Container */}
              <div className="bg-cream-50 rounded-xl p-4 border border-cream-300">
                {/* Leg Header */}
                <div className="flex items-center justify-between gap-3 mb-3 pb-2.5 border-b border-cream-200">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-6 h-6 rounded-md bg-espresso-900 text-cream-100 flex items-center justify-center text-xs font-bold font-mono">
                      {index + 1}
                    </span>
                    <div className="truncate">
                      <div className="font-semibold text-sm text-espresso-900 truncate">
                        {leg.train_name}
                      </div>
                      <div className="text-[11px] text-espresso-600 font-mono">
                        Train #{leg.train_number}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-olive/15 text-olive">
                      <ShieldCheck className="w-3 h-3" />
                      <span>Timetable Confirmed</span>
                    </span>
                  </div>
                </div>

                {/* Departure & Arrival Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
                  {/* Departure Node */}
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                      Departure
                    </span>
                    <div className="font-display text-lg font-bold text-espresso-900 mt-0.5">
                      {formatTime(leg.departure_time)}
                    </div>
                    <div className="font-semibold text-espresso-800 flex items-center gap-1">
                      <span>Station:</span>
                      <span className="font-mono bg-cream-200 px-1.5 py-0.2 rounded font-bold text-espresso-900">
                        {leg.origin_code}
                      </span>
                    </div>
                    <div className="text-[11px] text-espresso-500 mt-0.5">
                      {formatDate(leg.departure_time)}
                    </div>
                  </div>

                  {/* Arrival Node */}
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                      Arrival
                    </span>
                    <div className="font-display text-lg font-bold text-espresso-900 mt-0.5">
                      {formatTime(leg.arrival_time)}
                    </div>
                    <div className="font-semibold text-espresso-800 flex items-center gap-1">
                      <span>Station:</span>
                      <span className="font-mono bg-cream-200 px-1.5 py-0.2 rounded font-bold text-espresso-900">
                        {leg.destination_code}
                      </span>
                    </div>
                    <div className="text-[11px] text-espresso-500 mt-0.5">
                      {formatDate(leg.arrival_time)}
                    </div>
                  </div>

                  {/* Leg Metrics */}
                  <div className="col-span-2 sm:col-span-1 border-t sm:border-t-0 sm:border-l border-cream-200 pt-2 sm:pt-0 sm:pl-4 flex sm:flex-col justify-between sm:justify-center">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-espresso-500">
                        Leg Duration
                      </span>
                      <div className="font-semibold text-espresso-800">
                        {formatDuration(leg.duration_minutes)}
                      </div>
                    </div>
                    <div className="sm:mt-2">
                      <span className="text-[10px] uppercase font-bold text-espresso-500">
                        Distance
                      </span>
                      <div className="font-semibold text-espresso-800">
                        {leg.distance_km} km
                      </div>
                    </div>
                  </div>
                </div>

                {/* Seat Availability & Fare Honest Notice */}
                <div className="mt-3 pt-2.5 border-t border-cream-200 flex items-center justify-between text-[11px] text-espresso-600">
                  <span>Seat Availability: <strong className="text-espresso-800 font-semibold">Live feed deferred</strong></span>
                  <span>Fare: <strong className="text-espresso-800 font-semibold">Feed deferred</strong></span>
                </div>
              </div>

              {/* Transfer Layover Hub Marker (if there is another leg) */}
              {layoverDuration !== undefined && (
                <div className="flex items-center gap-3 py-1 px-3">
                  <div className="w-8 flex justify-center">
                    <div className="w-0.5 h-10 bg-terracotta border-dashed"></div>
                  </div>
                  <div className="flex-1 bg-terracotta/10 rounded-xl p-3 border border-terracotta/20 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-terracotta" />
                      <div>
                        <span className="font-semibold text-espresso-900">
                          {formatDuration(layoverDuration)} Transfer Window
                        </span>
                        <span className="text-espresso-600 block text-[11px]">
                          Change trains at station <strong className="font-mono text-terracotta font-bold">{leg.destination_code}</strong>
                        </span>
                      </div>
                    </div>

                    <span className="text-[10px] font-bold uppercase tracking-wider text-terracotta bg-white px-2 py-1 rounded border border-terracotta/20">
                      Coordinated Hub
                    </span>
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

