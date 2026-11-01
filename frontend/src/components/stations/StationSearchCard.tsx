'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Search, MapPin, Loader2, ArrowRight, X, Compass, ShieldCheck } from 'lucide-react';
import { Station } from '../../types/api';
import { searchStations } from '../../services/api';

interface StationSearchCardProps {
  onSelectStation: (stationCode: string) => void;
  selectedStationCode?: string | null;
  initialStationCode?: string | null;
}

const PRESET_STATIONS = [
  { code: 'NDLS', name: 'New Delhi' },
  { code: 'BCT', name: 'Mumbai Central' },
  { code: 'HWH', name: 'Howrah' },
  { code: 'MAS', name: 'Chennai Central' },
  { code: 'BPL', name: 'Bhopal Jn' },
  { code: 'GWL', name: 'Gwalior Jn' },
];

export function StationSearchCard({
  onSelectStation,
  selectedStationCode,
  initialStationCode,
}: StationSearchCardProps) {
  const [query, setQuery] = useState(initialStationCode || selectedStationCode || '');
  const [suggestions, setSuggestions] = useState<Station[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const val = selectedStationCode || initialStationCode;
    if (val) {
      setQuery(val);
    }
  }, [selectedStationCode, initialStationCode]);

  useEffect(() => {
    const clean = query.trim();
    if (clean.length < 1) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    let isMounted = true;
    setLoading(true);

    const timer = setTimeout(() => {
      searchStations(clean, 8)
        .then((res) => {
          if (isMounted) {
            setSuggestions(res);
            setIsOpen(res.length > 0);
            setLoading(false);
          }
        })
        .catch(() => {
          if (isMounted) {
            setSuggestions([]);
            setLoading(false);
          }
        });
    }, 250);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [query]);

  // Handle outside click to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (station: Station) => {
    setQuery(`${station.name} (${station.code})`);
    setIsOpen(false);
    onSelectStation(station.code);
  };

  const handleClear = () => {
    setQuery('');
    setSuggestions([]);
    setIsOpen(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = query.trim();
    if (clean) {
      if (suggestions.length > 0) {
        handleSelect(suggestions[0]);
      } else {
        onSelectStation(clean.toUpperCase());
        setIsOpen(false);
      }
    }
  };

  return (
    <div id="station-search-card" className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Compass className="w-5 h-5 text-terracotta" />
          <h2 className="font-display text-xl sm:text-2xl font-bold text-espresso-900">
            Station Intelligence & Spatial Discovery
          </h2>
        </div>
        <p className="text-xs sm:text-sm text-espresso-600">
          Search any railway station across India by name or code to inspect exact coordinates, verified timetable coverage, and nearby stations within your chosen spatial radius.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="relative" ref={containerRef}>
        <div className="flex items-center gap-2 bg-cream-50 rounded-xl border border-cream-300 px-3.5 py-2.5 focus-within:ring-2 focus-within:ring-terracotta/40 focus-within:border-terracotta transition-all">
          <Search className="w-5 h-5 text-espresso-500 flex-shrink-0" />
          <input
            id="station-search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.trim().length >= 1 && suggestions.length > 0 && setIsOpen(true)}
            placeholder="Search Station Code (e.g. NDLS, BPL, GWL) or Name (e.g. New Delhi, Bhopal, Gwalior)..."
            className="w-full bg-transparent text-sm font-medium text-espresso-900 placeholder:text-espresso-400 focus:outline-none"
            autoComplete="off"
          />

          {loading && <Loader2 className="w-4 h-4 animate-spin text-terracotta flex-shrink-0" />}

          {query && !loading && (
            <button
              type="button"
              onClick={handleClear}
              className="p-1 rounded-full text-espresso-400 hover:text-espresso-700 hover:bg-cream-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}

          <button
            type="submit"
            className="px-4 py-1.5 rounded-lg bg-espresso-900 hover:bg-espresso-800 text-cream-100 text-xs font-semibold flex items-center gap-1 transition-colors flex-shrink-0"
          >
            <span>Inspect</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Autocomplete Dropdown */}
        {isOpen && suggestions.length > 0 && (
          <div
            role="listbox"
            className="absolute z-50 left-0 right-0 top-full mt-1.5 bg-white rounded-xl border border-cream-300 shadow-xl max-h-72 overflow-y-auto divide-y divide-cream-200 animate-fade-in"
          >
            {suggestions.map((station, idx) => (
              <button
                key={station.code}
                id={`station-suggestion-${idx}`}
                type="button"
                onClick={() => handleSelect(station)}
                className="w-full text-left px-4 py-2.5 hover:bg-cream-100 flex items-center justify-between group transition-colors"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold bg-cream-200 text-espresso-900 px-1.5 py-0.5 rounded">
                      {station.code}
                    </span>
                    <span className="text-sm font-semibold text-espresso-900 group-hover:text-terracotta transition-colors">
                      {station.name}
                    </span>
                  </div>
                  <div className="text-[11px] text-espresso-500">
                    {[station.city, station.state, station.zone ? `Zone: ${station.zone}` : null]
                      .filter(Boolean)
                      .join(' • ')}
                  </div>
                </div>

                <div className="text-[11px] font-mono text-espresso-400 group-hover:text-espresso-700">
                  {station.latitude.toFixed(2)}°, {station.longitude.toFixed(2)}°
                </div>
              </button>
            ))}
          </div>
        )}
      </form>

      {/* Preset Station Pills */}
      <div className="flex items-center gap-2 flex-wrap pt-1 text-xs">
        <span className="text-espresso-500 font-medium">Quick hubs:</span>
        {PRESET_STATIONS.map((preset) => (
          <button
            key={preset.code}
            type="button"
            onClick={() => {
              setQuery(`${preset.name} (${preset.code})`);
              onSelectStation(preset.code);
            }}
            className="px-2.5 py-1 rounded-lg bg-cream-200/80 hover:bg-cream-300 text-espresso-800 text-xs font-semibold border border-cream-300 transition-colors"
          >
            <span className="font-mono font-bold">{preset.code}</span> · {preset.name}
          </button>
        ))}
      </div>
    </div>
  );
}
