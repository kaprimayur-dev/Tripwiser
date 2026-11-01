'use client';

import React from 'react';
import { Train, ArrowRight, RefreshCw, ShieldCheck, Info, CheckCircle2 } from 'lucide-react';
import { BachelorSpecialItinerary } from '../../types/api';

interface BachelorSpecialCardProps {
  itinerary: BachelorSpecialItinerary;
  index: number;
}

export function BachelorSpecialCard({ itinerary, index }: BachelorSpecialCardProps) {
  const getBerthTypeFullName = (type: string) => {
    switch (type.toUpperCase()) {
      case 'LB':
        return 'Lower Berth';
      case 'MB':
        return 'Middle Berth';
      case 'UB':
        return 'Upper Berth';
      case 'SL':
        return 'Side Lower';
      case 'SU':
        return 'Side Upper';
      default:
        return `${type} Berth`;
    }
  };

  const isRecommended = index === 0;

  return (
    <article
      id={`bachelor-card-${index}`}
      className={`rounded-2xl border transition-all duration-200 overflow-hidden bg-white shadow-sm hover:shadow-md ${
        isRecommended ? 'border-terracotta/40 ring-1 ring-terracotta/20' : 'border-cream-300'
      }`}
    >
      <div className="p-5 sm:p-6 space-y-5">
        {/* Header Badges */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            {isRecommended && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-espresso-900 text-cream-100 shadow-sm">
                <span>RECOMMENDED ITINERARY</span>
              </span>
            )}
            <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-terracotta/15 text-terracotta border border-terracotta/20">
              {itinerary.berth_changes_count === 0
                ? 'DIRECT THROUGH BERTH'
                : `${itinerary.berth_changes_count} BERTH CHANGE${itinerary.berth_changes_count > 1 ? 'S' : ''}`}
            </span>
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-cream-200 text-espresso-800 border border-cream-300">
              {itinerary.total_segment_count} Contiguous Segments
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-olive font-semibold">
            <ShieldCheck className="w-4 h-4 text-olive" />
            <span>Same-Train Service</span>
          </div>
        </div>

        {/* Train Details */}
        <div className="flex items-center justify-between gap-4 pb-4 border-b border-cream-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-espresso-900 text-cream-100 flex items-center justify-center flex-shrink-0">
              <Train className="w-5 h-5 text-terracotta" />
            </div>
            <div>
              <h3 className="font-display text-lg font-bold text-espresso-900">
                {itinerary.train_name}
              </h3>
              <div className="flex items-center gap-2 text-xs text-espresso-600 font-mono">
                <span>Train #{itinerary.train_number}</span>
                <span>•</span>
                <span>Class {itinerary.travel_class}</span>
                <span>•</span>
                <span>{itinerary.travel_date}</span>
              </div>
            </div>
          </div>

          <div className="text-right">
            <span className="text-[11px] font-bold uppercase tracking-wider text-espresso-500">
              Journey Span
            </span>
            <div className="font-mono text-sm font-bold text-espresso-900">
              {itinerary.origin_code} ➔ {itinerary.destination_code}
            </div>
          </div>
        </div>

        {/* Continuous Segment Breakdown & Berth Changes */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-espresso-500">
            Continuous Berth Segments
          </h4>

          <div className="space-y-2.5">
            {itinerary.segments.map((seg, sIdx) => {
              const isLast = sIdx === itinerary.segments.length - 1;
              const nextSeg = !isLast ? itinerary.segments[sIdx + 1] : null;

              return (
                <React.Fragment key={`${seg.segment_id}-${sIdx}`}>
                  {/* Berth Segment Node */}
                  <div className="p-3.5 bg-cream-50 rounded-xl border border-cream-300 flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3">
                      <span className="w-7 h-7 rounded-lg bg-white text-espresso-900 border border-cream-300 font-mono font-bold text-xs flex items-center justify-center">
                        {sIdx + 1}
                      </span>
                      <div>
                        <div className="flex items-center gap-1.5 font-semibold text-xs text-espresso-900">
                          <span className="font-mono text-terracotta">{seg.from_station_code}</span>
                          <ArrowRight className="w-3.5 h-3.5 text-espresso-400" />
                          <span className="font-mono text-terracotta">{seg.to_station_code}</span>
                          <span className="text-espresso-400 font-normal">
                            (stops {seg.from_sequence} ➔ {seg.to_sequence})
                          </span>
                        </div>
                        <div className="text-[11px] text-espresso-600 mt-0.5">
                          {getBerthTypeFullName(seg.berth_type)}
                        </div>
                      </div>
                    </div>

                    {/* Allocated Berth Badge */}
                    <div className="flex items-center gap-2">
                      <div className="px-3 py-1.5 rounded-xl bg-white border border-cream-300 shadow-sm text-right">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 block">
                          Coach / Berth
                        </span>
                        <span className="font-mono font-bold text-sm text-espresso-900">
                          {seg.coach} - {seg.berth_number}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Berth Hand-off indicator if moving to another berth */}
                  {nextSeg && (
                    <div className="px-4 py-2 rounded-xl bg-terracotta/5 border border-terracotta/20 flex items-center gap-2 text-xs text-terracotta">
                      <RefreshCw className="w-3.5 h-3.5 flex-shrink-0 animate-spin-slow" />
                      <span>
                        <strong>Berth Relocation at {seg.to_station_code}:</strong> Move from{' '}
                        <span className="font-mono font-semibold">{seg.coach}-{seg.berth_number}</span> to{' '}
                        <span className="font-mono font-semibold">{nextSeg.coach}-{nextSeg.berth_number}</span>{' '}
                        ({nextSeg.coach !== seg.coach ? 'Inter-coach transfer' : 'Same coach'}). No train interchange.
                      </span>
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Ticketing Policy & Disclaimer */}
        <div className="p-3.5 rounded-xl bg-cream-50 border border-cream-200 flex items-start gap-2.5 text-[11px] text-espresso-600 leading-relaxed">
          <Info className="w-4 h-4 text-olive flex-shrink-0 mt-0.5" />
          <span>
            <strong>Bachelor Special Policy:</strong> This itinerary combines vacant berth allocations on the same train. Individual berth segments may require point-to-point ticket booking or TTE confirmation. One composite PNR is not guaranteed.
          </span>
        </div>
      </div>
    </article>
  );
}

