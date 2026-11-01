import React from 'react';
import { ShieldCheck, Info } from 'lucide-react';

interface DataIntegrityBannerProps {
  timetableStatus?: string;
  fareStatus?: string;
  availabilityStatus?: string;
  className?: string;
}

export function DataIntegrityBanner({
  timetableStatus = 'TIMETABLE_CONFIRMED',
  fareStatus = 'DEFERRED_NO_COMMERCIAL_FEED',
  availabilityStatus = 'NOT_CHECKED_SEAT_AVAILABILITY_DEFERRED',
  className = '',
}: DataIntegrityBannerProps) {
  return (
    <div
      className={`bg-cream-50 rounded-xl p-4 border border-cream-300 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs ${className}`}
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-olive/15 text-olive flex items-center justify-center flex-shrink-0 mt-0.5 sm:mt-0">
          <ShieldCheck className="w-4 h-4 text-olive" />
        </div>
        <div>
          <div className="font-semibold text-espresso-900 flex items-center gap-2 flex-wrap">
            <span>Verified Timetable Foundation</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] bg-olive/15 text-olive font-bold uppercase">
              {timetableStatus === 'TIMETABLE_CONFIRMED' ? 'Timetable Confirmed' : timetableStatus}
            </span>
          </div>
          <p className="text-espresso-600 mt-0.5 leading-relaxed">
            Routes and connections are calculated directly from official railway timetables and operating days. Live seat availability and booking feeds are strictly deferred.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 self-stretch sm:self-auto justify-end flex-shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-cream-300">
        <span
          title="Fares and live seat availability require commercial feeds which are not fabricated."
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-espresso-900/5 text-espresso-700 text-[11px] font-medium"
        >
          <Info className="w-3.5 h-3.5 text-espresso-500" />
          <span>Fares Deferred</span>
        </span>
      </div>
    </div>
  );
}

