import React from 'react';
import { ShieldCheck, Database, GitBranch } from 'lucide-react';

export function Footer() {
  return (
    <footer className="w-full bg-cream-200/60 border-t border-cream-300 py-12 mt-20 text-xs text-espresso-600">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="font-display text-base font-bold text-espresso-900">
                TripWiser
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-terracotta text-white font-semibold">
                v1.0
              </span>
            </div>
            <p className="text-espresso-700 leading-relaxed max-w-sm">
              Discovering alternative, multi-leg railway routes across India when direct trains are sold out.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-espresso-900 uppercase tracking-wider mb-2 text-[11px]">
              Data Integrity Guarantee
            </h4>
            <ul className="space-y-1.5">
              <li className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-olive" />
                <span>Zero fabrication of fares or seat availability</span>
              </li>
              <li className="flex items-center gap-2">
                <Database className="w-4 h-4 text-olive" />
                <span>Verified 8,697 stations & real timetables</span>
              </li>
              <li className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-olive" />
                <span>Strict operating day & day offset calculation</span>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-espresso-900 uppercase tracking-wider mb-2 text-[11px]">
              Engine Status
            </h4>
            <p className="leading-relaxed">
              Timetable discovery engine connected to PostGIS spatial database. Seat availability and live commercial feeds remain deferred until official IRCTC integration.
            </p>
          </div>
        </div>

        <div className="border-t border-cream-300 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-espresso-500 text-[11px]">
          <div>
            © {new Date().getFullYear()} TripWiser Engineering. All rights reserved.
          </div>
          <div className="flex items-center gap-4">
            <span>DataMeet Railway Foundation</span>
            <span>•</span>
            <span>PostGIS Spatial Routing</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

