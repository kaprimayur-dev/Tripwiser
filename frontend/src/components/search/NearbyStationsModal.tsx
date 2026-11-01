'use client';

import React, { useState } from 'react';
import { MapPin, Navigation, X, Loader2, AlertCircle, ArrowRight } from 'lucide-react';
import { Station, NearbyStationItem } from '../../types/api';
import { getNearbyStations } from '../../services/api';

interface NearbyStationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectStation: (station: Station, role: 'origin' | 'destination') => void;
}

export function NearbyStationsModal({
  isOpen,
  onClose,
  onSelectStation,
}: NearbyStationsModalProps) {
  const [radiusKm, setRadiusKm] = useState<number>(30);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [stations, setStations] = useState<NearbyStationItem[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [locationStatus, setLocationStatus] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFetchNearby = (lat: number, lon: number, radius = radiusKm) => {
    setIsLoading(true);
    setErrorMessage(null);

    getNearbyStations(lat, lon, radius)
      .then((items) => {
        setStations(items);
        if (items.length === 0) {
          setLocationStatus(`No railway stations found within ${radius} km.`);
        } else {
          setLocationStatus(`Found ${items.length} station${items.length === 1 ? '' : 's'} within ${radius} km.`);
        }
      })
      .catch((err) => {
        console.error('Nearby station error:', err);
        setErrorMessage('Failed to fetch nearby stations. Please try again or search directly by station name.');
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  const handleUseGeolocation = () => {
    if (!navigator.geolocation) {
      setErrorMessage('Geolocation is not supported by your browser. You can still search stations directly.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setLocationStatus('Locating your position...');

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        setLocationStatus(`Latitude: ${latitude.toFixed(2)}, Longitude: ${longitude.toFixed(2)}`);
        handleFetchNearby(latitude, longitude, radiusKm);
      },
      (err) => {
        setIsLoading(false);
        // Denying location permission must never break the experience
        if (err.code === err.PERMISSION_DENIED) {
          setErrorMessage('Location access was denied. You can search stations by name, code or city instead.');
        } else {
          setErrorMessage('Could not determine current location. Try searching for your station above.');
        }
        setLocationStatus(null);
      },
      { timeout: 10000, enableHighAccuracy: false }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-espresso-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 border border-cream-300 shadow-2xl relative max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-cream-200">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-olive/15 text-olive flex items-center justify-center">
              <Navigation className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-display text-lg font-bold text-espresso-900">
                Nearby Railway Stations
              </h3>
              <p className="text-xs text-espresso-600">
                PostGIS spatial proximity discovery
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full text-espresso-500 hover:text-espresso-900 hover:bg-cream-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="py-4 space-y-4 overflow-y-auto flex-1">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-cream-50 p-3.5 rounded-xl border border-cream-300">
            <button
              type="button"
              onClick={handleUseGeolocation}
              disabled={isLoading}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-espresso-900 text-cream-100 rounded-lg text-xs font-semibold hover:bg-espresso-800 transition-colors disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin text-cream-100" />
              ) : (
                <Navigation className="w-4 h-4 text-terracotta" />
              )}
              <span>Use My Current Location</span>
            </button>

            {/* Radius options */}
            <div className="flex items-center gap-1.5 justify-end">
              <span className="text-[11px] font-semibold text-espresso-600 mr-1">Radius:</span>
              {[15, 30, 50].map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => {
                    setRadiusKm(r);
                    // If we have previous search, re-fetch
                  }}
                  className={`px-2.5 py-1 text-xs rounded-md font-semibold transition-colors ${
                    radiusKm === r
                      ? 'bg-olive text-white'
                      : 'bg-cream-200 text-espresso-700 hover:bg-cream-300'
                  }`}
                >
                  {r} km
                </button>
              ))}
            </div>
          </div>

          {/* Status Message */}
          {locationStatus && (
            <p className="text-xs text-olive font-medium px-1 flex items-center gap-1.5">
              <span>{locationStatus}</span>
            </p>
          )}

          {/* Error Message */}
          {errorMessage && (
            <div className="p-3 bg-terracotta/10 border border-terracotta/20 rounded-xl flex items-start gap-2.5 text-xs text-terracotta">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Station List */}
          {stations.length > 0 && (
            <div className="space-y-2 pt-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-espresso-500">
                Nearby Results
              </div>

              {stations.map(({ station, distance_km }) => (
                <div
                  key={station.code}
                  className="p-3 rounded-xl border border-cream-300 bg-white hover:bg-cream-50 transition-colors flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-espresso-900 truncate">
                        {station.name}
                      </span>
                      <span className="font-mono text-xs font-bold px-1.5 py-0.2 rounded bg-cream-100 text-espresso-800 border border-cream-300">
                        {station.code}
                      </span>
                    </div>
                    <div className="text-xs text-espresso-600 mt-0.5">
                      {[station.city, station.state].filter(Boolean).join(', ')} •{' '}
                      <span className="font-semibold text-olive">{distance_km} km away</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => {
                        onSelectStation(station, 'origin');
                        onClose();
                      }}
                      className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-cream-100 text-espresso-800 hover:bg-terracotta hover:text-white transition-colors"
                      title="Set as Origin Station"
                    >
                      From
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        onSelectStation(station, 'destination');
                        onClose();
                      }}
                      className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-cream-100 text-espresso-800 hover:bg-olive hover:text-white transition-colors"
                      title="Set as Destination Station"
                    >
                      To
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Quick Demo Coordinates for Delhi/Mumbai/Kolkata hubs */}
          {!stations.length && !isLoading && (
            <div className="pt-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-espresso-500 mb-2">
                Quick Test Coordinates
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => handleFetchNearby(28.6139, 77.209, radiusKm)}
                  className="p-2.5 rounded-lg border border-cream-300 bg-cream-50 hover:bg-cream-100 text-left transition-colors"
                >
                  <div className="font-semibold text-espresso-900">Delhi Hub Region</div>
                  <div className="text-[11px] text-espresso-600">NDLS, NZM, DLI area (28.61, 77.20)</div>
                </button>
                <button
                  type="button"
                  onClick={() => handleFetchNearby(18.9696, 72.8193, radiusKm)}
                  className="p-2.5 rounded-lg border border-cream-300 bg-cream-50 hover:bg-cream-100 text-left transition-colors"
                >
                  <div className="font-semibold text-espresso-900">Mumbai Hub Region</div>
                  <div className="text-[11px] text-espresso-600">BCT, CSMT area (18.97, 72.82)</div>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

