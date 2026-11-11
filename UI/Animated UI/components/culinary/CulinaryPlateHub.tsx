'use client';

import React, { useState } from 'react';
import type { ActiveScreen, ViewportMode } from '../../types/culinary';
import { soundEngine } from '../../lib/soundEngine';
import { useAppState } from '../../../state';
import { AudioControls } from './AudioControls';
import { DimensionalPlate } from './DimensionalPlate';
import { VortexTransition } from './VortexTransition';
import { ScreenHeader } from './ScreenHeader';
import { DiningTableView } from './views/DiningTableView';
import { PlanWithAIView } from './views/PlanWithAIView';
import { RecipeDetailView } from './views/RecipeDetailView';
import { WeeklyPlanView } from './views/WeeklyPlanView';
import { GroceryListView } from './views/GroceryListView';
import { PrepDayView } from './views/PrepDayView';
import { PlanHistoryView } from './views/PlanHistoryView';

const screenNames: Record<ActiveScreen, string> = {
  plate: 'Meal-Prep Table', dining: 'Meal-Prep Hub', ai: 'Plan with AI', recipe: 'Recipe Details',
  weekly: 'Weekly Plan', grocery: 'Grocery List', prep: 'Prep Timeline', plans: 'Saved Plans',
};

export default function CulinaryPlateHub() {
  const [activeScreen, setActiveScreen] = useState<ActiveScreen>('plate');
  const [backgroundScreen, setBackgroundScreen] = useState<Exclude<ActiveScreen, 'recipe'>>('plate');
  const [viewportMode, setViewportMode] = useState<ViewportMode>('auto');
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [isVortexActive, setIsVortexActive] = useState(false);
  const [transitionTarget, setTransitionTarget] = useState('Meal Prep');
  const { chat } = useAppState();

  const toggleAudio = () => {
    soundEngine.enabled = !audioEnabled;
    setAudioEnabled(!audioEnabled);
  };

  const handleNavigate = (target: ActiveScreen) => {
    soundEngine.playPop();
    setTransitionTarget(screenNames[target]);
    setIsVortexActive(true);
    setTimeout(() => soundEngine.playVortex(), 240);
    setTimeout(() => {
      if (target === 'recipe' && activeScreen !== 'recipe') setBackgroundScreen(activeScreen);
      setActiveScreen(target);
      setIsVortexActive(false);
      soundEngine.playChime();
    }, 1100);
  };

  const returnToPlate = () => {
    soundEngine.playPop();
    setActiveScreen('plate');
  };

  return <div data-culinary-shell className="culinary-shell">
    {isVortexActive && <VortexTransition activeBladeName={transitionTarget} />}
    <div className="culinary-shell-glow" aria-hidden="true" />
    <div className="culinary-shell-inner">
      <header className="culinary-brand-bar">
        <div className="culinary-brand">
          <span className="culinary-brand-mark">🥄</span>
          <span><strong>DASH Meal Prep AI</strong><small>Personal meal prep, built around you</small></span>
        </div>
        <AudioControls viewportMode={viewportMode} setViewportMode={setViewportMode} audioEnabled={audioEnabled} toggleAudio={toggleAudio} />
      </header>

      <main className="culinary-main-stage">
        {activeScreen === 'plate' ? <section className="culinary-plate-stage" aria-labelledby="plate-title">
          <div className="culinary-kicker">🍽️ Choose a meal-prep space</div>
          <h1 id="plate-title">The Meal-Prep Table</h1>
          <p>Find recipes, build your week, combine groceries, and organize prep.</p>
          <DimensionalPlate viewportMode={viewportMode} onNavigate={handleNavigate} />
          {chat?.plan && <div className="culinary-current-plan">Current plan: <strong>{chat.plan.name}</strong></div>}
        </section> : <section data-workspace-frame data-device-mode={viewportMode} className={`culinary-workspace-frame culinary-mode-${viewportMode}`} aria-label={screenNames[activeScreen]}>
          <div className="culinary-device-notch" aria-hidden="true"><span /></div>
          <div className="culinary-workspace-surface">
            <ScreenHeader activeScreen={activeScreen} onReturn={returnToPlate} />
            <div className="culinary-workspace-scroll">
              {activeScreen === 'dining' && <DiningTableView onNavigate={handleNavigate} />}
              {activeScreen === 'ai' && <PlanWithAIView onNavigate={handleNavigate} />}
              {activeScreen === 'recipe' && <RecipeDetailView onNavigate={handleNavigate} onBack={() => setActiveScreen(backgroundScreen)} />}
              {activeScreen === 'weekly' && <WeeklyPlanView onNavigate={handleNavigate} />}
              {activeScreen === 'grocery' && <GroceryListView onNavigate={handleNavigate} />}
              {activeScreen === 'prep' && <PrepDayView onNavigate={handleNavigate} />}
              {activeScreen === 'plans' && <PlanHistoryView onNavigate={handleNavigate} />}
            </div>
          </div>
        </section>}
      </main>

      <footer className="culinary-shell-footer"><span>Built from your selected recipes and preferences</span><span>Viewing: {viewportMode === 'auto' ? 'Responsive' : viewportMode === 'desktop' ? 'Desktop' : 'Mobile'}</span></footer>
    </div>
  </div>;
}
