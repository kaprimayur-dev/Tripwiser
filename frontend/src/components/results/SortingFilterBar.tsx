'use client';

import React from 'react';
import { Sparkles, Zap, ArrowDownUp, AlertCircle, IndianRupee, Filter } from 'lucide-react';

export type SortMode = 'recommended' | 'fastest' | 'fewest_transfers' | 'cheapest';
export type TransferFilterMode = 'all' | 'direct' | '1-transfer' | '2-transfers';

interface SortingFilterBarProps {
  currentSort: SortMode;
  onSortChange: (mode: SortMode) => void;
  transferFilter?: TransferFilterMode;
  onTransferFilterChange?: (filter: TransferFilterMode) => void;
  directCount?: number;
  transfer1Count?: number;
  transfer2Count?: number;
  sortingNote?: string | null;
  totalRoutes: number;
}

export function SortingFilterBar({
  currentSort,
  onSortChange,
  transferFilter = 'all',
  onTransferFilterChange,
  directCount,
  transfer1Count,
  transfer2Count,
  sortingNote,
  totalRoutes,
}: SortingFilterBarProps) {
  const tabs: { id: SortMode; label: string; icon: React.ReactNode; isDeferred?: boolean }[] = [
    {
      id: 'recommended',
      label: 'Recommended',
      icon: <Sparkles className="w-3.5 h-3.5" />,
    },
    {
      id: 'fastest',
      label: 'Fastest',
      icon: <Zap className="w-3.5 h-3.5" />,
    },
    {
      id: 'fewest_transfers',
      label: 'Fewest Transfers',
      icon: <ArrowDownUp className="w-3.5 h-3.5" />,
    },
    {
      id: 'cheapest',
      label: 'Cheapest',
      icon: <IndianRupee className="w-3.5 h-3.5" />,
      isDeferred: true,
    },
  ];

  return (
    <div className="space-y-3">
      {/* Top Bar: Sort Mode Tabs & Total Count */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 text-xs no-scrollbar">
          {tabs.map((tab) => {
            const isActive = currentSort === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                id={`sort-tab-${tab.id}`}
                onClick={() => onSortChange(tab.id)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full font-semibold transition-all whitespace-nowrap min-h-[36px] ${
                  isActive
                    ? 'bg-espresso-900 text-cream-100 shadow-sm'
                    : 'bg-white text-espresso-700 hover:bg-cream-200 border border-cream-300'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
                {tab.isDeferred && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-cream-200 text-espresso-700 font-bold uppercase">
                    Deferred
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="text-xs text-espresso-600 font-medium self-end sm:self-auto">
          {totalRoutes} {totalRoutes === 1 ? 'Route' : 'Routes'} available
        </div>
      </div>

      {/* Filter Row: Transfer Count Filter Pills */}
      {onTransferFilterChange && (
        <div className="flex items-center gap-2 flex-wrap text-xs pt-1 border-t border-cream-200/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-espresso-500 flex items-center gap-1">
            <Filter className="w-3 h-3 text-terracotta" />
            <span>Show:</span>
          </span>

          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              type="button"
              id="filter-all-transfers"
              onClick={() => onTransferFilterChange('all')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                transferFilter === 'all'
                  ? 'bg-espresso-900 text-white shadow-2xs'
                  : 'bg-white text-espresso-700 border border-cream-300 hover:bg-cream-100'
              }`}
            >
              All Routes ({totalRoutes})
            </button>

            {directCount !== undefined && directCount > 0 && (
              <button
                type="button"
                id="filter-direct-only"
                onClick={() => onTransferFilterChange('direct')}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  transferFilter === 'direct'
                    ? 'bg-olive text-white shadow-2xs'
                    : 'bg-white text-olive border border-olive/30 hover:bg-olive/10'
                }`}
              >
                Direct Only ({directCount})
              </button>
            )}

            {transfer1Count !== undefined && transfer1Count > 0 && (
              <button
                type="button"
                id="filter-1-transfer"
                onClick={() => onTransferFilterChange('1-transfer')}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  transferFilter === '1-transfer'
                    ? 'bg-terracotta text-white shadow-2xs'
                    : 'bg-white text-terracotta border border-terracotta/30 hover:bg-terracotta/10'
                }`}
              >
                1 Transfer ({transfer1Count})
              </button>
            )}

            {transfer2Count !== undefined && transfer2Count > 0 && (
              <button
                type="button"
                id="filter-2-transfers"
                onClick={() => onTransferFilterChange('2-transfers')}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                  transferFilter === '2-transfers'
                    ? 'bg-espresso-800 text-white shadow-2xs'
                    : 'bg-white text-espresso-800 border border-cream-300 hover:bg-cream-100'
                }`}
              >
                2 Transfers ({transfer2Count})
              </button>
            )}
          </div>
        </div>
      )}

      {/* Notice if Cheapest is selected or note returned from backend */}
      {(currentSort === 'cheapest' || sortingNote) && (
        <div className="p-3 bg-cream-50 rounded-xl border border-cream-300 flex items-start gap-2.5 text-xs text-espresso-700 animate-in fade-in duration-150">
          <AlertCircle className="w-4 h-4 text-terracotta flex-shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-semibold text-espresso-900">Fare Feed Deferred</span>
            <p className="text-espresso-600 leading-relaxed">
              {sortingNote ||
                'Cheapest sorting is deferred because no verified commercial fare feed is available. Showing recommended route ordering instead.'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
