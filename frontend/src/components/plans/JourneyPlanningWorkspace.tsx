'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Compass,
  Train,
  Clock,
  ArrowRight,
  Share2,
  Trash2,
  RefreshCw,
  Check,
  Calendar,
  AlertTriangle,
  ShieldCheck,
  Sparkles,
  ArrowUpDown,
  Plus,
  Layers,
  Star,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import { JourneyPlan, JourneyPlanOption, TransferRiskLevel } from '../../types/api';
import {
  getJourneyPlans,
  setPlanPreferredRoute,
  removeOptionFromJourneyPlan,
  removeJourneyPlan,
  subscribeJourneyPlans,
} from '../../lib/journeyPlans';
import { buildShareableJourneyUrl, copyToClipboard } from '../../lib/shareUrl';
import { TransferAdvisoryBadge } from '../results/TransferAdvisoryBadge';
import { TransitTimeline } from '../results/TransitTimeline';

interface JourneyPlanningWorkspaceProps {
  initialPlanId?: string | null;
  onRecheckPlan: (plan: JourneyPlan) => void;
  onInspectTrain: (trainNumber: string) => void;
  onNavigateSearch: () => void;
}

type CompareFilter = 'all' | 'fastest' | 'fewest_changes' | 'comfortable_transfers';

export function JourneyPlanningWorkspace({
  initialPlanId,
  onRecheckPlan,
  onInspectTrain,
  onNavigateSearch,
}: JourneyPlanningWorkspaceProps) {
  const [plans, setPlans] = useState<JourneyPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(initialPlanId || null);
  const [compareFilter, setCompareFilter] = useState<CompareFilter>('all');
  const [copiedPlanId, setCopiedPlanId] = useState<string | null>(null);
  const [expandedOptionId, setExpandedOptionId] = useState<string | null>(null);

  useEffect(() => {
    const loaded = getJourneyPlans();
    setPlans(loaded);

    if (loaded.length > 0 && !selectedPlanId) {
      if (initialPlanId && loaded.some((p) => p.id === initialPlanId)) {
        setSelectedPlanId(initialPlanId);
      } else {
        setSelectedPlanId(loaded[0].id);
      }
    }

    const unsubscribe = subscribeJourneyPlans(() => {
      const refreshed = getJourneyPlans();
      setPlans(refreshed);
      if (refreshed.length > 0 && (!selectedPlanId || !refreshed.some((p) => p.id === selectedPlanId))) {
        setSelectedPlanId(refreshed[0].id);
      }
    });

    return unsubscribe;
  }, [initialPlanId, selectedPlanId]);

  const activePlan = useMemo(() => {
    return plans.find((p) => p.id === selectedPlanId) || (plans.length > 0 ? plans[0] : null);
  }, [plans, selectedPlanId]);

  const preferredOption = useMemo(() => {
    if (!activePlan || activePlan.options.length === 0) return null;
    return (
      activePlan.options.find((o) => o.route_id === activePlan.preferred_route_id) ||
      activePlan.options[0]
    );
  }, [activePlan]);

  const sortedAlternatives = useMemo(() => {
    if (!activePlan) return [];
    const list = [...activePlan.options];

    if (compareFilter === 'fastest') {
      list.sort((a, b) => a.total_duration_minutes - b.total_duration_minutes);
    } else if (compareFilter === 'fewest_changes') {
      list.sort((a, b) => a.transfer_count - b.transfer_count || a.total_duration_minutes - b.total_duration_minutes);
    } else if (compareFilter === 'comfortable_transfers') {
      list.sort((a, b) => {
        // Direct routes first, then routes with comfortable layovers (60-180m)
        const scoreA = a.is_direct ? -100 : a.total_wait_time_minutes < 60 ? 500 : a.total_wait_time_minutes;
        const scoreB = b.is_direct ? -100 : b.total_wait_time_minutes < 60 ? 500 : b.total_wait_time_minutes;
        return scoreA - scoreB;
      });
    }

    return list;
  }, [activePlan, compareFilter]);

  const handleSetPreferred = (routeId: string) => {
    if (!activePlan) return;
    setPlanPreferredRoute(activePlan.id, routeId);
  };

  const handleRemoveOption = (routeId: string) => {
    if (!activePlan) return;
    removeOptionFromJourneyPlan(activePlan.id, routeId);
  };

  const handleDeletePlan = (planId: string) => {
    removeJourneyPlan(planId);
  };

  const handleSharePlan = async (plan: JourneyPlan) => {
    const alternativeIds = plan.options
      .filter((o) => o.route_id !== plan.preferred_route_id)
      .map((o) => o.route_id);

    const url = buildShareableJourneyUrl({
      originCode: plan.origin_code,
      destinationCode: plan.destination_code,
      journeyDate: plan.journey_date,
      maxTransfers: plan.max_transfers,
      mode: 'plan',
      preferredRouteId: plan.preferred_route_id,
      alternativeRouteIds: alternativeIds,
    });

    const success = await copyToClipboard(url);
    if (success) {
      setCopiedPlanId(plan.id);
      setTimeout(() => setCopiedPlanId(null), 2000);
    }
  };

  const formatDuration = (mins: number) => {
    const hours = Math.floor(mins / 60);
    const minutes = mins % 60;
    if (hours === 0) return `${minutes}m`;
    if (minutes === 0) return `${hours}h`;
    return `${hours}h ${minutes}m`;
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return '';
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
        return d.toLocaleDateString('en-IN', {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        });
      }
      return dateStr;
    } catch {
      return dateStr;
    }
  };

  if (plans.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-cream-300 p-8 sm:p-12 text-center max-w-xl mx-auto space-y-4 shadow-sm" id="empty-plans-view">
        <div className="w-14 h-14 bg-cream-100 rounded-full flex items-center justify-center mx-auto text-espresso-400">
          <Compass className="w-7 h-7 text-terracotta" />
        </div>
        <h2 className="font-display text-xl sm:text-2xl font-bold text-espresso-900">
          Your Journey Planning Workspace is Empty
        </h2>
        <p className="text-xs sm:text-sm text-espresso-600 leading-relaxed">
          Search connecting or direct train journeys and click <strong>&ldquo;Add to Plan&rdquo;</strong> on route cards.
          You can organize multiple alternatives under a single plan, compare them together, and designate your preferred route.
        </p>
        <div className="pt-2">
          <button
            type="button"
            id="btn-start-plan-search"
            onClick={onNavigateSearch}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-terracotta hover:bg-terracotta/90 text-white text-xs sm:text-sm font-semibold transition-colors shadow-sm"
          >
            <span>Search &amp; Plan Journeys</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" id="journey-planning-workspace">
      {/* Top Workspace Header & Plan Selector */}
      <div className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cream-200 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Compass className="w-5 h-5 text-terracotta" />
              <h2 className="font-display text-xl sm:text-2xl font-bold text-espresso-900">
                Journey Planning Workspace
              </h2>
            </div>
            <p className="text-xs text-espresso-600 mt-0.5">
              Organize, compare alternatives, and select your preferred route for each railway journey.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              id="btn-workspace-add-new-search"
              onClick={onNavigateSearch}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-cream-300 bg-cream-50 hover:bg-cream-100 text-xs font-semibold text-espresso-800 transition-colors"
            >
              <Plus className="w-3.5 h-3.5 text-terracotta" />
              <span>New Journey Search</span>
            </button>
          </div>
        </div>

        {/* Plan Switcher Pills */}
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500 flex-shrink-0">
            Active Plans:
          </span>
          {plans.map((p) => {
            const isSelected = p.id === activePlan?.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedPlanId(p.id)}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs transition-all whitespace-nowrap flex-shrink-0 border ${
                  isSelected
                    ? 'bg-espresso-900 text-cream-100 border-espresso-900 font-bold shadow-sm'
                    : 'bg-cream-50 text-espresso-700 border-cream-300 hover:bg-cream-100'
                }`}
              >
                <span>
                  {p.origin_code} ➔ {p.destination_code}
                </span>
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${isSelected ? 'bg-terracotta text-white' : 'bg-cream-200 text-espresso-600'}`}>
                  {p.options.length} {p.options.length === 1 ? 'opt' : 'opts'}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {activePlan && (
        <>
          {/* Active Plan Meta Bar */}
          <div className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-cream-200 text-espresso-800">
                    {activePlan.origin_code}
                  </span>
                  <ArrowRight className="w-4 h-4 text-terracotta" />
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-cream-200 text-espresso-800">
                    {activePlan.destination_code}
                  </span>
                  <span className="text-xs font-semibold text-espresso-600">
                    ({activePlan.origin_name} ➔ {activePlan.destination_name})
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-espresso-600">
                  <span className="inline-flex items-center gap-1 font-medium">
                    <Calendar className="w-3.5 h-3.5 text-espresso-500" />
                    <span>{formatDate(activePlan.journey_date)}</span>
                  </span>
                  <span>•</span>
                  <span>{activePlan.options.length} route {activePlan.options.length === 1 ? 'option' : 'alternatives'} saved</span>
                </div>
              </div>

              {/* Action Toolbar */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  id="btn-recheck-plan-timetable"
                  onClick={() => onRecheckPlan(activePlan)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-cream-300 bg-cream-50 hover:bg-cream-100 text-xs font-semibold text-espresso-800 transition-colors shadow-sm"
                  title="Recheck current timetable running days and transfer windows"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-terracotta" />
                  <span>Recheck Timetable</span>
                </button>

                <button
                  type="button"
                  id="btn-share-plan"
                  onClick={() => handleSharePlan(activePlan)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-cream-300 bg-cream-50 hover:bg-cream-100 text-xs font-semibold text-espresso-800 transition-colors shadow-sm"
                  title="Share this journey plan with alternatives"
                >
                  {copiedPlanId === activePlan.id ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-olive" />
                      <span className="text-olive font-bold">Link Copied!</span>
                    </>
                  ) : (
                    <>
                      <Share2 className="w-3.5 h-3.5 text-espresso-600" />
                      <span>Share Plan</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  id="btn-delete-plan"
                  onClick={() => handleDeletePlan(activePlan.id)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-cream-300 bg-white hover:bg-red-50 text-xs font-semibold text-red-600 transition-colors"
                  title="Remove this journey plan"
                >
                  <Trash2 className="w-3.5 h-3.5 text-red-500" />
                  <span>Delete Plan</span>
                </button>
              </div>
            </div>
          </div>

          {/* Preferred Journey Hero Card */}
          {preferredOption && (
            <div
              className="bg-cream-50 rounded-2xl border-2 border-terracotta/40 shadow-sm p-5 sm:p-6 space-y-4 relative overflow-hidden"
              id="preferred-journey-showcase"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-cream-300/80 pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-terracotta text-white flex items-center justify-center flex-shrink-0">
                    <Star className="w-3.5 h-3.5 fill-white text-white" />
                  </div>
                  <div>
                    <h3 className="font-display text-base sm:text-lg font-bold text-espresso-900">
                      Preferred Journey Selection
                    </h3>
                    <p className="text-[11px] text-espresso-600">
                      Designated primary itinerary for your travel on {formatDate(activePlan.journey_date)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-espresso-900 text-cream-100">
                    <ShieldCheck className="w-3 h-3 text-terracotta" />
                    <span>Selected Option</span>
                  </span>
                </div>
              </div>

              {/* Timing & Duration Strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-white p-3 rounded-xl border border-cream-300">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">Departure</span>
                  <div className="font-display text-base sm:text-lg font-bold text-espresso-900 mt-0.5">
                    {formatTime(preferredOption.departure_time)}
                  </div>
                  <span className="text-[10px] text-espresso-500">{activePlan.origin_code}</span>
                </div>

                <div className="bg-white p-3 rounded-xl border border-cream-300">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">Arrival</span>
                  <div className="font-display text-base sm:text-lg font-bold text-espresso-900 mt-0.5">
                    {formatTime(preferredOption.arrival_time)}
                  </div>
                  <span className="text-[10px] text-espresso-500">{activePlan.destination_code}</span>
                </div>

                <div className="bg-white p-3 rounded-xl border border-cream-300">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">Total Duration</span>
                  <div className="font-display text-base sm:text-lg font-bold text-terracotta mt-0.5">
                    {formatDuration(preferredOption.total_duration_minutes)}
                  </div>
                  <span className="text-[10px] text-espresso-500">
                    {preferredOption.is_direct ? 'Direct non-stop' : `${preferredOption.transfer_count} transfer(s)`}
                  </span>
                </div>

                <div className="bg-white p-3 rounded-xl border border-cream-300">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-espresso-500">Layover Waiting</span>
                  <div className="font-display text-base sm:text-lg font-bold text-espresso-900 mt-0.5">
                    {preferredOption.is_direct ? '0m' : formatDuration(preferredOption.total_wait_time_minutes)}
                  </div>
                  <span className="text-[10px] text-espresso-500">
                    Travel: {formatDuration(preferredOption.total_travel_time_minutes)}
                  </span>
                </div>
              </div>

              {/* Transit Timeline of Preferred Option */}
              {preferredOption.legs && preferredOption.legs.length > 0 && (
                <div className="pt-2">
                  <TransitTimeline route={preferredOption as any} />
                </div>
              )}

              {/* Leg Timetable Quick Inspectors */}
              <div className="pt-2 border-t border-cream-300/80 flex items-center justify-between flex-wrap gap-2 text-xs">
                <div className="flex items-center gap-1.5 text-espresso-600">
                  <Train className="w-3.5 h-3.5 text-terracotta" />
                  <span className="font-semibold text-espresso-800">Train Services:</span>
                  <span>{preferredOption.train_summary}</span>
                </div>

                <div className="flex items-center gap-2">
                  {preferredOption.train_numbers.map((num) => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => onInspectTrain(num)}
                      className="px-2 py-1 rounded-lg bg-cream-200/90 hover:bg-cream-300 text-espresso-800 text-[11px] font-bold transition-colors border border-cream-300"
                    >
                      Inspect #{num} Timetable
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Compare Alternatives Section */}
          <div className="bg-white rounded-2xl border border-cream-300 shadow-sm p-5 sm:p-6 space-y-4" id="compare-alternatives-section">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cream-200 pb-3">
              <div>
                <h3 className="font-display text-lg font-bold text-espresso-900 flex items-center gap-2">
                  <ArrowUpDown className="w-4 h-4 text-terracotta" />
                  <span>Compare Journey Alternatives ({activePlan.options.length})</span>
                </h3>
                <p className="text-xs text-espresso-600 mt-0.5">
                  Evaluate all saved options side-by-side to choose your best travel route.
                </p>
              </div>

              {/* Priority Sorting Filters */}
              <div className="flex items-center gap-1 bg-cream-100 p-1 rounded-xl border border-cream-300 self-start sm:self-auto overflow-x-auto no-scrollbar">
                <button
                  type="button"
                  onClick={() => setCompareFilter('all')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                    compareFilter === 'all' ? 'bg-white text-espresso-900 shadow-sm font-bold' : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  All Options
                </button>
                <button
                  type="button"
                  id="filter-compare-fastest"
                  onClick={() => setCompareFilter('fastest')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                    compareFilter === 'fastest' ? 'bg-white text-espresso-900 shadow-sm font-bold' : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  Fastest Journey
                </button>
                <button
                  type="button"
                  id="filter-compare-fewest-changes"
                  onClick={() => setCompareFilter('fewest_changes')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                    compareFilter === 'fewest_changes' ? 'bg-white text-espresso-900 shadow-sm font-bold' : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  Fewest Changes
                </button>
                <button
                  type="button"
                  id="filter-compare-comfortable"
                  onClick={() => setCompareFilter('comfortable_transfers')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                    compareFilter === 'comfortable_transfers' ? 'bg-white text-espresso-900 shadow-sm font-bold' : 'text-espresso-600 hover:text-espresso-900'
                  }`}
                >
                  Comfortable Transfers
                </button>
              </div>
            </div>

            {/* Alternatives Cards List */}
            <div className="space-y-3">
              {sortedAlternatives.map((opt) => {
                const isPreferred = opt.route_id === activePlan.preferred_route_id;
                const isExpanded = expandedOptionId === opt.route_id;

                return (
                  <div
                    key={opt.route_id}
                    className={`rounded-xl border transition-all p-4 ${
                      isPreferred
                        ? 'bg-cream-50/70 border-terracotta/40 ring-1 ring-terracotta/20'
                        : 'bg-white border-cream-300 hover:border-cream-400'
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      {/* Left Route Identity */}
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          {isPreferred ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-terracotta text-white">
                              <Star className="w-3 h-3 fill-white" />
                              <span>Preferred</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-cream-200 text-espresso-800">
                              <span>Alternative</span>
                            </span>
                          )}

                          <span className="text-xs font-bold text-espresso-900">
                            {formatTime(opt.departure_time)} ➔ {formatTime(opt.arrival_time)}
                          </span>

                          <span className="text-xs font-mono font-bold text-terracotta">
                            {formatDuration(opt.total_duration_minutes)}
                          </span>

                          <span className="text-[11px] text-espresso-500">
                            ({opt.is_direct ? 'Direct' : `${opt.transfer_count} change`})
                          </span>
                        </div>

                        <div className="text-xs text-espresso-700 flex items-center gap-1.5">
                          <Train className="w-3 h-3 text-espresso-400 flex-shrink-0" />
                          <span className="truncate">{opt.train_summary}</span>
                        </div>
                      </div>

                      {/* Right Metrics & Actions */}
                      <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap justify-between sm:justify-end">
                        <div className="text-right text-[11px] text-espresso-600 hidden md:block">
                          <div>Travel: {formatDuration(opt.total_travel_time_minutes)}</div>
                          <div>Wait: {formatDuration(opt.total_wait_time_minutes)}</div>
                        </div>

                        {opt.overall_transfer_risk && (
                          <TransferAdvisoryBadge
                            transferMinutes={opt.total_wait_time_minutes}
                            riskLevel={opt.overall_transfer_risk}
                          />
                        )}

                        <div className="flex items-center gap-1.5">
                          {!isPreferred && (
                            <button
                              type="button"
                              onClick={() => handleSetPreferred(opt.route_id)}
                              className="px-2.5 py-1 rounded-lg bg-cream-100 hover:bg-cream-200 text-espresso-800 text-xs font-semibold transition-colors border border-cream-300"
                              title="Designate this option as your preferred journey"
                            >
                              Set as Preferred
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => setExpandedOptionId(isExpanded ? null : opt.route_id)}
                            className="p-1 rounded-lg text-espresso-500 hover:text-espresso-800 hover:bg-cream-100 transition-colors"
                            title={isExpanded ? 'Collapse itinerary' : 'Expand itinerary'}
                          >
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>

                          {activePlan.options.length > 1 && (
                            <button
                              type="button"
                              onClick={() => handleRemoveOption(opt.route_id)}
                              className="p-1 rounded-lg text-espresso-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                              title="Remove this alternative"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Collapsible Details */}
                    {isExpanded && opt.legs && opt.legs.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-cream-200">
                        <TransitTimeline route={opt as any} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Local Storage & Timetable Guarantee Disclosure */}
      <div className="bg-cream-50 rounded-2xl border border-cream-300 p-4 text-xs text-espresso-600 space-y-1">
        <div className="flex items-center gap-1.5 font-bold text-espresso-800">
          <Info className="w-4 h-4 text-olive" />
          <span>Workspace Persistence &amp; Timetable Disclosures</span>
        </div>
        <p className="text-[11px] leading-relaxed">
          Your journey plans and selected alternatives are stored locally within this browser. To access this plan on another computer or mobile device, use the <strong>&ldquo;Share Plan&rdquo;</strong> button to generate a shareable link.
        </p>
        <p className="text-[11px] leading-relaxed text-espresso-500">
          Timetables and transfer windows reflect compiled Indian Railways TAG records. Transfer windows are scheduled connection windows, not guaranteed connections or live train delay predictions.
        </p>
      </div>
    </div>
  );
}

