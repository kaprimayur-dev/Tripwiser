import React from 'react';
import { Clock, AlertTriangle, CheckCircle2, AlertOctagon, HelpCircle } from 'lucide-react';
import { TransferRiskLevel } from '../../types/api';

interface TransferAdvisoryBadgeProps {
  transferMinutes: number;
  transferStationCode?: string;
  riskLevel?: TransferRiskLevel;
  riskDescription?: string;
  variant?: 'compact' | 'detailed';
  className?: string;
}

export function TransferAdvisoryBadge({
  transferMinutes,
  transferStationCode,
  riskLevel,
  riskDescription,
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

  // Determine tier if not explicitly passed
  let level: TransferRiskLevel = riskLevel || 'COMFORTABLE_CONNECTION';
  if (!riskLevel) {
    if (transferMinutes < 30) {
      level = 'INVALID_CONNECTION';
    } else if (transferMinutes <= 44) {
      level = 'TIGHT_CONNECTION';
    } else if (transferMinutes <= 89) {
      level = 'MODERATE_CONNECTION';
    } else if (transferMinutes <= 180) {
      level = 'COMFORTABLE_CONNECTION';
    } else {
      level = 'LONG_WAIT';
    }
  }

  if (level === 'INVALID_CONNECTION') {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-300 ${className}`}
        title="Scheduled transfer time is below the 30-minute minimum buffer"
      >
        <AlertOctagon className="w-3.5 h-3.5 flex-shrink-0 text-red-600" />
        <span>Invalid Connection ({formatDuration(transferMinutes)})</span>
        {variant === 'detailed' && (
          <span className="text-[11px] font-normal block mt-1 text-red-700">
            {riskDescription || `Transfer window of ${transferMinutes}m at ${transferStationCode || 'interchange'} violates the minimum 30-minute connection window.`}
          </span>
        )}
      </div>
    );
  }

  if (level === 'TIGHT_CONNECTION') {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300 ${className}`}
        title="Tight scheduled connection: limited buffer for inbound delays"
      >
        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 text-amber-600" />
        <span>Tight Connection ({formatDuration(transferMinutes)})</span>
        {variant === 'detailed' && (
          <span className="text-[11px] font-normal block mt-1 text-amber-800">
            {riskDescription || `Tight ${transferMinutes}m scheduled buffer at ${transferStationCode || 'interchange'}. Delays to inbound train may risk missing the connecting service.`}
          </span>
        )}
      </div>
    );
  }

  if (level === 'MODERATE_CONNECTION') {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-800 border border-blue-200 ${className}`}
        title="Moderate scheduled connection window"
      >
        <Clock className="w-3.5 h-3.5 flex-shrink-0 text-blue-600" />
        <span>Moderate Connection ({formatDuration(transferMinutes)})</span>
        {variant === 'detailed' && (
          <span className="text-[11px] font-normal block mt-1 text-blue-700">
            {riskDescription || `Moderate scheduled transfer buffer of ${transferMinutes}m at ${transferStationCode || 'interchange'}.`}
          </span>
        )}
      </div>
    );
  }

  if (level === 'COMFORTABLE_CONNECTION') {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-olive/15 text-olive border border-olive/20 ${className}`}
        title="Comfortable scheduled layover with ample transfer window"
      >
        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
        <span>Comfortable Connection ({formatDuration(transferMinutes)})</span>
        {variant === 'detailed' && (
          <span className="text-[11px] font-normal block mt-1 text-olive">
            {riskDescription || `Comfortable ${formatDuration(transferMinutes)} scheduled layover at ${transferStationCode || 'interchange'}.`}
          </span>
        )}
      </div>
    );
  }

  // LONG_WAIT
  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-cream-200 text-espresso-700 border border-cream-300 ${className}`}
      title="Extended layover between connecting trains"
    >
      <Clock className="w-3.5 h-3.5 flex-shrink-0 text-espresso-600" />
      <span>Long Wait ({formatDuration(transferMinutes)})</span>
      {variant === 'detailed' && (
        <span className="text-[11px] font-normal block mt-1 text-espresso-600">
          {riskDescription || `Extended scheduled waiting period of ${formatDuration(transferMinutes)} at ${transferStationCode || 'interchange'}.`}
        </span>
      )}
    </div>
  );
}

