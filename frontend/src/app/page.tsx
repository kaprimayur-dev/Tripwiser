'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from '../components/layout/Navbar';
import { Footer } from '../components/layout/Footer';
import { JourneySearchCard } from '../components/search/JourneySearchCard';
import { ResultsStream } from '../components/results/ResultsStream';
import { DataIntegrityBanner } from '../components/common/DataIntegrityBanner';
import { BachelorSearchCard } from '../components/bachelor/BachelorSearchCard';
import { BachelorSpecialStream } from '../components/bachelor/BachelorSpecialStream';
import { SortMode } from '../components/results/SortingFilterBar';
import { Station, RouteSearchResponse, BachelorSpecialSearchResponse } from '../types/api';
import { searchRoutes, searchBachelorSpecial, getStationByCode } from '../services/api';
import { Sparkles, Navigation } from 'lucide-react';

export default function Home() {
  const [activeMode, setActiveMode] = useState<'connecting' | 'bachelor'>('connecting');

  // Shared Form State
  const [origin, setOrigin] = useState<Station | null>(null);
  const [destination, setDestination] = useState<Station | null>(null);
  const [date, setDate] = useState<string>('');

  // Connecting Routes State
  const [maxTransfers, setMaxTransfers] = useState<number>(1);
  const [sortMode, setSortMode] = useState<SortMode>('recommended');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [searchResponse, setSearchResponse] = useState<RouteSearchResponse | null>(null);

  // Bachelor Special State
  const [travelClass, setTravelClass] = useState<string>('3A');
  const [bachelorLoading, setBachelorLoading] = useState<boolean>(false);
  const [bachelorError, setBachelorError] = useState<Error | null>(null);
  const [bachelorResponse, setBachelorResponse] = useState<BachelorSpecialSearchResponse | null>(null);

  // Default tomorrow date on mount
  useEffect(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    setDate(d.toISOString().split('T')[0]);
  }, []);

  // Execute connecting route search
  const executeSearch = useCallback(
    async (params: {
      originCode: string;
      destCode: string;
      journeyDate: string;
      transfers: number;
      sortBy: SortMode;
    }) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await searchRoutes({
          origin: params.originCode,
          destination: params.destCode,
          date: params.journeyDate,
          maxTransfers: params.transfers,
          sortBy: params.sortBy,
        });
        setSearchResponse(response);

        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);
          url.searchParams.set('origin', params.originCode);
          url.searchParams.set('destination', params.destCode);
          url.searchParams.set('date', params.journeyDate);
          url.searchParams.set('sort', params.sortBy);
          window.history.replaceState({}, '', url.toString());
        }
      } catch (err: any) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setSearchResponse(null);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Execute Bachelor Special search
  const executeBachelorSearch = useCallback(
    async (params: {
      originCode: string;
      destCode: string;
      journeyDate: string;
      preferredClass?: string;
    }) => {
      setBachelorLoading(true);
      setBachelorError(null);

      try {
        const response = await searchBachelorSpecial({
          origin: params.originCode,
          destination: params.destCode,
          date: params.journeyDate,
          travelClass: params.preferredClass,
        });
        setBachelorResponse(response);
      } catch (err: any) {
        setBachelorError(err instanceof Error ? err : new Error(String(err)));
        setBachelorResponse(null);
      } finally {
        setBachelorLoading(false);
      }
    },
    []
  );

  // Handle connecting search submission
  const handleSearchSubmit = (params: {
    origin: Station;
    destination: Station;
    date: string;
    maxTransfers: number;
  }) => {
    setOrigin(params.origin);
    setDestination(params.destination);
    setDate(params.date);
    setMaxTransfers(params.maxTransfers);

    executeSearch({
      originCode: params.origin.code,
      destCode: params.destination.code,
      journeyDate: params.date,
      transfers: params.maxTransfers,
      sortBy: sortMode,
    });
  };

  // Handle Bachelor Special search submission
  const handleBachelorSubmit = (params: {
    origin: Station;
    destination: Station;
    date: string;
    travelClass?: string;
  }) => {
    setOrigin(params.origin);
    setDestination(params.destination);
    setDate(params.date);
    if (params.travelClass) setTravelClass(params.travelClass);

    executeBachelorSearch({
      originCode: params.origin.code,
      destCode: params.destination.code,
      journeyDate: params.date,
      preferredClass: params.travelClass,
    });
  };

  // Handle changing sort mode
  const handleSortChange = (newSort: SortMode) => {
    setSortMode(newSort);
    if (origin && destination && date) {
      executeSearch({
        originCode: origin.code,
        destCode: destination.code,
        journeyDate: date,
        transfers: maxTransfers,
        sortBy: newSort,
      });
    }
  };

  // Corridor helper
  const handleSelectCorridor = async (origCode: string, destCode: string) => {
    try {
      const [origStation, destStation] = await Promise.all([
        getStationByCode(origCode),
        getStationByCode(destCode),
      ]);

      if (origStation && destStation) {
        setOrigin(origStation);
        setDestination(destStation);
        const queryDate = date || new Date().toISOString().split('T')[0];

        if (activeMode === 'connecting') {
          executeSearch({
            originCode: origStation.code,
            destCode: destStation.code,
            journeyDate: queryDate,
            transfers: 1,
            sortBy: 'recommended',
          });
        } else {
          executeBachelorSearch({
            originCode: origStation.code,
            destCode: destStation.code,
            journeyDate: queryDate,
            preferredClass: travelClass,
          });
        }
      }
    } catch (err) {
      console.error('Failed to set corridor:', err);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-cream-100 text-espresso-900">
      <Navbar currentMode={activeMode} onSelectMode={setActiveMode} />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-8">
        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-olive/15 text-olive">
            <span>Travel Intelligence Dispatch</span>
          </div>

          <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight text-espresso-900 leading-tight">
            {activeMode === 'connecting'
              ? 'The direct route isn’t the only route.'
              : 'One train. Continuous berths. Zero waitlist.'}
          </h1>

          <p className="text-sm sm:text-base text-espresso-600 leading-relaxed">
            {activeMode === 'connecting'
              ? 'When direct trains are waitlisted, TripWiser discovers practical connecting journeys, guaranteed transfer windows, and nearby station alternatives across Indian Railways.'
              : 'TripWiser Bachelor Special finds and assembles vacant berth segments across intermediate stations on the same train, giving you a continuous journey without changing trains.'}
          </p>
        </div>

        {/* Feature Mode Selector Tabs */}
        <div className="flex justify-center">
          <div className="inline-flex p-1 rounded-2xl bg-cream-200/80 border border-cream-300 shadow-inner">
            <button
              type="button"
              id="tab-connecting-mode"
              onClick={() => setActiveMode('connecting')}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
                activeMode === 'connecting'
                  ? 'bg-white text-espresso-900 shadow-sm'
                  : 'text-espresso-600 hover:text-espresso-900'
              }`}
            >
              <Navigation className="w-4 h-4 text-espresso-700" />
              <span>Connecting Route Discovery</span>
            </button>

            <button
              type="button"
              id="tab-bachelor-mode"
              onClick={() => setActiveMode('bachelor')}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
                activeMode === 'bachelor'
                  ? 'bg-terracotta text-white shadow-sm'
                  : 'text-terracotta hover:bg-terracotta/10'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>Bachelor Special (Berth Segments)</span>
            </button>
          </div>
        </div>

        {/* Dynamic Search Console according to active mode */}
        {activeMode === 'connecting' ? (
          <>
            <JourneySearchCard
              initialOrigin={origin}
              initialDestination={destination}
              initialDate={date}
              initialMaxTransfers={maxTransfers}
              isLoading={isLoading}
              onSearch={handleSearchSubmit}
            />

            <DataIntegrityBanner
              timetableStatus={searchResponse?.timetable_status}
              fareStatus={searchResponse?.fare_status}
              availabilityStatus={searchResponse?.availability_status}
            />

            <ResultsStream
              data={searchResponse}
              isLoading={isLoading}
              error={error}
              currentSort={sortMode}
              onSortChange={handleSortChange}
              onSelectCorridor={handleSelectCorridor}
            />
          </>
        ) : (
          <>
            <BachelorSearchCard
              initialOrigin={origin}
              initialDestination={destination}
              initialDate={date}
              initialTravelClass={travelClass}
              isLoading={bachelorLoading}
              onSearch={handleBachelorSubmit}
            />

            <BachelorSpecialStream
              data={bachelorResponse}
              isLoading={bachelorLoading}
              error={bachelorError}
              onSwitchToConnecting={() => setActiveMode('connecting')}
              onSelectSampleCorridor={handleSelectCorridor}
            />
          </>
        )}
      </main>

      <Footer />
    </div>
  );
}
