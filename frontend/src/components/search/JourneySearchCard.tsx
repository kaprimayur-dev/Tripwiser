'use client';

import React, { useState } from 'react';
import { ArrowLeftRight, Calendar, Search, Navigation, Filter, Sparkles, Loader2 } from 'lucide-react';
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
      setValidationError('Please select a destination station.');
      return;
    }
    if (origin.code === destination.code) {
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

  return (
    <>
      <div className="bg-white rounded-2xl p-5 sm:p-7 border border-cream-300 shadow-md">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Top Station Row with Swap Trigger */}
          <div className="relative flex flex-col md:flex-row items-stretch md:items-center gap-3">
            <StationAutocomplete
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
              label="Arriving At"
              placeholder="e.g. New Delhi (NDLS)"
              value={destination}
              onChange={setDestination}
              icon="pin"
            />
          </div>

          {/* Date & Options Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
            {/* Date Input */}
            <div className="sm:col-span-2">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-espresso-600 mb-1 flex items-center justify-between">
                <span>Journey Date</span>
                <span className="text-[10px] text-espresso-500 font-normal">
                  {new Date(date).toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' })}
                </span>
              </label>
              <div className="relative flex items-center bg-white rounded-xl border border-cream-300 px-3.5 py-2.5 focus-within:border-terracotta focus-within:ring-2 focus-within:ring-terracotta/15 transition-all">
                <Calendar className="w-4 h-4 text-espresso-600 mr-2.5 flex-shrink-0" />
                <input
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
                  onClick={() => setQuickDate(0)}
                  className="px-2.5 py-1 rounded-md bg-cream-100 hover:bg-cream-200 text-espresso-800 text-[11px] font-medium transition-colors"
                >
                  Today
                </button>
                <button
                  type="button"
                  onClick={() => setQuickDate(1)}
                  className="px-2.5 py-1 rounded-md bg-cream-100 hover:bg-cream-200 text-espresso-800 text-[11px] font-medium transition-colors"
                >
                  Tomorrow
                </button>
                <button
                  type="button"
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
              <div className="flex rounded-xl border border-cream-300 bg-cream-50 p-1">
                <button
                  type="button"
                  onClick={() => setMaxTransfers(0)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    maxTransfers === 0
                      ? 'bg-white text-espresso-900 shadow-sm border border-cream-300'
                      : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  Direct Only
                </button>
                <button
                  type="button"
                  onClick={() => setMaxTransfers(1)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    maxTransfers === 1
                      ? 'bg-white text-espresso-900 shadow-sm border border-cream-300'
                      : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  1 Transfer
                </button>
              </div>
              <p className="text-[10px] text-espresso-500 mt-1">
                {maxTransfers === 1 ? 'Finds guaranteed layover hubs' : 'Only direct trains'}
              </p>
            </div>

            {/* Nearby Stations Trigger */}
            <div className="flex flex-col justify-between">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-espresso-600 mb-1">
                Spatial Radius
              </label>
              <button
                type="button"
                onClick={() => setIsNearbyModalOpen(true)}
                className="w-full py-2.5 px-3 rounded-xl border border-cream-300 bg-cream-50 hover:bg-cream-100 text-espresso-800 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <Navigation className="w-3.5 h-3.5 text-olive" />
                <span>Nearby Stations</span>
              </button>
              <p className="text-[10px] text-espresso-500 mt-1">
                Use GPS or city proximity
              </p>
            </div>
          </div>

          {/* Validation Error Alert */}
          {validationError && (
            <div className="p-3 bg-terracotta/10 border border-terracotta/20 rounded-xl text-xs text-terracotta font-medium flex items-center gap-2">
              <span>{validationError}</span>
            </div>
          )}

          {/* Action Trigger */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3.5 px-6 rounded-xl bg-terracotta hover:bg-terracotta-hover text-white font-display text-sm font-bold tracking-wide shadow-sm hover:shadow transition-all flex items-center justify-center gap-2 disabled:opacity-60 active:scale-[0.99]"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>Searching Real Railway Timetables...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Find Railway Routes</span>
              </>
            )}
          </button>
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

