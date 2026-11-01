/**
 * URL Sharing utilities for TripWiser journeys.
 * Preserves search parameters (origin, destination, date, transfers, sort)
 * without exposing database internal IDs.
 */

export interface ShareJourneyParams {
  originCode: string;
  destinationCode: string;
  journeyDate: string;
  maxTransfers?: number;
  sortBy?: string;
  routeId?: string;
}

/**
 * Builds the full shareable URL string based on current window location or origin.
 */
export function buildShareableJourneyUrl(params: ShareJourneyParams): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : 'https://tripwiser.in';
  const url = new URL(origin);

  url.searchParams.set('mode', 'connecting');
  url.searchParams.set('origin', params.originCode.trim().toUpperCase());
  url.searchParams.set('destination', params.destinationCode.trim().toUpperCase());
  url.searchParams.set('date', params.journeyDate);
  if (params.maxTransfers !== undefined) {
    url.searchParams.set('transfers', String(params.maxTransfers));
  }
  if (params.sortBy) {
    url.searchParams.set('sort', params.sortBy);
  }
  if (params.routeId) {
    url.searchParams.set('route', params.routeId);
  }

  return url.toString();
}

/**
 * Copy text to clipboard with modern navigator.clipboard and legacy fallback.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (typeof window === 'undefined') return false;

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (err) {
    console.warn('navigator.clipboard failed, attempting fallback...', err);
  }

  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    return successful;
  } catch (fallbackErr) {
    console.error('Fallback clipboard copy failed:', fallbackErr);
    return false;
  }
}

