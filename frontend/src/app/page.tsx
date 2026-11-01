'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from '../components/layout/Navbar';
import { Footer } from '../components/layout/Footer';
import { JourneySearchCard } from '../components/search/JourneySearchCard';
import { ResultsStream } from '../components/results/ResultsStream';
import { DataIntegrityBanner } from '../components/common/DataIntegrityBanner';
import { SortMode } from '../components/results/SortingFilterBar';
import { Station, RouteSearchResponse } from '../types/api';
import { searchRoutes, getStationByCode } from '../services/api';

export default function Home() {
  const [origin, setOrigin] = useState<Station | null>(null);
  const [destination, setDestination] = useState<Station | null>(null);
  const [date, setDate] = useState<string>('');
  const [maxTransfers, setMaxTransfers] = useState<number>(1);
  const [sortMode, setSortMode] = useState<SortMode>('recommended');

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [searchResponse, setSearchResponse] = useState<RouteSearchResponse | null>(null);

  // Default tomorrow date on mount
  useEffect(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    setDate(d.toISOString().split('T')[0]);
  }, []);

  // Execute route search
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

        // Update URL query parameters cleanly
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

  // Handle search submission from JourneySearchCard
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

  // Helper to quickly load a test corridor
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

        executeSearch({
          originCode: origStation.code,
          destCode: destStation.code,
          journeyDate: queryDate,
          transfers: 1,
          sortBy: 'recommended',
        });
      }
    } catch (err) {
      console.error('Failed to set corridor:', err);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-cream-100 text-espresso-900">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-8">
        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-olive/15 text-olive">
            <span>Travel Intelligence Dispatch</span>
          </div>

          <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight text-espresso-900 leading-tight">
            The direct route isn&rsquo;t the only route.
          </h1>

          <p className="text-sm sm:text-base text-espresso-600 leading-relaxed">
            When direct trains are waitlisted, TripWiser discovers practical connecting journeys, guaranteed transfer windows, and nearby station alternatives across Indian Railways.
          </p>
        </div>

        {/* Search Console */}
        <JourneySearchCard
          initialOrigin={origin}
          initialDestination={destination}
          initialDate={date}
          initialMaxTransfers={maxTransfers}
          isLoading={isLoading}
          onSearch={handleSearchSubmit}
        />

        {/* Data Integrity Banner */}
        <DataIntegrityBanner
          timetableStatus={searchResponse?.timetable_status}
          fareStatus={searchResponse?.fare_status}
          availabilityStatus={searchResponse?.availability_status}
        />

        {/* Results Stream */}
        <ResultsStream
          data={searchResponse}
          isLoading={isLoading}
          error={error}
          currentSort={sortMode}
          onSortChange={handleSortChange}
          onSelectCorridor={handleSelectCorridor}
        />
      </main>

      <Footer />
    </div>
  );
}
