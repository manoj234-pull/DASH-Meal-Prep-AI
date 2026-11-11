'use client';

import React from 'react';
import { Flame } from 'lucide-react';
import type { ActiveScreen, ViewportMode } from '../../types/culinary';
import { useAppState } from '../../../state';

interface DimensionalPlateProps {
  viewportMode: ViewportMode;
  onNavigate: (target: ActiveScreen) => void;
}

export function DimensionalPlate({ viewportMode, onNavigate }: DimensionalPlateProps) {
  const { chat, plans } = useAppState();
  const mealCount = chat?.plan?.entries.length ?? 0;
  const resultCount = chat?.result?.count ?? 0;
  const recipeTitle = chat?.result?.recipes?.[0]?.title;
  return (
    <div data-plate-hub data-plate-mode={viewportMode} className="culinary-plate-wrap">
      {/* Cutlery (visible on desktop view) */}
      {viewportMode !== 'mobile' && (
        <>
          <div className="culinary-cutlery culinary-fork" aria-hidden="true"><i/><i/><i/><i/><b/></div>
          <div className="culinary-cutlery culinary-knife" aria-hidden="true"><i/><b/></div>
        </>
      )}

      {/* Porcelain Ceramic Plate */}
      <div className="culinary-plate">
        <div className="w-full h-full rounded-full grid grid-cols-2 grid-rows-2 gap-1.5 p-1">
          {/* Quadrant 1: The Dining Table */}
          <button
            onClick={() => onNavigate('dining')}
            className="culinary-quadrant rounded-tl-full"
          >
            <div className="culinary-quadrant-icon">
              🍱
            </div>
            <span className="culinary-quadrant-title">Meal-Prep Hub</span>
            <span className="culinary-quadrant-detail">{plans.length ? `${plans.length} saved plan${plans.length === 1 ? '' : 's'}` : 'Your planning workspace'}</span>
          </button>

          {/* Quadrant 2: Plan with AI */}
          <button
            onClick={() => onNavigate('ai')}
            className="culinary-quadrant rounded-tr-full"
          >
            <div className="culinary-quadrant-icon">
              💬
            </div>
            <span className="culinary-quadrant-title">Plan with AI</span>
            <span className="culinary-quadrant-detail accent">{resultCount ? `${resultCount} recipe matches` : 'Start with ingredients'}</span>
          </button>

          {/* Quadrant 3: Recipe Detail */}
          <button
            onClick={() => onNavigate('recipe')}
            className="culinary-quadrant rounded-bl-full"
          >
            <div className="culinary-quadrant-icon">
              📖
            </div>
            <span className="culinary-quadrant-title">Recipe Details</span>
            <span className="culinary-quadrant-detail success">{recipeTitle ?? 'Choose a recipe'}</span>
          </button>

          {/* Quadrant 4: Weekly Plan */}
          <button
            onClick={() => onNavigate('weekly')}
            className="culinary-quadrant rounded-br-full"
          >
            <div className="culinary-quadrant-icon">
              📅
            </div>
            <span className="culinary-quadrant-title">Weekly Plan</span>
            <span className="culinary-quadrant-detail">{mealCount ? `${mealCount} selected meal${mealCount === 1 ? '' : 's'}` : 'Build your week'}</span>
          </button>
        </div>

        {/* Center Ceramic Nav Emblem */}
        <div className="culinary-plate-center">
          <Flame size={18} />
        </div>
      </div>
    </div>
  );
}
