import React from 'react';
import { Clock, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface TransferAdvisoryBadgeProps {
  transferMinutes: number;
  transferStationCode?: string;
  variant?: 'compact' | 'detailed';
  className?: string;
}

export function TransferAdvisoryBadge({
  transferMinutes,
  transferStationCode,
  variant = 'compact',
  className = '',
}: TransferAdvisoryBadgeProps) {
  const formatDuration = (mins: number) => {
    const hours = Math.floor(mins / 60);
    const minutes = mins % 60;
    if (hours === 0) return `${minutes}m`;
    if (minutes === 0) return `${hours}h`;
    return `${hours}h ${minutes}m`;
  };

  if (transferMinutes < 45) {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-terracotta/10 text-terracotta border border-terracotta/20 ${className}`}
        title="Tight transfer window: minimal margin for train delays"
      >
        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
        <span>Tight Connection ({formatDuration(transferMinutes)})</span>
        {variant === 'detailed' && (
          <span className="text-[11px] font-normal block mt-1 text-terracotta">
            Minimal delay buffer. Alight promptly at {transferStationCode || 'interchange'} and navigate cross-platform transfers via foot overbridge (FOB) to connecting train.
          </span>
        )}
      </div>
    );
  }

  if (transferMinutes <= 180) {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-olive/15 text-olive border border-olive/20 ${className}`}
        title="Optimal transfer window: sufficient buffer for minor delays and platform change"
      >
        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
        <span>Comfortable Layover ({formatDuration(transferMinutes)})</span>
        {variant === 'detailed' && (
          <span className="text-[11px] font-normal block mt-1 text-olive">
            Reliable transfer buffer at {transferStationCode || 'interchange'}. Ample time for cross-platform transfers, foot overbridge transit, and waiting.
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-cream-200 text-espresso-700 border border-cream-300 ${className}`}
      title="Extended layover: ample waiting time at station"
    >
      <Clock className="w-3.5 h-3.5 flex-shrink-0" />
      <span>Extended Layover ({formatDuration(transferMinutes)})</span>
      {variant === 'detailed' && (
        <span className="text-[11px] font-normal block mt-1 text-espresso-600">
          Substantial connection window at {transferStationCode || 'interchange'}. Station waiting lounges, executive rooms, and refreshment facilities recommended.
        </span>
      )}
    </div>
  );
}

