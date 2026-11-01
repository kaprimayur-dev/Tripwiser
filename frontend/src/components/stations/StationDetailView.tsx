'use client';

import React, { useState, useEffect } from 'react';
import {
  MapPin,
  Navigation,
  Compass,
  Train,
  ShieldCheck,
  AlertCircle,
  Loader2,
  ArrowRight,
  Layers,
  X,
  ExternalLink,
} from 'lucide-react';
import { Station, StationDetail, NearbyStationItem } from '../../types/api';
import { getStationDetails, getNearbyStationsByCode } from '../../services/api';

interface StationDetailViewProps {
  stationCode: string;
  onClose?: () => void;
  onSelectAsOrigin: (station: Station) => void;
  onSelectAsDestination: (station: Station) => void;
  onInspectStation: (stationCode: string) => void;
}

const RADIUS_OPTIONS = [15, 30, 50, 75];

export function StationDetailView({
  stationCode,
  onClose,
  onSelectAsOrigin,
  onSelectAsDestination,
  onInspectStation,
}: StationDetailViewProps) {
  const [stationData, setStationData] = useState<StationDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Nearby stations state
  const [radiusKm, setRadiusKm] = useState<number>(30);
  const [nearbyStations, setNearbyStations] = useState<NearbyStationItem[]>([]);
  const [nearbyLoading, setNearbyLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!stationCode) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    getStationDetails(stationCode)
      .then((data) => {
        if (isMounted) {
          if (!data) {
            setError(`Station '${stationCode}' not found in railway database.`);
          } else {
            setStationData(data);
          }
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || `Failed to load details for station '${stationCode}'`);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [stationCode]);

  useEffect(() => {
    if (!stationCode || !stationData) return;

    let isMounted = true;
    setNearbyLoading(true);

    getNearbyStationsByCode(stationCode, radiusKm, 20)
      .then((items) => {
        if (isMounted) {
          setNearbyStations(items);
          setNearbyLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setNearbyStations([]);
          setNearbyLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [stationCode, stationData, radiusKm]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-cream-300 p-8 text-center space-y-3 shadow-sm animate-fade-in">
        <Loader2 className="w-8 h-8 animate-spin text-terracotta mx-auto" />
        <div className="font-display font-bold text-lg text-espresso-900">
          Loading Station Intelligence for {stationCode}...
        </div>
        <p className="text-xs text-espresso-600">
          Querying PostGIS coordinates, location metadata, and verified timetable coverage.
        </p>
      </div>
    );
  }

  if (error || !stationData) {
    return (
      <div className="bg-white rounded-2xl border border-red-200 p-6 shadow-sm space-y-3 animate-fade-in">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-6 h-6 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-display text-base font-bold text-red-900">
              Station Not Found
            </h3>
            <p className="text-xs text-red-700 mt-1">
              {error || `No records found matching station code '${stationCode}'.`}
            </p>
            <div className="mt-3 p-3 bg-red-50 rounded-xl text-xs text-red-800 border border-red-100">
              <span className="font-semibold">Zero-Fabrication Policy:</span> TripWiser never creates synthetic stations or artificial coordinates. Only genuinely cataloged railway stations are rendered.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { code, name, city, state, zone, latitude, longitude, timetable_coverage } = stationData;

  return (
    <div id="station-detail-view" className="space-y-6 animate-fade-in">
      {/* Station Header Banner */}
      <div className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cream-200 pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-espresso-900 text-cream-100 font-mono">
                {code}
              </span>
              {zone && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cream-200 text-espresso-800">
                  Zone: {zone}
                </span>
              )}
              {timetable_coverage.has_timetable_coverage ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-olive/15 text-olive flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Timetable Verified</span>
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cream-300/80 text-espresso-600 flex items-center gap-1">
                  <span>Network Station</span>
                </span>
              )}
            </div>

            <h1 className="font-display text-2xl sm:text-3xl font-bold text-espresso-900">
              {name}
            </h1>
            <div className="text-xs text-espresso-600 mt-1 flex items-center gap-2 flex-wrap">
              <span className="flex items-center gap-1 text-espresso-800 font-medium">
                <MapPin className="w-3.5 h-3.5 text-terracotta" />
                {[city, state].filter(Boolean).join(', ') || 'Indian Railways Network'}
              </span>
              <span>•</span>
              <span className="font-mono text-espresso-600">
                {latitude.toFixed(4)}° N, {longitude.toFixed(4)}° E
              </span>
            </div>
          </div>

          <div className="flex items-center sm:flex-col sm:items-end justify-between gap-3 pt-2 sm:pt-0">
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="order-last sm:order-first inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-espresso-600 hover:text-espresso-900 bg-cream-200/70 hover:bg-cream-300 transition-colors"
                title="Close station inspector"
              >
                <X className="w-3.5 h-3.5" />
                <span>Close</span>
              </button>
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                id="btn-use-as-origin"
                onClick={() => onSelectAsOrigin(stationData)}
                className="px-3 py-1.5 rounded-xl bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-xs font-semibold transition-colors shadow-sm"
              >
                Set as Origin
              </button>
              <button
                type="button"
                id="btn-use-as-destination"
                onClick={() => onSelectAsDestination(stationData)}
                className="px-3 py-1.5 rounded-xl bg-terracotta hover:bg-terracotta/90 text-white text-xs font-semibold transition-colors shadow-sm"
              >
                Set as Destination
              </button>
            </div>
          </div>
        </div>

        {/* Timetable Coverage Metrics Strip */}
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block mb-2">
            Timetable Schedule Coverage
          </span>

          {timetable_coverage.has_timetable_coverage ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-cream-50 p-3.5 rounded-xl border border-cream-300">
                <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                  Compiled Trains Calling
                </span>
                <div className="font-display text-xl font-bold text-espresso-900 mt-0.5">
                  {timetable_coverage.total_compiled_trains}
                </div>
                <p className="text-[11px] text-espresso-600 mt-0.5">
                  Scheduled stopping or passing trains
                </p>
              </div>

              <div className="bg-cream-50 p-3.5 rounded-xl border border-cream-300">
                <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                  Originating Trains
                </span>
                <div className="font-display text-xl font-bold text-espresso-900 mt-0.5">
                  {timetable_coverage.originating_trains_count}
                </div>
                <p className="text-[11px] text-espresso-600 mt-0.5">
                  Trains starting their journey from here
                </p>
              </div>

              <div className="bg-cream-50 p-3.5 rounded-xl border border-cream-300">
                <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">
                  Terminating Trains
                </span>
                <div className="font-display text-xl font-bold text-espresso-900 mt-0.5">
                  {timetable_coverage.terminating_trains_count}
                </div>
                <p className="text-[11px] text-espresso-600 mt-0.5">
                  Trains completing their journey here
                </p>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-cream-50 rounded-xl border border-cream-200 text-xs text-espresso-700 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-espresso-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-espresso-900">Awaiting Compiled Schedule Deployments:</span>{' '}
                {timetable_coverage.coverage_note}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Nearby Stations Discovery Section */}
      <div className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cream-200 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Navigation className="w-4 h-4 text-olive" />
              <h3 className="font-display text-lg font-bold text-espresso-900">
                Nearby Railway Stations
              </h3>
            </div>
            <p className="text-xs text-espresso-600 mt-0.5">
              Discovered using PostGIS geodetic distance calculations from {name} ({code})
            </p>
          </div>

          {/* Spatial Radius Selector */}
          <div className="flex items-center gap-1.5 bg-cream-100 p-1 rounded-xl border border-cream-300 self-start sm:self-auto text-xs">
            <span className="text-[10px] uppercase font-bold text-espresso-500 px-1.5">Radius:</span>
            {RADIUS_OPTIONS.map((r) => (
              <button
                key={r}
                id={`radius-btn-${r}`}
                type="button"
                onClick={() => setRadiusKm(r)}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                  radiusKm === r
                    ? 'bg-white text-espresso-900 shadow-sm font-bold'
                    : 'text-espresso-600 hover:text-espresso-900'
                }`}
              >
                {r} km
              </button>
            ))}
          </div>
        </div>

        {/* Nearby Station Cards */}
        {nearbyLoading ? (
          <div className="py-8 text-center text-xs text-espresso-600 flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-terracotta" />
            <span>Calculating geodetic distances across railway stations...</span>
          </div>
        ) : nearbyStations.length === 0 ? (
          <div className="p-6 text-center rounded-xl bg-cream-50 border border-cream-200 text-xs text-espresso-600">
            No railway stations found within {radiusKm} km of {name} ({code}). Try increasing the search radius above.
          </div>
        ) : (
          <div className="space-y-2.5" id="nearby-stations-list">
            <div className="text-[11px] text-espresso-500 font-medium">
              Found {nearbyStations.length} railway stations within {radiusKm} km (sorted nearest first):
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {nearbyStations.map(({ station: s, distance_km }, idx) => (
                <div
                  key={s.code}
                  id={`nearby-station-card-${idx}`}
                  data-testid="nearby-station-card"
                  className="bg-cream-50/70 hover:bg-cream-100/70 transition-all rounded-xl border border-cream-200 p-3.5 space-y-2.5 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-xs font-bold bg-cream-200 text-espresso-900 px-1.5 py-0.5 rounded">
                            {s.code}
                          </span>
                          <span className="font-bold text-espresso-900 text-sm line-clamp-1">
                            {s.name}
                          </span>
                        </div>
                        <div className="text-[11px] text-espresso-500 mt-0.5">
                          {[s.city, s.state].filter(Boolean).join(', ') || 'Railway Station'}
                        </div>
                      </div>

                      <div className="text-right flex-shrink-0">
                        <span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-bold bg-olive/15 text-olive">
                          {distance_km.toFixed(1)} km
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="pt-2 border-t border-cream-200 flex items-center justify-between gap-2 text-xs">
                    <button
                      type="button"
                      onClick={() => onInspectStation(s.code)}
                      className="text-espresso-600 hover:text-espresso-900 font-semibold text-[11px] flex items-center gap-1"
                    >
                      <span>Inspect</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>

                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        id={`btn-set-origin-${idx}`}
                        onClick={() => onSelectAsOrigin(s)}
                        className="px-2.5 py-1 rounded-lg bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-[11px] font-semibold transition-colors"
                      >
                        Boarding
                      </button>
                      <button
                        type="button"
                        id={`btn-set-dest-${idx}`}
                        onClick={() => onSelectAsDestination(s)}
                        className="px-2.5 py-1 rounded-lg bg-terracotta hover:bg-terracotta/90 text-white text-[11px] font-semibold transition-colors"
                      >
                        Destination
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Spatial Integrity Notice */}
        <div className="p-3 bg-cream-50 rounded-xl text-[11px] text-espresso-600 border border-cream-200 space-y-1">
          <div className="font-semibold text-espresso-800 flex items-center gap-1">
            <Compass className="w-3.5 h-3.5 text-olive" />
            <span>Spatial Proximity Disclaimer</span>
          </div>
          <p>
            Distances reflect true spherical geodetic distance between station coordinates. Being geographically nearby does not imply direct track connectivity or scheduled train frequency between the stations. Use journey search to verify rail connections.
          </p>
        </div>
      </div>
    </div>
  );
}
