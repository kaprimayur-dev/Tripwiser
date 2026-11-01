'use client';

import React, { useState, useEffect } from 'react';
import { Train, Sparkles, Navigation, Layers, Compass, Bookmark } from 'lucide-react';
import { getSavedTrips, subscribeSavedTrips } from '../../lib/savedTrips';

export type AppMode = 'connecting' | 'timetable' | 'stations' | 'bachelor' | 'saved';

interface NavbarProps {
  currentMode?: AppMode;
  onSelectMode?: (mode: AppMode) => void;
}

export function Navbar({ currentMode = 'connecting', onSelectMode }: NavbarProps) {
  const [savedCount, setSavedCount] = useState<number>(0);

  useEffect(() => {
    setSavedCount(getSavedTrips().length);
    const unsubscribe = subscribeSavedTrips(() => {
      setSavedCount(getSavedTrips().length);
    });
    return unsubscribe;
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full bg-cream-100/95 backdrop-blur-md border-b border-cream-300 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Logo & Brand */}
        <div
          className="flex items-center gap-3 cursor-pointer"
          onClick={() => onSelectMode && onSelectMode('connecting')}
        >
          <div className="w-10 h-10 rounded-xl bg-espresso-900 text-cream-100 flex items-center justify-center shadow-sm">
            <Train className="w-5 h-5 text-terracotta" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-display text-xl font-bold tracking-tight text-espresso-900">
                TripWiser
              </span>
              <span className="hidden sm:inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-olive/15 text-olive">
                Intelligence
              </span>
            </div>
            <p className="text-[11px] text-espresso-600 hidden sm:block">
              Indian Railway Route Discovery Engine
            </p>
          </div>
        </div>

        {/* Mode Selector in Header */}
        <div className="flex items-center gap-1 bg-cream-200/70 p-1 rounded-xl border border-cream-300 overflow-x-auto no-scrollbar">
          <button
            type="button"
            id="nav-connecting-tab"
            onClick={() => onSelectMode && onSelectMode('connecting')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap min-h-[36px] ${
              currentMode === 'connecting'
                ? 'bg-white text-espresso-900 shadow-sm font-bold'
                : 'text-espresso-600 hover:text-espresso-900'
            }`}
          >
            <Navigation className="w-3.5 h-3.5 text-terracotta" />
            <span className="hidden sm:inline">Connecting</span>
            <span>Routes</span>
          </button>

          <button
            type="button"
            id="nav-timetable-tab"
            onClick={() => onSelectMode && onSelectMode('timetable')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap min-h-[36px] ${
              currentMode === 'timetable'
                ? 'bg-white text-espresso-900 shadow-sm font-bold'
                : 'text-espresso-600 hover:text-espresso-900'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Timetable</span>
          </button>

          <button
            type="button"
            id="nav-stations-tab"
            onClick={() => onSelectMode && onSelectMode('stations')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap min-h-[36px] ${
              currentMode === 'stations'
                ? 'bg-white text-espresso-900 shadow-sm font-bold'
                : 'text-espresso-600 hover:text-espresso-900'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            <span>Stations</span>
          </button>

          <button
            type="button"
            id="nav-bachelor-tab"
            onClick={() => onSelectMode && onSelectMode('bachelor')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap min-h-[36px] ${
              currentMode === 'bachelor'
                ? 'bg-terracotta text-white shadow-sm font-bold'
                : 'text-terracotta hover:bg-terracotta/10'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Bachelor</span>
            <span>Special</span>
          </button>

          {/* My Trips Tab with Badge */}
          <button
            type="button"
            id="nav-saved-trips-tab"
            onClick={() => onSelectMode && onSelectMode('saved')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap min-h-[36px] ${
              currentMode === 'saved'
                ? 'bg-espresso-900 text-cream-100 shadow-sm font-bold'
                : 'text-espresso-700 hover:text-espresso-900'
            }`}
          >
            <Bookmark className={`w-3.5 h-3.5 ${currentMode === 'saved' ? 'fill-terracotta text-terracotta' : ''}`} />
            <span>My Trips</span>
            {savedCount > 0 && (
              <span
                id="saved-trips-count-badge"
                className={`ml-0.5 px-1.5 py-0.2 text-[10px] rounded-full font-bold ${
                  currentMode === 'saved'
                    ? 'bg-terracotta text-white'
                    : 'bg-terracotta/15 text-terracotta'
                }`}
              >
                {savedCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
