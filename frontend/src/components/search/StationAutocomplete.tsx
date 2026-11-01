'use client';

import React, { useState, useEffect, useRef } from 'react';
import { MapPin, Search, X, Loader2, Train } from 'lucide-react';
import { Station } from '../../types/api';
import { searchStations } from '../../services/api';

const POPULAR_HUBS: Station[] = [
  { code: 'NDLS', name: 'New Delhi', city: 'Delhi', state: 'Delhi', latitude: 28.6423, longitude: 77.2185 },
  { code: 'BCT', name: 'Mumbai Central', city: 'Mumbai', state: 'Maharashtra', latitude: 18.9696, longitude: 72.8193 },
  { code: 'HWH', name: 'Howrah Junction', city: 'Kolkata', state: 'West Bengal', latitude: 22.5839, longitude: 88.3426 },
  { code: 'BPL', name: 'Bhopal Junction', city: 'Bhopal', state: 'Madhya Pradesh', latitude: 23.2678, longitude: 77.4124 },
  { code: 'GWL', name: 'Gwalior Junction', city: 'Gwalior', state: 'Madhya Pradesh', latitude: 26.2183, longitude: 78.1828 },
];

interface StationAutocompleteProps {
  label: string;
  placeholder?: string;
  value: Station | null;
  onChange: (station: Station | null) => void;
  icon?: 'train' | 'pin';
  className?: string;
  id?: string;
}

export function StationAutocomplete({
  label,
  placeholder = 'Search station name or code...',
  value,
  onChange,
  icon = 'train',
  className = '',
  id,
}: StationAutocompleteProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<Station[]>([]);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Synchronize internal query when external value changes
  useEffect(() => {
    if (value) {
      setQuery(`${value.name} (${value.code})`);
    } else {
      setQuery('');
    }
  }, [value]);

  // Handle outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Debounced search
  useEffect(() => {
    if (!isOpen) return;

    const trimmed = query.trim();

    // If input matches the current value representation, show popular hubs on focus
    if (value && trimmed === `${value.name} (${value.code})`) {
      setResults(POPULAR_HUBS);
      return;
    }

    if (trimmed.length === 0) {
      setResults(POPULAR_HUBS);
      return;
    }

    setIsLoading(true);
    const timer = setTimeout(async () => {
      try {
        const stations = await searchStations(trimmed, 8);
        setResults(stations);
      } catch (err) {
        console.error('Station search error:', err);
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, isOpen, value]);

  const handleSelect = (station: Station) => {
    onChange(station);
    setQuery(`${station.name} (${station.code})`);
    setIsOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(null);
    setQuery('');
    setResults(POPULAR_HUBS);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setIsOpen(true);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === 'Enter' && highlightedIndex >= 0 && results[highlightedIndex]) {
      e.preventDefault();
      handleSelect(results[highlightedIndex]);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div ref={wrapperRef} className={`relative flex-1 ${className}`}>
      <div className="flex items-center justify-between mb-1">
        <label
          htmlFor={id}
          className="block text-[11px] font-bold uppercase tracking-wider text-espresso-600"
        >
          {label}
        </label>
        {value && (
          <span className="text-[10px] text-espresso-500 font-medium">
            {[value.city, value.state].filter(Boolean).join(', ')}
          </span>
        )}
      </div>

      <div
        onClick={() => {
          setIsOpen(true);
          inputRef.current?.focus();
        }}
        className={`relative flex items-center bg-white rounded-xl border transition-all duration-150 px-3.5 py-2.5 min-h-[46px] cursor-text ${
          isOpen
            ? 'border-terracotta ring-2 ring-terracotta/15 shadow-sm'
            : 'border-cream-300 hover:border-espresso-500'
        }`}
      >
        <div className="w-8 h-8 rounded-lg bg-cream-50 text-terracotta flex items-center justify-center flex-shrink-0 mr-2.5">
          {icon === 'train' ? (
            <Train className="w-4 h-4 text-terracotta" />
          ) : (
            <MapPin className="w-4 h-4 text-olive" />
          )}
        </div>

        <div className="flex-1 min-w-0 pr-12">
          <input
            id={id}
            ref={inputRef}
            type="text"
            value={query}
            placeholder={placeholder}
            onFocus={() => setIsOpen(true)}
            onChange={(e) => {
              setQuery(e.target.value);
              setIsOpen(true);
            }}
            onKeyDown={handleKeyDown}
            className="w-full bg-transparent font-sans text-sm font-semibold text-espresso-900 placeholder:text-espresso-500 placeholder:font-normal focus:outline-none truncate"
          />
        </div>

        {/* Code Chip or Clear Button */}
        <div className="absolute right-3 flex items-center gap-1.5">
          {isLoading && <Loader2 className="w-4 h-4 text-espresso-500 animate-spin" />}

          {value && !isLoading ? (
            <>
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-cream-100 text-espresso-800 border border-cream-300">
                {value.code}
              </span>
              <button
                type="button"
                onClick={handleClear}
                aria-label={`Clear ${label} selection`}
                className="p-1 text-espresso-500 hover:text-espresso-900 rounded-full hover:bg-cream-100 transition-colors"
                title="Clear station"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </>
          ) : null}
        </div>
      </div>

      {/* Dropdown Options */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-white rounded-xl border border-cream-300 shadow-xl max-h-72 overflow-y-auto py-1 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-espresso-500 border-b border-cream-200">
            {query.trim().length === 0 ? 'Major Railway Hubs' : 'Matching Stations'}
          </div>

          {results.length === 0 && !isLoading ? (
            <div className="px-4 py-4 text-center text-xs text-espresso-500">
              No railway stations found for &ldquo;{query}&rdquo;
            </div>
          ) : (
            results.map((station, index) => {
              const isSelected = value?.code === station.code;
              const isHighlighted = highlightedIndex === index;

              return (
                <button
                  key={station.code}
                  type="button"
                  data-station-code={station.code}
                  onMouseEnter={() => setHighlightedIndex(index)}
                  onClick={() => handleSelect(station)}
                  className={`w-full px-3.5 py-2.5 min-h-[44px] text-left flex items-center justify-between gap-3 transition-colors ${
                    isHighlighted || isSelected
                      ? 'bg-cream-100 text-espresso-900'
                      : 'hover:bg-cream-50 text-espresso-800'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Train className="w-3.5 h-3.5 text-espresso-500 flex-shrink-0" />
                    <div className="truncate">
                      <div className="font-semibold text-sm text-espresso-900 truncate">
                        {station.name}
                      </div>
                      <div className="text-[11px] text-espresso-600 truncate">
                        {[station.city, station.state].filter(Boolean).join(', ')}
                      </div>
                    </div>
                  </div>

                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-cream-50 text-terracotta border border-cream-300 flex-shrink-0">
                    {station.code}
                  </span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
