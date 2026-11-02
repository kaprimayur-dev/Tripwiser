/**
 * Journey Plans & Personalization Persistence Manager (TW-117).
 * Provides client-side local persistence for multi-alternative Journey Plans,
 * preferred journey selection, seamless backward-compatibility with legacy My Trips (SavedTrips),
 * and journey preference settings.
 */

import { CandidateRoute, JourneyPlan, JourneyPlanOption, JourneyPreference } from '../types/api';
import { getSavedTrips, SavedTrip } from './savedTrips';

const PLANS_STORAGE_KEY = 'TRIPWISER_JOURNEY_PLANS';
const PREFERENCE_STORAGE_KEY = 'TRIPWISER_JOURNEY_PREFERENCE';
const EVENT_NAME = 'tripwiser:journey-plans-updated';

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

/**
 * Generate a deterministic ID for a Journey Plan based on origin, destination, and date.
 */
export function buildPlanId(originCode: string, destCode: string, journeyDate: string): string {
  return `PLAN_${originCode.trim().toUpperCase()}_${destCode.trim().toUpperCase()}_${journeyDate.trim()}`;
}

/**
 * Convert a CandidateRoute into a JourneyPlanOption.
 */
export function candidateRouteToPlanOption(route: CandidateRoute): JourneyPlanOption {
  const firstLeg = route.legs[0];
  const lastLeg = route.legs[route.legs.length - 1];

  const trainSummary = route.is_direct
    ? `${firstLeg.train_name} (#${firstLeg.train_number})`
    : route.legs.map((l) => `${l.train_name} (#${l.train_number})`).join(' ➔ ');

  return {
    route_id: route.route_id,
    is_direct: route.is_direct,
    transfer_count: route.transfer_count,
    total_duration_minutes: route.total_duration_minutes,
    total_travel_time_minutes: route.total_travel_time_minutes,
    total_wait_time_minutes: route.total_wait_time_minutes,
    train_summary: trainSummary,
    train_numbers: route.legs.map((l) => l.train_number),
    departure_time: firstLeg.departure_time,
    arrival_time: lastLeg.arrival_time,
    overall_transfer_risk: route.overall_transfer_risk,
    legs: route.legs,
    layovers: route.layovers,
    insights: route.insights,
    added_at: new Date().toISOString(),
  };
}

/**
 * Convert a legacy SavedTrip into a JourneyPlan.
 */
function legacySavedTripToPlan(trip: SavedTrip): JourneyPlan {
  const planId = buildPlanId(trip.originCode, trip.destinationCode, trip.journeyDate);
  const now = trip.savedAt || new Date().toISOString();

  const option: JourneyPlanOption = {
    route_id: trip.routeId,
    is_direct: trip.isDirect,
    transfer_count: trip.transferCount,
    total_duration_minutes: trip.totalDurationMinutes,
    total_travel_time_minutes: trip.totalTravelTimeMinutes,
    total_wait_time_minutes: trip.totalWaitTimeMinutes,
    train_summary: trip.trainSummary,
    train_numbers: trip.trainNumbers || [],
    departure_time: trip.departureTime,
    arrival_time: trip.arrivalTime,
    overall_transfer_risk: trip.overallTransferRisk as any,
    legs: [],
    layovers: [],
    insights: [],
    added_at: now,
  };

  return {
    id: planId,
    created_at: now,
    updated_at: now,
    origin_code: trip.originCode,
    origin_name: trip.originName,
    destination_code: trip.destinationCode,
    destination_name: trip.destinationName,
    journey_date: trip.journeyDate,
    max_transfers: trip.maxTransfers,
    preferred_route_id: trip.routeId,
    options: [option],
  };
}

/**
 * Retrieve all Journey Plans from localStorage, migrating legacy SavedTrips if needed.
 */
export function getJourneyPlans(): JourneyPlan[] {
  if (!isBrowser()) return [];

  try {
    const rawPlans = window.localStorage.getItem(PLANS_STORAGE_KEY);
    let plans: JourneyPlan[] = [];

    if (rawPlans) {
      const parsed = JSON.parse(rawPlans);
      if (Array.isArray(parsed)) {
        plans = parsed;
      }
    }

    // Check legacy SavedTrips and integrate any missing ones
    const legacyTrips = getSavedTrips();
    if (legacyTrips.length > 0) {
      let migratedAny = false;
      for (const trip of legacyTrips) {
        const expectedPlanId = buildPlanId(trip.originCode, trip.destinationCode, trip.journeyDate);
        const existingPlan = plans.find((p) => p.id === expectedPlanId);

        if (!existingPlan) {
          plans.push(legacySavedTripToPlan(trip));
          migratedAny = true;
        } else {
          // Check if this option is already inside the plan
          const hasOption = existingPlan.options.some((o) => o.route_id === trip.routeId);
          if (!hasOption) {
            existingPlan.options.push({
              route_id: trip.routeId,
              is_direct: trip.isDirect,
              transfer_count: trip.transferCount,
              total_duration_minutes: trip.totalDurationMinutes,
              total_travel_time_minutes: trip.totalTravelTimeMinutes,
              total_wait_time_minutes: trip.totalWaitTimeMinutes,
              train_summary: trip.trainSummary,
              train_numbers: trip.trainNumbers || [],
              departure_time: trip.departureTime,
              arrival_time: trip.arrivalTime,
              overall_transfer_risk: trip.overallTransferRisk as any,
              legs: [],
              layovers: [],
              insights: [],
              added_at: trip.savedAt || new Date().toISOString(),
            });
            migratedAny = true;
          }
        }
      }

      if (migratedAny) {
        window.localStorage.setItem(PLANS_STORAGE_KEY, JSON.stringify(plans));
      }
    }

    return plans;
  } catch (err) {
    console.error('Error reading journey plans from localStorage:', err);
    return [];
  }
}

/**
 * Retrieve a single Journey Plan by ID.
 */
export function getJourneyPlanById(planId: string): JourneyPlan | null {
  const plans = getJourneyPlans();
  return plans.find((p) => p.id === planId) || null;
}

/**
 * Check if a route is in any Journey Plan or a specific plan.
 */
export function isRouteInPlan(planId: string, routeId: string): boolean {
  const plan = getJourneyPlanById(planId);
  if (!plan) return false;
  return plan.options.some((o) => o.route_id === routeId);
}

/**
 * Add a CandidateRoute to a Journey Plan.
 * If the plan does not exist, creates it and marks this route as preferred.
 * If the plan exists, adds the route as an alternative (or preserves existing if already added).
 */
export function addRouteToJourneyPlan(
  originCode: string,
  originName: string,
  destCode: string,
  destName: string,
  journeyDate: string,
  maxTransfers: number,
  route: CandidateRoute,
  setAsPreferred = false
): { plan: JourneyPlan; isNewOption: boolean } {
  if (!isBrowser()) {
    throw new Error('localStorage is unavailable');
  }

  const planId = buildPlanId(originCode, destCode, journeyDate);
  const plans = getJourneyPlans();
  const existingIndex = plans.findIndex((p) => p.id === planId);
  const now = new Date().toISOString();
  const option = candidateRouteToPlanOption(route);

  let updatedPlan: JourneyPlan;
  let isNewOption = true;

  if (existingIndex >= 0) {
    const current = plans[existingIndex];
    const optIndex = current.options.findIndex((o) => o.route_id === route.route_id);

    if (optIndex >= 0) {
      // Option already exists, update legs and data
      current.options[optIndex] = option;
      isNewOption = false;
    } else {
      current.options.push(option);
    }

    if (setAsPreferred || !current.preferred_route_id) {
      current.preferred_route_id = route.route_id;
    }

    current.updated_at = now;
    plans[existingIndex] = current;
    updatedPlan = current;
  } else {
    // Create new plan
    updatedPlan = {
      id: planId,
      created_at: now,
      updated_at: now,
      origin_code: originCode.trim().toUpperCase(),
      origin_name: originName,
      destination_code: destCode.trim().toUpperCase(),
      destination_name: destName,
      journey_date: journeyDate,
      max_transfers: maxTransfers,
      preferred_route_id: route.route_id,
      options: [option],
    };
    plans.unshift(updatedPlan);
  }

  window.localStorage.setItem(PLANS_STORAGE_KEY, JSON.stringify(plans));
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { planId, count: plans.length } }));

  return { plan: updatedPlan, isNewOption };
}

/**
 * Set the preferred route for a Journey Plan.
 */
export function setPlanPreferredRoute(planId: string, routeId: string): boolean {
  if (!isBrowser()) return false;

  const plans = getJourneyPlans();
  const plan = plans.find((p) => p.id === planId);
  if (!plan) return false;

  const hasOption = plan.options.some((o) => o.route_id === routeId);
  if (!hasOption) return false;

  plan.preferred_route_id = routeId;
  plan.updated_at = new Date().toISOString();

  window.localStorage.setItem(PLANS_STORAGE_KEY, JSON.stringify(plans));
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { planId, count: plans.length } }));
  return true;
}

/**
 * Remove an individual alternative route option from a Journey Plan.
 * If the removed option was preferred, another available option becomes preferred.
 * If no options remain, the entire plan is removed.
 */
export function removeOptionFromJourneyPlan(planId: string, routeId: string): boolean {
  if (!isBrowser()) return false;

  let plans = getJourneyPlans();
  const planIndex = plans.findIndex((p) => p.id === planId);
  if (planIndex < 0) return false;

  const plan = plans[planIndex];
  const filteredOptions = plan.options.filter((o) => o.route_id !== routeId);

  if (filteredOptions.length === 0) {
    // No options left, remove the plan
    plans = plans.filter((p) => p.id !== planId);
  } else {
    plan.options = filteredOptions;
    if (plan.preferred_route_id === routeId) {
      plan.preferred_route_id = filteredOptions[0].route_id;
    }
    plan.updated_at = new Date().toISOString();
    plans[planIndex] = plan;
  }

  window.localStorage.setItem(PLANS_STORAGE_KEY, JSON.stringify(plans));
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { planId, count: plans.length } }));
  return true;
}

/**
 * Remove an entire Journey Plan by ID.
 */
export function removeJourneyPlan(planId: string): boolean {
  if (!isBrowser()) return false;

  const plans = getJourneyPlans();
  const filtered = plans.filter((p) => p.id !== planId);
  if (filtered.length === plans.length) return false;

  window.localStorage.setItem(PLANS_STORAGE_KEY, JSON.stringify(filtered));
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { planId, count: filtered.length } }));
  return true;
}

/**
 * Subscribe to Journey Plan updates across components.
 */
export function subscribeJourneyPlans(callback: () => void): () => void {
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
 * Personalization: Get and save journey search preferences.
 */
export function getSavedJourneyPreference(): JourneyPreference {
  if (!isBrowser()) return 'recommended';
  try {
    const raw = window.localStorage.getItem(PREFERENCE_STORAGE_KEY);
    if (
      raw === 'recommended' ||
      raw === 'fastest' ||
      raw === 'fewest_transfers' ||
      raw === 'comfortable'
    ) {
      return raw;
    }
    return 'recommended';
  } catch {
    return 'recommended';
  }
}

export function saveJourneyPreference(pref: JourneyPreference): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(PREFERENCE_STORAGE_KEY, pref);
  } catch (err) {
    console.error('Failed to save journey preference:', err);
  }
}

