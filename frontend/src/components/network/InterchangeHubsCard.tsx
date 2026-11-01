'use client';

import React, { useState, useEffect } from 'react';
import { GitFork, ArrowRight, Train, Layers, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { InterchangeStationItem } from '../../types/api';
import { getInterchanges } from '../../services/api';

interface InterchangeHubsCardProps {
  originCode: string;
  destinationCode: string;
}

export function InterchangeHubsCard({ originCode, destinationCode }: InterchangeHubsCardProps) {
  const [interchanges, setInterchanges] = useState<InterchangeStationItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isOpen, setIsOpen] = useState<boolean>(false);

  useEffect(() => {
    if (!originCode || !destinationCode || originCode === destinationCode) {
      setInterchanges([]);
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);

    getInterchanges(originCode, destinationCode, 6)
      .then((res) => {
        if (isMounted) {
          setInterchanges(res.interchanges || []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setInterchanges([]);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [originCode, destinationCode]);

  if (loading) {
    return null;
  }

  if (interchanges.length === 0) {
    return null;
  }

  return (
    <div id="interchange-hubs-section" className="bg-white rounded-2xl border border-cream-300 shadow-sm p-4 sm:p-5 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-terracotta/10 text-terracotta flex items-center justify-center flex-shrink-0">
            <GitFork className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-display text-base font-bold text-espresso-900 leading-tight">
              Verified Interchange Junctions
            </h3>
            <p className="text-xs text-espresso-600">
              {interchanges.length} major transfer stations connecting services between {originCode} and {destinationCode}
            </p>
          </div>
        </div>

        <button
          type="button"
          id="btn-toggle-interchanges"
          onClick={() => setIsOpen((prev) => !prev)}
          className="text-xs font-semibold text-terracotta hover:text-terracotta/80 flex items-center gap-1 transition-colors px-2 py-1 rounded-lg hover:bg-cream-100"
        >
          <span>{isOpen ? 'Collapse' : 'Explore Hubs'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {isOpen && (
        <div className="pt-2 border-t border-cream-200 animate-fade-in space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {interchanges.map((hub) => (
              <div
                key={hub.station_code}
                data-testid="interchange-hub-item"
                className="bg-cream-50/80 rounded-xl p-3 border border-cream-200 space-y-2 hover:bg-cream-100/70 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs font-bold bg-cream-200 text-espresso-900 px-1.5 py-0.5 rounded">
                        {hub.station_code}
                      </span>
                      <span className="font-bold text-xs text-espresso-900 truncate">
                        {hub.station_name}
                      </span>
                    </div>
                    <div className="text-[11px] text-espresso-500 mt-0.5">
                      {[hub.city, hub.state, hub.zone ? `Zone: ${hub.zone}` : null].filter(Boolean).join(' • ')}
                    </div>
                  </div>
                </div>

                <div className="pt-1.5 border-t border-cream-200/80 grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-[10px] text-espresso-500 uppercase font-bold block">From {originCode}</span>
                    <span className="font-bold text-espresso-900">{hub.inbound_trains_count} train{hub.inbound_trains_count > 1 ? 's' : ''}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-espresso-500 uppercase font-bold block">To {destinationCode}</span>
                    <span className="font-bold text-espresso-900">{hub.outbound_trains_count} train{hub.outbound_trains_count > 1 ? 's' : ''}</span>
                  </div>
                </div>

                {hub.sample_inbound_trains.length > 0 && (
                  <div className="text-[10px] text-espresso-500 truncate">
                    Trains: <span className="font-mono text-espresso-700">{hub.sample_inbound_trains.join(', ')}</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="text-[11px] text-espresso-500 bg-cream-50 p-2.5 rounded-lg border border-cream-200 flex items-center gap-2">
            <span className="font-semibold text-espresso-700">Verified Network Data:</span>
            <span>These junction stations have scheduled timetable stops connecting both legs of the requested corridor.</span>
          </div>
        </div>
      )}
    </div>
  );
}
