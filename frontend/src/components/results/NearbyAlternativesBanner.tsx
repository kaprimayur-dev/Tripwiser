'use client';

import React from 'react';
import { Navigation, ArrowRight, Train, Sparkles } from 'lucide-react';

interface NearbyAlternativesBannerProps {
  currentOriginCode: string;
  currentDestinationCode: string;
  onSelectAlternative: (originCode: string, destinationCode: string) => void;
}

interface ClusterHub {
  code: string;
  name: string;
  cluster: string;
  twinStations: { code: string; name: string; distanceDesc: string }[];
}

const METROPOLITAN_CLUSTERS: Record<string, ClusterHub> = {
  NDLS: {
    code: 'NDLS',
    name: 'New Delhi',
    cluster: 'Delhi NCR Hub',
    twinStations: [
      { code: 'NZM', name: 'Hazrat Nizamuddin', distanceDesc: '5 km south' },
      { code: 'DLI', name: 'Old Delhi Junction', distanceDesc: '4 km north' },
    ],
  },
  NZM: {
    code: 'NZM',
    name: 'Hazrat Nizamuddin',
    cluster: 'Delhi NCR Hub',
    twinStations: [
      { code: 'NDLS', name: 'New Delhi', distanceDesc: '5 km north' },
    ],
  },
  BCT: {
    code: 'BCT',
    name: 'Mumbai Central',
    cluster: 'Mumbai Metropolitan Hub',
    twinStations: [
      { code: 'BDTS', name: 'Bandra Terminus', distanceDesc: '10 km north' },
      { code: 'CSMT', name: 'Chhatrapati Shivaji Maharaj Terminus', distanceDesc: '4 km south' },
    ],
  },
  HWH: {
    code: 'HWH',
    name: 'Howrah Junction',
    cluster: 'Kolkata Metropolitan Hub',
    twinStations: [
      { code: 'SDAH', name: 'Sealdah', distanceDesc: '5 km east (across Hooghly)' },
    ],
  },
  BPL: {
    code: 'BPL',
    name: 'Bhopal Junction',
    cluster: 'Bhopal Urban Hub',
    twinStations: [
      { code: 'RKMP', name: 'Rani Kamlapati', distanceDesc: '6 km south' },
    ],
  },
};

export function NearbyAlternativesBanner({
  currentOriginCode,
  currentDestinationCode,
  onSelectAlternative,
}: NearbyAlternativesBannerProps) {
  const originHub = METROPOLITAN_CLUSTERS[currentOriginCode.toUpperCase()];
  const destHub = METROPOLITAN_CLUSTERS[currentDestinationCode.toUpperCase()];

  if (!originHub && !destHub) return null;

  return (
    <div className="bg-cream-50 rounded-2xl border border-cream-300 p-4 sm:p-5 shadow-sm space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-olive/15 text-olive flex items-center justify-center flex-shrink-0 mt-0.5">
          <Navigation className="w-4 h-4" />
        </div>
        <div className="space-y-1">
          <div className="font-semibold text-xs text-espresso-900 flex items-center gap-2">
            <span>Nearby Boarding &amp; Terminal Recommendations</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] bg-olive/15 text-olive font-bold">
              Spatial Proximity
            </span>
          </div>
          <p className="text-xs text-espresso-600 leading-relaxed">
            In major metropolitan hubs like {originHub?.cluster || destHub?.cluster}, premium and express trains often depart from twin satellite terminals. Consider these nearby terminal recommendations for alternate departure timings or improved seat availability.
          </p>
        </div>
      </div>

      {/* Suggestion Buttons */}
      <div className="flex items-center gap-2 flex-wrap pt-1 pl-0 sm:pl-11">
        {originHub?.twinStations.map((twin) => (
          <button
            key={twin.code}
            type="button"
            onClick={() => onSelectAlternative(twin.code, currentDestinationCode)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-cream-300 bg-white hover:bg-terracotta hover:text-white hover:border-terracotta text-espresso-800 text-xs font-semibold transition-all shadow-sm group"
          >
            <Train className="w-3.5 h-3.5 text-terracotta group-hover:text-white transition-colors" />
            <span>Try From {twin.name} ({twin.code})</span>
            <span className="text-[10px] text-espresso-500 group-hover:text-white/80">
              • {twin.distanceDesc}
            </span>
          </button>
        ))}

        {destHub?.twinStations.map((twin) => (
          <button
            key={twin.code}
            type="button"
            onClick={() => onSelectAlternative(currentOriginCode, twin.code)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-cream-300 bg-white hover:bg-olive hover:text-white hover:border-olive text-espresso-800 text-xs font-semibold transition-all shadow-sm group"
          >
            <Train className="w-3.5 h-3.5 text-olive group-hover:text-white transition-colors" />
            <span>Try To {twin.name} ({twin.code})</span>
            <span className="text-[10px] text-espresso-500 group-hover:text-white/80">
              • {twin.distanceDesc}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

