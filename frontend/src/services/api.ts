/**
 * TripWiser API Client Service
 * Uses relative URL path to leverage Next.js proxy rewrites in next.config.js.
 */

import { Station, NearbyStationItem, RouteSearchResponse, BachelorSpecialSearchResponse } from '../types/api';

const API_BASE = '/api/v1';

export async function searchStations(query: string, limit = 8): Promise<Station[]> {
  const clean = query.trim();
  if (!clean) return [];

  const res = await fetch(`${API_BASE}/stations/search?q=${encodeURIComponent(clean)}&limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to search stations: ${res.statusText}`);
  }
  return res.json();
}

export async function getNearbyStations(
  latitude: number,
  longitude: number,
  radiusKm = 30
): Promise<NearbyStationItem[]> {
  const res = await fetch(
    `${API_BASE}/stations/nearby?latitude=${latitude}&longitude=${longitude}&radius_km=${radiusKm}`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch nearby stations: ${res.statusText}`);
  }
  return res.json();
}

export async function getStationByCode(code: string): Promise<Station | null> {
  const res = await fetch(`${API_BASE}/stations/${encodeURIComponent(code.trim().toUpperCase())}`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to get station: ${res.statusText}`);
  }
  return res.json();
}

export interface RouteSearchParams {
  origin: string;
  destination: string;
  date: string;
  maxTransfers?: number;
  sortBy?: 'recommended' | 'fastest' | 'fewest_transfers' | 'cheapest';
}

export async function searchRoutes(params: RouteSearchParams): Promise<RouteSearchResponse> {
  const searchParams = new URLSearchParams({
    origin: params.origin.trim().toUpperCase(),
    destination: params.destination.trim().toUpperCase(),
    date: params.date,
    max_transfers: String(params.maxTransfers ?? 1),
    sort_by: params.sortBy ?? 'recommended',
  });

  const res = await fetch(`${API_BASE}/routes/search?${searchParams.toString()}`);
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `Route search failed with status ${res.status}`);
  }
  return res.json();
}

export interface BachelorSearchParams {
  origin: string;
  destination: string;
  date: string;
  travelClass?: string;
}

export async function searchBachelorSpecial(params: BachelorSearchParams): Promise<BachelorSpecialSearchResponse> {
  const searchParams = new URLSearchParams({
    origin: params.origin.trim().toUpperCase(),
    destination: params.destination.trim().toUpperCase(),
    date: params.date,
  });
  if (params.travelClass) {
    searchParams.set('travel_class', params.travelClass.trim().toUpperCase());
  }

  const res = await fetch(`${API_BASE}/bachelor/search?${searchParams.toString()}`);
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `Bachelor Special search failed with status ${res.status}`);
  }
  return res.json();
}


