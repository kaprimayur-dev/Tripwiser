'use client';

import React from 'react';
import { Sparkles, AlertCircle, Clock, ShieldCheck, HelpCircle, ArrowRight } from 'lucide-react';
import { BachelorSpecialSearchResponse } from '../../types/api';
import { BachelorSpecialCard } from './BachelorSpecialCard';

interface BachelorSpecialStreamProps {
  data: BachelorSpecialSearchResponse | null;
  isLoading: boolean;
  error: Error | null;
  onSwitchToConnecting?: () => void;
  onSelectSampleCorridor?: (orig: string, dest: string) => void;
}

export function BachelorSpecialStream({
  data,
  isLoading,
  error,
  onSwitchToConnecting,
  onSelectSampleCorridor,
}: BachelorSpecialStreamProps) {
  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-10 bg-cream-200 rounded-xl w-64" />
        <div className="h-56 bg-cream-200 rounded-2xl" />
        <div className="h-56 bg-cream-200 rounded-2xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center space-y-3">
        <AlertCircle className="w-8 h-8 text-red-600 mx-auto" />
        <h3 className="font-display text-lg font-bold text-red-900">
          Search Unavailable
        </h3>
        <p className="text-sm text-red-700 max-w-md mx-auto">
          {error.message || 'An error occurred while querying the berth vacancy service. Please verify your search criteria and retry.'}
        </p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  // 1. Case: No direct trains operate on this corridor on requested date
  if (data.status === 'NO_DIRECT_TRAINS') {
    return (
      <div className="bg-cream-50 border border-cream-300 rounded-2xl p-6 sm:p-8 text-center space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-cream-200 text-espresso-700 flex items-center justify-center mx-auto">
          <Clock className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="font-display text-xl font-bold text-espresso-900">
            No Direct Trains On This Date
          </h3>
          <p className="text-sm text-espresso-600 max-w-lg mx-auto">
            Bachelor Special requires a direct train run to assemble continuous berth segments on the same train. No direct service operates between <span className="font-mono font-semibold">{data.origin_code}</span> and <span className="font-mono font-semibold">{data.destination_code}</span> on this date.
          </p>
        </div>

        {onSwitchToConnecting && (
          <button
            type="button"
            onClick={onSwitchToConnecting}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-xs font-semibold shadow-sm transition-colors"
          >
            <span>Search 1-Transfer Connecting Routes Instead</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  }

  // 2. Case: Direct train runs exist, but no vacancies recorded in chart_vacancies
  if (data.status === 'NO_CHART_VACANCIES' || data.total_itineraries === 0) {
    return (
      <div className="bg-cream-50 border border-cream-300 rounded-2xl p-6 sm:p-8 space-y-5">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-2xl bg-terracotta/10 text-terracotta flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-6 h-6" />
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-display text-xl font-bold text-espresso-900">
                No Vacant Berth Segments Observed
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-olive/15 text-olive">
                Zero-Fabrication Assurance
              </span>
            </div>

            <p className="text-sm text-espresso-700 leading-relaxed max-w-2xl">
              Direct trains operate along the <strong className="font-mono">{data.origin_code} ➔ {data.destination_code}</strong> corridor, but no vacant berth records were observed for <strong className="font-mono">{data.travel_date}</strong>.
            </p>
          </div>
        </div>

        {/* Indian Railways Charting Notice */}
        <div className="bg-white rounded-xl p-4 border border-cream-300 space-y-2 text-xs text-espresso-700">
          <div className="font-bold flex items-center gap-1.5 text-espresso-900">
            <HelpCircle className="w-4 h-4 text-terracotta" />
            <span>Why are vacancy segments not available yet?</span>
          </div>
          <p className="leading-relaxed text-espresso-600">
            {data.chart_policy_notice}
          </p>
          <div className="pt-2 border-t border-cream-200 text-[11px] text-espresso-500 font-semibold">
            TripWiser strictly uses genuine railway chart records and will never manufacture synthetic berth numbers.
          </div>
        </div>

        {onSwitchToConnecting && (
          <div className="pt-2 flex items-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={onSwitchToConnecting}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-xs font-semibold transition-colors"
            >
              <span>Explore Connecting Routes with Seat Vacancy</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    );
  }

  // 3. Case: Valid itineraries discovered
  return (
    <div className="space-y-5 animate-fade-in">
      {/* Results Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap pb-2 border-b border-cream-300">
        <div>
          <h2 className="font-display text-xl font-bold text-espresso-900 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-terracotta" />
            <span>Bachelor Special Discovered Itineraries</span>
          </h2>
          <p className="text-xs text-espresso-600 mt-0.5">
            {data.total_itineraries} continuous same-train option{data.total_itineraries > 1 ? 's' : ''} covering{' '}
            <span className="font-mono font-semibold">{data.origin_code} ➔ {data.destination_code}</span> on{' '}
            <span className="font-mono font-semibold">{data.travel_date}</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-olive bg-olive/10 px-2.5 py-1 rounded-full border border-olive/20">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Verified Chart Records</span>
          </span>
        </div>
      </div>

      {/* Itinerary Cards */}
      <div className="space-y-4">
        {data.itineraries.map((itinerary, idx) => (
          <BachelorSpecialCard
            key={`${itinerary.train_number}-${idx}`}
            itinerary={itinerary}
            index={idx}
          />
        ))}
      </div>
    </div>
  );
}

