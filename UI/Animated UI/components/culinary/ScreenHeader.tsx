'use client';

import React from 'react';
import { ArrowLeft } from 'lucide-react';
import type { ActiveScreen } from '../../types/culinary';

const labels: Record<ActiveScreen, string> = {
  plate: 'Meal-Prep Table', dining: 'Meal-Prep Hub', ai: 'Plan with AI', weekly: 'Weekly Plan',
  recipe: 'Recipe Details', grocery: 'Grocery List', prep: 'Prep Timeline', plans: 'Saved Plans',
};

export function ScreenHeader({ activeScreen, onReturn }: { activeScreen: ActiveScreen; onReturn: () => void }) {
  return <div className="culinary-screen-header">
    <button type="button" onClick={onReturn}><ArrowLeft size={12} />Return to table</button>
    <span>DASH Meal Prep AI</span>
    <strong>{labels[activeScreen]}</strong>
  </div>;
}
