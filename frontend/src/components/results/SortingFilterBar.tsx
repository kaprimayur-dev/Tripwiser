'use client';

import React from 'react';
import { Sparkles, Zap, ArrowDownUp, AlertCircle, IndianRupee } from 'lucide-react';

export type SortMode = 'recommended' | 'fastest' | 'fewest_transfers' | 'cheapest';

interface SortingFilterBarProps {
  currentSort: SortMode;
  onSortChange: (mode: SortMode) => void;
  sortingNote?: string | null;
  totalRoutes: number;
}

export function SortingFilterBar({
  currentSort,
  onSortChange,
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
    <div className="space-y-2.5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 text-xs">
          {tabs.map((tab) => {
            const isActive = currentSort === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onSortChange(tab.id)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full font-semibold transition-all whitespace-nowrap ${
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

        <div className="text-xs text-espresso-600 font-medium">
          {totalRoutes} {totalRoutes === 1 ? 'Route' : 'Routes'} available
        </div>
      </div>

      {/* Notice if Cheapest is selected or note returned from backend */}
      {(currentSort === 'cheapest' || sortingNote) && (
        <div className="p-3 bg-cream-50 rounded-xl border border-cream-300 flex items-start gap-2.5 text-xs text-espresso-700 animate-fade-in">
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

