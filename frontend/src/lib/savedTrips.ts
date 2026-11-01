/**
 * Local storage manager for Saved Trips (My Trips).
 * Provides lightweight client-side persistence with duplicate prevention,
 * removal, and custom event broadcasting for reactive UI updates.
 */

export interface SavedTrip {
  id: string; // Deterministic unique signature: e.g. `${originCode}-${destCode}-${routeId}`
  savedAt: string; // ISO timestamp
  originCode: string;
  originName: string;
  destinationCode: string;
  destinationName: string;
  journeyDate: string; // Original search date (YYYY-MM-DD)
  maxTransfers: number;
  totalDurationMinutes: number;
  totalTravelTimeMinutes: number;
  totalWaitTimeMinutes: number;
  transferCount: number;
  isDirect: boolean;
  trainSummary: string; // e.g. "Mumbai Central-New Delhi Rajdhani Express ➔ Howrah Duronto Express"
  trainNumbers: string[];
  departureTime: string;
  arrivalTime: string;
  overallTransferRisk?: string | null;
  routeId: string;
}

const STORAGE_KEY = 'TRIPWISER_SAVED_TRIPS';
const EVENT_NAME = 'tripwiser:saved-trips-updated';

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

/**
 * Retrieve all saved trips from localStorage.
 */
export function getSavedTrips(): SavedTrip[] {
  if (!isBrowser()) return [];

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed;
    }
    return [];
  } catch (err) {
    console.error('Error reading saved trips from localStorage:', err);
    return [];
  }
}

/**
 * Check if a specific trip is already saved.
 */
export function isTripSaved(id: string): boolean {
  if (!isBrowser()) return false;
  const trips = getSavedTrips();
  return trips.some((t) => t.id === id);
}

/**
 * Save a trip to localStorage.
 * Prevents duplicates. Returns true if newly added, false if already present.
 */
export function saveTrip(trip: SavedTrip): boolean {
  if (!isBrowser()) return false;

  try {
    const trips = getSavedTrips();
    const existingIndex = trips.findIndex((t) => t.id === trip.id);
    if (existingIndex >= 0) {
      return false; // Already saved
    }

    const updated = [trip, ...trips];
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { count: updated.length } }));
    return true;
  } catch (err) {
    console.error('Error saving trip to localStorage:', err);
    return false;
  }
}

/**
 * Remove a trip from localStorage by its unique id.
 */
export function removeSavedTrip(id: string): boolean {
  if (!isBrowser()) return false;

  try {
    const trips = getSavedTrips();
    const filtered = trips.filter((t) => t.id !== id);
    if (filtered.length === trips.length) return false;

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { count: filtered.length } }));
    return true;
  } catch (err) {
    console.error('Error removing saved trip from localStorage:', err);
    return false;
  }
}

/**
 * Subscribe to saved trip updates across components.
 */
export function subscribeSavedTrips(callback: () => void): () => void {
  if (!isBrowser()) return () => {};

  const handler = () => callback();
  window.addEventListener(EVENT_NAME, handler);
  window.addEventListener('storage', handler);

  return () => {
    window.removeEventListener(EVENT_NAME, handler);
    window.removeEventListener('storage', handler);
  };
}

/**
 * Generate a deterministic ID for a candidate route to avoid duplicates.
 */
export function buildTripId(
  originCode: string,
  destCode: string,
  journeyDate: string,
  routeId: string
): string {
  return `${originCode.toUpperCase()}_${destCode.toUpperCase()}_${journeyDate}_${routeId}`;
}

