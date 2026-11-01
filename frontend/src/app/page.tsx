'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Navbar, AppMode } from '../components/layout/Navbar';
import { Footer } from '../components/layout/Footer';
import { JourneySearchCard } from '../components/search/JourneySearchCard';
import { ResultsStream } from '../components/results/ResultsStream';
import { DataIntegrityBanner } from '../components/common/DataIntegrityBanner';
import { BachelorSearchCard } from '../components/bachelor/BachelorSearchCard';
import { BachelorSpecialStream } from '../components/bachelor/BachelorSpecialStream';
import { TrainSearchCard } from '../components/trains/TrainSearchCard';
import { TrainScheduleView } from '../components/trains/TrainScheduleView';
import { StationSearchCard } from '../components/stations/StationSearchCard';
import { StationDetailView } from '../components/stations/StationDetailView';
import { SortMode } from '../components/results/SortingFilterBar';
import { Station, RouteSearchResponse, BachelorSpecialSearchResponse } from '../types/api';
import { searchRoutes, searchBachelorSpecial, getStationByCode } from '../services/api';
import { Sparkles, Navigation, Layers, Compass } from 'lucide-react';

export default function Home() {
  const [activeMode, setActiveMode] = useState<AppMode>('connecting');

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

  // Timetable Inspector State
  const [selectedTrain, setSelectedTrain] = useState<string | null>(null);

  // Station Discovery State
  const [selectedStationCode, setSelectedStationCode] = useState<string | null>(null);

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
          url.searchParams.set('mode', 'connecting');
          url.searchParams.set('origin', params.originCode);
          url.searchParams.set('destination', params.destCode);
          url.searchParams.set('date', params.journeyDate);
          url.searchParams.set('transfers', String(params.transfers));
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

  // Default tomorrow date and URL params on mount
  useEffect(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    setDate(d.toISOString().split('T')[0]);

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const modeParam = params.get('mode');
      if (
        modeParam === 'timetable' ||
        modeParam === 'bachelor' ||
        modeParam === 'connecting' ||
        modeParam === 'stations'
      ) {
        setActiveMode(modeParam as AppMode);
      }
      const trainParam = params.get('train');
      if (trainParam) {
        setSelectedTrain(trainParam.trim());
      }
      const stationParam = params.get('station');
      if (stationParam) {
        setSelectedStationCode(stationParam.trim().toUpperCase());
      }
      const transfersParam = params.get('transfers');
      if (transfersParam && ['0', '1', '2'].includes(transfersParam)) {
        setMaxTransfers(Number(transfersParam));
      }

      const origParam = params.get('origin');
      const destParam = params.get('destination');
      if (origParam && destParam && (!modeParam || modeParam === 'connecting')) {
        Promise.all([getStationByCode(origParam), getStationByCode(destParam)]).then(([o, d]) => {
          if (o && d) {
            setOrigin(o);
            setDestination(d);
            const queryDate = params.get('date') || new Date(Date.now() + 86400000).toISOString().split('T')[0];
            const numTransfers = transfersParam ? Number(transfersParam) : 1;
            executeSearch({
              originCode: o.code,
              destCode: d.code,
              journeyDate: queryDate,
              transfers: numTransfers,
              sortBy: 'recommended',
            });
          }
        });
      }
    }
  }, [executeSearch]);

  const handleModeChange = (mode: AppMode) => {
    setActiveMode(mode);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('mode', mode);
      window.history.replaceState({}, '', url.toString());
    }
  };

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

        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);
          url.searchParams.set('mode', 'bachelor');
          url.searchParams.set('origin', params.originCode);
          url.searchParams.set('destination', params.destCode);
          url.searchParams.set('date', params.journeyDate);
          if (params.preferredClass) {
            url.searchParams.set('class', params.preferredClass);
          }
          window.history.replaceState({}, '', url.toString());
        }
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
        } else if (activeMode === 'bachelor') {
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

  // Train selection helper
  const handleSelectTrain = (trainNumber: string) => {
    setSelectedTrain(trainNumber);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('mode', 'timetable');
      url.searchParams.set('train', trainNumber);
      window.history.replaceState({}, '', url.toString());
    }
  };

  const handleClearTrain = () => {
    setSelectedTrain(null);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('train');
      window.history.replaceState({}, '', url.toString());
    }
  };

  // Station selection helper
  const handleSelectStation = (stationCode: string) => {
    setSelectedStationCode(stationCode);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('mode', 'stations');
      url.searchParams.set('station', stationCode);
      window.history.replaceState({}, '', url.toString());
    }
  };

  const handleClearStation = () => {
    setSelectedStationCode(null);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('station');
      window.history.replaceState({}, '', url.toString());
    }
  };

  // Use station as route alternative
  const handleStationAsOrigin = (st: Station) => {
    setOrigin(st);
    handleModeChange('connecting');
    if (destination && date) {
      executeSearch({
        originCode: st.code,
        destCode: destination.code,
        journeyDate: date,
        transfers: maxTransfers,
        sortBy: sortMode,
      });
    }
  };

  const handleStationAsDestination = (st: Station) => {
    setDestination(st);
    handleModeChange('connecting');
    if (origin && date) {
      executeSearch({
        originCode: origin.code,
        destCode: st.code,
        journeyDate: date,
        transfers: maxTransfers,
        sortBy: sortMode,
      });
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-cream-100 text-espresso-900">
      <Navbar currentMode={activeMode} onSelectMode={handleModeChange} />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-8">
        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-olive/15 text-olive">
            <span>Travel Intelligence Dispatch</span>
          </div>

          <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight text-espresso-900 leading-tight">
            {activeMode === 'connecting'
              ? 'The direct route isn’t the only route.'
              : activeMode === 'bachelor'
              ? 'One train. Continuous berths. Zero waitlist.'
              : activeMode === 'timetable'
              ? 'Inspect every halt, offset & running day.'
              : 'Every station, coordinates & spatial radius.'}
          </h1>

          <p className="text-sm sm:text-base text-espresso-600 leading-relaxed">
            {activeMode === 'connecting'
              ? 'When direct trains are waitlisted, TripWiser discovers practical connecting journeys, guaranteed transfer windows, and nearby station alternatives across Indian Railways.'
              : activeMode === 'bachelor'
              ? 'TripWiser Bachelor Special finds and assembles vacant berth segments across intermediate stations on the same train, giving you a continuous journey without changing trains.'
              : activeMode === 'timetable'
              ? 'Search any compiled train to view its complete stoppage sequence, arrival/departure timings, halt durations, operating days, and verified timetable provenance.'
              : 'Explore 8,697 Indian railway stations, discover nearby alternate boarding terminals with PostGIS geodetic distance, and inspect verified timetable schedule coverage.'}
          </p>
        </div>

        {/* Feature Mode Selector Tabs */}
        <div className="flex justify-center">
          <div className="inline-flex p-1 rounded-2xl bg-cream-200/80 border border-cream-300 shadow-inner flex-wrap justify-center gap-1">
            <button
              type="button"
              id="tab-connecting-mode"
              onClick={() => handleModeChange('connecting')}
              className={`inline-flex items-center gap-2 px-4 sm:px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
                activeMode === 'connecting'
                  ? 'bg-white text-espresso-900 shadow-sm'
                  : 'text-espresso-600 hover:text-espresso-900'
              }`}
            >
              <Navigation className="w-4 h-4 text-espresso-700" />
              <span>Connecting Routes</span>
            </button>

            <button
              type="button"
              id="tab-timetable-mode"
              onClick={() => handleModeChange('timetable')}
              className={`inline-flex items-center gap-2 px-4 sm:px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
                activeMode === 'timetable'
                  ? 'bg-white text-espresso-900 shadow-sm'
                  : 'text-espresso-600 hover:text-espresso-900'
              }`}
            >
              <Layers className="w-4 h-4 text-espresso-700" />
              <span>Train Timetable</span>
            </button>

            <button
              type="button"
              id="tab-stations-mode"
              onClick={() => handleModeChange('stations')}
              className={`inline-flex items-center gap-2 px-4 sm:px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
                activeMode === 'stations'
                  ? 'bg-white text-espresso-900 shadow-sm'
                  : 'text-espresso-600 hover:text-espresso-900'
              }`}
            >
              <Compass className="w-4 h-4 text-espresso-700" />
              <span>Station Discovery</span>
            </button>

            <button
              type="button"
              id="tab-bachelor-mode"
              onClick={() => handleModeChange('bachelor')}
              className={`inline-flex items-center gap-2 px-4 sm:px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
                activeMode === 'bachelor'
                  ? 'bg-terracotta text-white shadow-sm'
                  : 'text-terracotta hover:bg-terracotta/10'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>Bachelor Special</span>
            </button>
          </div>
        </div>

        {/* Dynamic Search Console according to active mode */}
        {activeMode === 'connecting' && (
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
        )}

        {activeMode === 'bachelor' && (
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
              onSwitchToConnecting={() => handleModeChange('connecting')}
              onSelectSampleCorridor={handleSelectCorridor}
            />
          </>
        )}

        {activeMode === 'timetable' && (
          <div className="space-y-6">
            <TrainSearchCard
              onSelectTrain={handleSelectTrain}
              initialTrainNumber={selectedTrain || undefined}
            />

            {selectedTrain ? (
              <TrainScheduleView
                trainNumber={selectedTrain}
                onClose={handleClearTrain}
              />
            ) : (
              <div className="p-8 text-center rounded-2xl bg-white border border-cream-300 shadow-sm text-espresso-600">
                <Layers className="w-10 h-10 text-espresso-300 mx-auto mb-3" />
                <h3 className="font-display text-lg font-bold text-espresso-900 mb-1">
                  Search a Train Schedule
                </h3>
                <p className="text-xs sm:text-sm text-espresso-600 max-w-md mx-auto">
                  Type a train number (e.g. 12002 Bhopal Shatabdi, 12951 Mumbai Rajdhani, 12621 Tamil Nadu Express) or train name above to inspect its verified stoppage timeline.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {[
                    { number: '12002', name: 'Bhopal Shatabdi' },
                    { number: '12951', name: 'Mumbai Rajdhani' },
                    { number: '12301', name: 'Howrah Rajdhani' },
                    { number: '12621', name: 'Tamil Nadu Express' },
                  ].map((preset) => (
                    <button
                      key={preset.number}
                      type="button"
                      onClick={() => handleSelectTrain(preset.number)}
                      className="px-3 py-1.5 rounded-lg bg-cream-200/80 hover:bg-cream-300 text-xs font-medium text-espresso-800 border border-cream-300 transition-colors"
                    >
                      {preset.number} · {preset.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeMode === 'stations' && (
          <div className="space-y-6">
            <StationSearchCard
              onSelectStation={handleSelectStation}
              initialStationCode={selectedStationCode || undefined}
            />

            {selectedStationCode ? (
              <StationDetailView
                stationCode={selectedStationCode}
                onClose={handleClearStation}
                onSelectAsOrigin={handleStationAsOrigin}
                onSelectAsDestination={handleStationAsDestination}
                onInspectStation={handleSelectStation}
              />
            ) : (
              <div className="p-8 text-center rounded-2xl bg-white border border-cream-300 shadow-sm text-espresso-600">
                <Compass className="w-10 h-10 text-espresso-300 mx-auto mb-3" />
                <h3 className="font-display text-lg font-bold text-espresso-900 mb-1">
                  Discover Any Railway Station
                </h3>
                <p className="text-xs sm:text-sm text-espresso-600 max-w-md mx-auto">
                  Search any station code or city name above to inspect its exact coordinates, verified compiled train schedule coverage, and nearby stations within 15–75 km.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {[
                    { code: 'NDLS', name: 'New Delhi' },
                    { code: 'BCT', name: 'Mumbai Central' },
                    { code: 'HWH', name: 'Howrah' },
                    { code: 'MAS', name: 'Chennai Central' },
                    { code: 'BPL', name: 'Bhopal Jn' },
                    { code: 'GWL', name: 'Gwalior Jn' },
                  ].map((preset) => (
                    <button
                      key={preset.code}
                      type="button"
                      onClick={() => handleSelectStation(preset.code)}
                      className="px-3 py-1.5 rounded-lg bg-cream-200/80 hover:bg-cream-300 text-xs font-medium text-espresso-800 border border-cream-300 transition-colors"
                    >
                      <span className="font-mono font-bold">{preset.code}</span> · {preset.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
