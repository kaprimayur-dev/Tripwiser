'use client';

import React, { useState } from 'react';
import { ArrowLeftRight, Calendar, Search, Sparkles, Loader2, Armchair } from 'lucide-react';
import { Station } from '../../types/api';
import { StationAutocomplete } from '../search/StationAutocomplete';

interface BachelorSearchCardProps {
  initialOrigin?: Station | null;
  initialDestination?: Station | null;
  initialDate?: string;
  initialTravelClass?: string;
  isLoading?: boolean;
  onSearch: (params: {
    origin: Station;
    destination: Station;
    date: string;
    travelClass?: string;
  }) => void;
}

export function BachelorSearchCard({
  initialOrigin = null,
  initialDestination = null,
  initialDate,
  initialTravelClass = '3A',
  isLoading = false,
  onSearch,
}: BachelorSearchCardProps) {
  const getTomorrowString = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  };

  const [origin, setOrigin] = useState<Station | null>(initialOrigin);
  const [destination, setDestination] = useState<Station | null>(initialDestination);
  const [date, setDate] = useState<string>(initialDate || getTomorrowString());
  const [travelClass, setTravelClass] = useState<string>(initialTravelClass);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSwapping, setIsSwapping] = useState<boolean>(false);

  const handleSwapStations = () => {
    setIsSwapping(true);
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
    setTimeout(() => setIsSwapping(false), 250);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!origin) {
      setValidationError('Please select a boarding station.');
      return;
    }
    if (!destination) {
      setValidationError('Please select an alighting destination station.');
      return;
    }
    if (origin.code.toUpperCase() === destination.code.toUpperCase()) {
      setValidationError('Boarding and destination stations cannot be the same.');
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
      travelClass: travelClass || undefined,
    });
  };

  return (
    <div
      id="bachelor-search-card"
      className="bg-white rounded-3xl border border-terracotta/25 shadow-lg p-5 sm:p-7 space-y-6 relative overflow-hidden"
    >
      {/* Decorative Signature Banner */}
      <div className="flex items-center justify-between pb-3 border-b border-cream-200 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-terracotta animate-pulse" />
          <span className="font-display font-bold text-sm text-espresso-900">
            TripWiser Signature: Same-Train Continuous Berth Discovery
          </span>
        </div>
        <span className="text-[11px] font-semibold text-terracotta bg-terracotta/10 px-2.5 py-0.5 rounded-full border border-terracotta/20">
          No Interchange Required
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Origin & Destination with Swap */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative">
          <div>
            <StationAutocomplete
              label="Boarding Station"
              placeholder="e.g. GWL (Gwalior) or BCT"
              value={origin}
              onChange={(st) => {
                setOrigin(st);
                setValidationError(null);
              }}
            />
          </div>

          <div>
            <StationAutocomplete
              label="Destination Station"
              placeholder="e.g. BPL (Bhopal) or NDLS"
              value={destination}
              onChange={(st) => {
                setDestination(st);
                setValidationError(null);
              }}
            />
          </div>

          {/* Station Swap Floating Button */}
          <div className="hidden md:flex absolute left-1/2 top-9 -translate-x-1/2 z-10">
            <button
              type="button"
              onClick={handleSwapStations}
              title="Swap Stations"
              className={`w-9 h-9 rounded-full bg-cream-100 hover:bg-terracotta hover:text-white border border-cream-300 text-espresso-700 shadow-md flex items-center justify-center transition-all ${
                isSwapping ? 'rotate-180 duration-200' : ''
              }`}
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Date and Travel Class */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Journey Date */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-espresso-600 mb-1.5">
              Journey Date
            </label>
            <div className="relative">
              <input
                type="date"
                value={date}
                min={new Date().toISOString().split('T')[0]}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-4 py-2.5 bg-cream-50 rounded-xl border border-cream-300 text-espresso-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-terracotta/40 focus:border-terracotta pl-10"
              />
              <Calendar className="w-4 h-4 text-espresso-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>

          {/* Travel Class Selector */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-espresso-600 mb-1.5">
              Preferred Travel Class
            </label>
            <div className="relative">
              <select
                value={travelClass}
                onChange={(e) => setTravelClass(e.target.value)}
                className="w-full px-4 py-2.5 bg-cream-50 rounded-xl border border-cream-300 text-espresso-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-terracotta/40 focus:border-terracotta pl-10 appearance-none cursor-pointer"
              >
                <option value="3A">AC 3 Tier (3A)</option>
                <option value="2A">AC 2 Tier (2A)</option>
                <option value="1A">AC First Class (1A)</option>
                <option value="SL">Sleeper (SL)</option>
                <option value="CC">AC Chair Car (CC)</option>
              </select>
              <Armchair className="w-4 h-4 text-espresso-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Validation Error Message */}
        {validationError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
            {validationError}
          </div>
        )}

        {/* Submit Button */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3.5 px-6 rounded-2xl bg-terracotta hover:bg-terracotta/90 text-white font-semibold text-sm sm:text-base flex items-center justify-center gap-2 shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed group cursor-pointer"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Discovering Continuous Berths...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5 text-cream-100 group-hover:rotate-12 transition-transform" />
                <span>Find Bachelor Special Berths</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
