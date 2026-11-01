'use client';

import React, { useState, useEffect } from 'react';
import {
  ArrowLeftRight,
  Calendar,
  Search,
  Filter,
  Sparkles,
  Loader2,
  AlertCircle,
  Clock,
} from 'lucide-react';
import { Station } from '../../types/api';
import { StationAutocomplete } from './StationAutocomplete';
import { NearbyStationsModal } from './NearbyStationsModal';

interface JourneySearchCardProps {
  initialOrigin?: Station | null;
  initialDestination?: Station | null;
  initialDate?: string;
  initialMaxTransfers?: number;
  isLoading?: boolean;
  onSearch: (params: {
    origin: Station;
    destination: Station;
    date: string;
    maxTransfers: number;
  }) => void;
}

export function JourneySearchCard({
  initialOrigin = null,
  initialDestination = null,
  initialDate,
  initialMaxTransfers = 1,
  isLoading = false,
  onSearch,
}: JourneySearchCardProps) {
  // Compute default date: today + 1 (tomorrow)
  const getTomorrowString = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  };

  const [origin, setOrigin] = useState<Station | null>(initialOrigin);
  const [destination, setDestination] = useState<Station | null>(initialDestination);
  const [date, setDate] = useState<string>(initialDate || getTomorrowString());
  const [maxTransfers, setMaxTransfers] = useState<number>(initialMaxTransfers);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isNearbyModalOpen, setIsNearbyModalOpen] = useState<boolean>(false);
  const [isSwapping, setIsSwapping] = useState<boolean>(false);

  useEffect(() => {
    if (initialOrigin) {
      setOrigin(initialOrigin);
    }
  }, [initialOrigin]);

  useEffect(() => {
    if (initialDestination) {
      setDestination(initialDestination);
    }
  }, [initialDestination]);

  useEffect(() => {
    if (initialDate) {
      setDate(initialDate);
    }
  }, [initialDate]);

  useEffect(() => {
    if (initialMaxTransfers !== undefined) {
      setMaxTransfers(initialMaxTransfers);
    }
  }, [initialMaxTransfers]);

  // Clear validation error when inputs change
  useEffect(() => {
    if (validationError && origin && destination && origin.code !== destination.code) {
      setValidationError(null);
    }
  }, [origin, destination, validationError]);

  // Quick date helpers
  const setQuickDate = (daysFromToday: number) => {
    const d = new Date();
    d.setDate(d.getDate() + daysFromToday);
    setDate(d.toISOString().split('T')[0]);
  };

  const setNextWeekend = () => {
    const d = new Date();
    const currentDay = d.getDay(); // 0 is Sunday, 6 is Saturday
    const daysUntilSaturday = (6 - currentDay + 7) % 7 || 7;
    d.setDate(d.getDate() + daysUntilSaturday);
    setDate(d.toISOString().split('T')[0]);
  };

  const handleSwap = () => {
    setIsSwapping(true);
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
    setTimeout(() => setIsSwapping(false), 300);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!origin) {
      setValidationError('Please select a boarding station.');
      return;
    }
    if (!destination) {
      setValidationError('Please select an arrival station.');
      return;
    }
    if (origin.code.toUpperCase() === destination.code.toUpperCase()) {
      setValidationError('Origin and destination stations cannot be identical.');
      return;
    }
    if (!date) {
      setValidationError('Please select a journey date.');
      return;
    }

    onSearch({
      origin,
      destination,
      date,
      maxTransfers,
    });
  };

  const handleNearbySelect = (station: Station, role: 'origin' | 'destination') => {
    if (role === 'origin') {
      setOrigin(station);
    } else {
      setDestination(station);
    }
  };

  const formattedDateLabel = (() => {
    try {
      const parts = date.split('-');
      if (parts.length === 3) {
        const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
        return d.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' });
      }
      return '';
    } catch {
      return '';
    }
  })();

  return (
    <>
      <div className="bg-white rounded-2xl p-5 sm:p-7 border border-cream-300 shadow-md">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Top Station Row with Swap Trigger */}
          <div className="relative flex flex-col md:flex-row items-stretch md:items-center gap-3">
            <StationAutocomplete
              id="input-origin-station"
              label="Boarding From"
              placeholder="e.g. Mumbai Central (BCT)"
              value={origin}
              onChange={setOrigin}
              icon="train"
            />

            {/* Swap Button */}
            <div className="flex justify-center md:pt-5 -my-1 md:my-0">
              <button
                type="button"
                id="btn-swap-stations"
                data-testid="swap-stations-btn"
                onClick={handleSwap}
                aria-label="Swap origin and destination"
                className={`w-10 h-10 rounded-full bg-cream-50 hover:bg-cream-100 text-espresso-700 border border-cream-300 flex items-center justify-center transition-all shadow-sm hover:scale-105 active:scale-95 ${
                  isSwapping ? 'rotate-180 duration-300' : ''
                }`}
                title="Swap stations"
              >
                <ArrowLeftRight className="w-4 h-4 text-terracotta" />
              </button>
            </div>

            <StationAutocomplete
              id="input-destination-station"
              label="Arriving At"
              placeholder="e.g. New Delhi (NDLS)"
              value={destination}
              onChange={setDestination}
              icon="pin"
            />
          </div>

          {/* Validation Alert */}
          {validationError && (
            <div
              id="search-validation-error"
              className="p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2.5 text-xs text-red-700 animate-in fade-in duration-150"
            >
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span className="font-medium">{validationError}</span>
            </div>
          )}

          {/* Date & Options Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
            {/* Date Input */}
            <div className="sm:col-span-2">
              <label
                htmlFor="input-journey-date"
                className="block text-[11px] font-bold uppercase tracking-wider text-espresso-600 mb-1 flex items-center justify-between"
              >
                <span>Journey Date</span>
                <span className="text-[10px] text-espresso-500 font-normal">
                  {formattedDateLabel}
                </span>
              </label>
              <div className="relative flex items-center bg-white rounded-xl border border-cream-300 px-3.5 py-2.5 focus-within:border-terracotta focus-within:ring-2 focus-within:ring-terracotta/15 transition-all min-h-[46px]">
                <Calendar className="w-4 h-4 text-espresso-600 mr-2.5 flex-shrink-0" />
                <input
                  id="input-journey-date"
                  type="date"
                  value={date}
                  min={new Date().toISOString().split('T')[0]}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full bg-transparent font-sans text-sm font-semibold text-espresso-900 focus:outline-none"
                />
              </div>

              {/* Quick Date Pills */}
              <div className="flex items-center gap-1.5 mt-2 flex-wrap text-xs">
                <button
                  type="button"
                  id="btn-quick-today"
                  onClick={() => setQuickDate(0)}
                  className="px-2.5 py-1 rounded-md bg-cream-100 hover:bg-cream-200 text-espresso-800 text-[11px] font-medium transition-colors"
                >
                  Today
                </button>
                <button
                  type="button"
                  id="btn-quick-tomorrow"
                  onClick={() => setQuickDate(1)}
                  className="px-2.5 py-1 rounded-md bg-cream-100 hover:bg-cream-200 text-espresso-800 text-[11px] font-medium transition-colors"
                >
                  Tomorrow
                </button>
                <button
                  type="button"
                  id="btn-quick-weekend"
                  onClick={setNextWeekend}
                  className="px-2.5 py-1 rounded-md bg-cream-100 hover:bg-cream-200 text-espresso-800 text-[11px] font-medium transition-colors"
                >
                  Weekend
                </button>
              </div>
            </div>

            {/* Max Transfers Selector */}
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-espresso-600 mb-1">
                Connections
              </label>
              <div className="flex rounded-xl border border-cream-300 bg-cream-50 p-1 min-h-[46px] items-center">
                <button
                  type="button"
                  id="btn-transfers-0"
                  onClick={() => setMaxTransfers(0)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    maxTransfers === 0
                      ? 'bg-white text-espresso-900 shadow-sm font-bold'
                      : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                  title="Direct trains only"
                >
                  Direct
                </button>
                <button
                  type="button"
                  id="btn-transfers-1"
                  onClick={() => setMaxTransfers(1)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    maxTransfers === 1
                      ? 'bg-white text-espresso-900 shadow-sm font-bold'
                      : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                  title="Direct or 1 transfer"
                >
                  1 Transfer
                </button>
                <button
                  type="button"
                  id="btn-transfers-2"
                  onClick={() => setMaxTransfers(2)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    maxTransfers === 2
                      ? 'bg-white text-espresso-900 shadow-sm font-bold'
                      : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                  title="Up to 2 transfers"
                >
                  2 Transfers
                </button>
              </div>
              <p className="text-[10px] text-espresso-500 mt-1">
                {maxTransfers === 0
                  ? 'Only trains with zero transfers'
                  : maxTransfers === 1
                  ? 'Searches direct & 1-transfer routes'
                  : 'Explores multi-transfer routes across India'}
              </p>
            </div>

            {/* Submit Action Button */}
            <div className="flex flex-col justify-end">
              <button
                type="submit"
                id="btn-search-routes"
                disabled={isLoading}
                className="w-full h-[46px] rounded-xl bg-terracotta hover:bg-terracotta/90 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-sm transition-all hover:shadow active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Searching Routes...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    <span>Search Routes</span>
                  </>
                )}
              </button>

              {/* Nearby Stations Trigger */}
              <div className="mt-2 text-center">
                <button
                  type="button"
                  id="btn-explore-nearby-stations"
                  onClick={() => setIsNearbyModalOpen(true)}
                  className="text-[11px] font-semibold text-espresso-600 hover:text-terracotta inline-flex items-center gap-1 transition-colors"
                >
                  <Sparkles className="w-3 h-3 text-terracotta" />
                  <span>Discover Nearby Stations</span>
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>

      {/* Nearby Stations Modal */}
      <NearbyStationsModal
        isOpen={isNearbyModalOpen}
        onClose={() => setIsNearbyModalOpen(false)}
        onSelectStation={handleNearbySelect}
      />
    </>
  );
}
