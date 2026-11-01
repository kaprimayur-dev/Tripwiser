'use client';

import React, { useState } from 'react';
import { Train, Sparkles, X, Info } from 'lucide-react';

export function Navbar() {
  const [showBachelorModal, setShowBachelorModal] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-cream-100/95 backdrop-blur-md border-b border-cream-300 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-espresso-900 text-cream-100 flex items-center justify-center shadow-sm">
              <Train className="w-5 h-5 text-terracotta" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-display text-xl font-bold tracking-tight text-espresso-900">
                  TripWiser
                </span>
                <span className="hidden sm:inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-olive/15 text-olive">
                  Intelligence
                </span>
              </div>
              <p className="text-[11px] text-espresso-600 hidden sm:block">
                Indian Railway Route Discovery Engine
              </p>
            </div>
          </div>

          {/* Right Navigation & Teaser */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowBachelorModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-terracotta/10 text-terracotta border border-terracotta/20 hover:bg-terracotta/20 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-terracotta" />
              <span>Bachelor Special</span>
              <span className="text-[10px] px-1.5 py-0.2 bg-terracotta text-white rounded-full">Soon</span>
            </button>
          </div>
        </div>
      </header>

      {/* Bachelor Special Teaser Modal */}
      {showBachelorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-espresso-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 border border-cream-300 shadow-xl relative">
            <button
              onClick={() => setShowBachelorModal(false)}
              className="absolute top-4 right-4 p-1 rounded-full text-espresso-600 hover:text-espresso-900 hover:bg-cream-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="w-12 h-12 rounded-2xl bg-terracotta/10 text-terracotta flex items-center justify-center mb-4">
              <Sparkles className="w-6 h-6" />
            </div>

            <span className="text-xs font-semibold uppercase tracking-wider text-terracotta">
              Upcoming Feature
            </span>
            <h3 className="font-display text-2xl font-bold text-espresso-900 mt-1 mb-2">
              Bachelor Special Routing
            </h3>

            <p className="text-sm text-espresso-700 leading-relaxed mb-4">
              Planning a trip with friends scattered across different cities? Bachelor Special will coordinate simultaneous journeys, rendezvous layover hubs, and group seat vacancy discovery.
            </p>

            <div className="bg-cream-50 rounded-xl p-3.5 border border-cream-300 flex items-start gap-2.5 text-xs text-espresso-600 mb-5">
              <Info className="w-4 h-4 text-olive flex-shrink-0 mt-0.5" />
              <span>
                Currently in development. Milestone TW-105 focuses on core journey discovery with real railway timetables.
              </span>
            </div>

            <button
              type="button"
              onClick={() => setShowBachelorModal(false)}
              className="w-full py-2.5 bg-espresso-900 text-cream-100 rounded-xl text-sm font-semibold hover:bg-espresso-800 transition-colors"
            >
              Got It
            </button>
          </div>
        </div>
      )}
    </>
  );
}

