'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Search, Train, Loader2, ArrowRight, X, Calendar, ShieldCheck } from 'lucide-react';
import { TrainSummary } from '../../types/api';
import { searchTrains } from '../../services/api';

interface TrainSearchCardProps {
  onSelectTrain: (trainNumber: string) => void;
  selectedTrainNumber?: string | null;
  initialTrainNumber?: string | null;
}

export function TrainSearchCard({
  onSelectTrain,
  selectedTrainNumber,
  initialTrainNumber,
}: TrainSearchCardProps) {
  const [query, setQuery] = useState(initialTrainNumber || selectedTrainNumber || '');
  const [suggestions, setSuggestions] = useState<TrainSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const val = selectedTrainNumber || initialTrainNumber;
    if (val) {
      setQuery(val);
    }
  }, [selectedTrainNumber, initialTrainNumber]);

  useEffect(() => {
    const clean = query.trim();
    if (clean.length < 2) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    let isMounted = true;
    setLoading(true);

    const timer = setTimeout(() => {
      searchTrains(clean, 12)
        .then((res) => {
          if (isMounted) {
            setSuggestions(res);
            setIsOpen(true);
            setLoading(false);
          }
        })
        .catch(() => {
          if (isMounted) {
            setSuggestions([]);
            setIsOpen(true);
            setLoading(false);
          }
        });
    }, 200);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [query]);

  // Handle clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (t: TrainSummary) => {
    setQuery(t.number);
    setIsOpen(false);
    onSelectTrain(t.number);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = query.trim().toUpperCase();
    if (clean) {
      setIsOpen(false);
      onSelectTrain(clean);
    }
  };

  const handleClear = () => {
    setQuery('');
    setSuggestions([]);
    setIsOpen(false);
  };

  return (
    <div className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-espresso-900 text-cream-100 shadow-sm">
              <Train className="w-3.5 h-3.5 text-terracotta" />
              <span>OFFICIAL TIMETABLE LOOKUP</span>
            </span>
            <span className="text-[11px] font-semibold text-olive inline-flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>TAG 2024–2026 Verified</span>
            </span>
          </div>
          <h2 className="font-display text-xl sm:text-2xl font-bold text-espresso-900">
            Train Timetable &amp; Stoppage Inspector
          </h2>
          <p className="text-xs text-espresso-600 mt-0.5">
            Search any Indian Railways train number, service name, or station (code or city) to inspect complete station halts, timings, and running days.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="relative" ref={containerRef}>
        <div className="flex items-center gap-2 bg-cream-50 rounded-xl border border-cream-300 px-3.5 py-2.5 focus-within:ring-2 focus-within:ring-terracotta/40 focus-within:border-terracotta transition-all">
          <Search className="w-5 h-5 text-espresso-500 flex-shrink-0" />
          <input
            id="train-search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.trim().length >= 2 && setIsOpen(true)}
            placeholder="Search by Train Number (e.g. 12002), Name (e.g. Shatabdi), or Station (e.g. Bhopal, BPL)..."
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
            id="btn-search-train"
            type="submit"
            className="px-4 py-1.5 rounded-lg bg-terracotta text-white text-xs font-bold hover:bg-terracotta/90 transition-colors shadow-sm flex-shrink-0"
          >
            Inspect Timetable
          </button>
        </div>

        {/* Suggestions Dropdown */}
        {isOpen && query.trim().length >= 2 && (
          <div className="absolute left-0 right-0 top-full mt-1.5 bg-white rounded-xl border border-cream-300 shadow-xl overflow-hidden z-30 max-h-72 overflow-y-auto divide-y divide-cream-100 animate-fade-in">
            {suggestions.length > 0 ? (
              suggestions.map((t) => (
                <button
                  key={t.number}
                  type="button"
                  onClick={() => handleSelect(t)}
                  className="w-full px-4 py-2.5 text-left hover:bg-cream-50 transition-colors flex items-center justify-between gap-3 text-xs"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-terracotta bg-terracotta/10 px-1.5 py-0.5 rounded text-[11px]">
                        #{t.number}
                      </span>
                      <span className="font-semibold text-espresso-900 truncate">
                        {t.name}
                      </span>
                    </div>
                    <div className="text-[11px] text-espresso-600 mt-0.5 flex items-center gap-1.5 truncate">
                      <span>{t.origin_name} ({t.origin_code})</span>
                      <ArrowRight className="w-3 h-3 text-espresso-400 flex-shrink-0" />
                      <span>{t.destination_name} ({t.destination_code})</span>
                    </div>
                  </div>

                  <div className="text-right flex-shrink-0">
                    <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-cream-200 text-espresso-800">
                      {t.frequency_description}
                    </span>
                    <div className="text-[10px] text-espresso-500 mt-0.5">
                      {t.total_stops} stops • {Math.round(t.distance_km)} km
                    </div>
                  </div>
                </button>
              ))
            ) : !loading ? (
              <div className="p-4 text-center text-xs text-espresso-600" id="train-search-empty-state">
                <p className="font-semibold text-espresso-800">No matching trains found</p>
                <p className="text-[11px] text-espresso-500 mt-0.5">
                  Try searching by train number (e.g. 12002, 12951), service name (e.g. Shatabdi), or station (e.g. Bhopal, NDLS).
                </p>
              </div>
            ) : null}
          </div>
        )}
      </form>
    </div>
  );
}
