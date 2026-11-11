'use client';

import React from 'react';
import { CalendarDays, ListChecks, Save, ShoppingBasket } from 'lucide-react';
import { useAppState } from '../../../../state';
import type { ActiveScreen } from '../../../types/culinary';

export function DiningTableView({ onNavigate }: { onNavigate: (screen: ActiveScreen) => void }) {
  const { chat, plans } = useAppState();
  const plan = chat?.plan;
  const groceryCount = chat?.grocery_list?.length ?? 0;
  const prepCount = chat?.prep_timeline?.length ?? 0;
  const spaces = [
    { label: 'Weekly plan', detail: plan ? `${plan.entries.length} selected meal${plan.entries.length === 1 ? '' : 's'}` : 'No plan yet', icon: CalendarDays, screen: 'weekly' as ActiveScreen },
    { label: 'Grocery list', detail: groceryCount ? `${groceryCount} combined item${groceryCount === 1 ? '' : 's'}` : 'Builds from your plan', icon: ShoppingBasket, screen: 'grocery' as ActiveScreen },
    { label: 'Prep timeline', detail: prepCount ? `${prepCount} source-backed task${prepCount === 1 ? '' : 's'}` : 'Organize your cooking steps', icon: ListChecks, screen: 'prep' as ActiveScreen },
    { label: 'Saved plans', detail: plans.length ? `${plans.length} plan${plans.length === 1 ? '' : 's'} ready to reuse` : 'Your plan history', icon: Save, screen: 'plans' as ActiveScreen },
  ];

  return (
    <div className="culinary-view culinary-view-dining w-full bg-[#fffdfa] text-[#180e07] rounded-3xl p-6 md:p-8 animate-fadeIn">
      <div className="flex justify-between items-start mb-6">
        <div>
          <span className="text-xs font-bold text-[#ea580c] uppercase tracking-wider">Your workspace</span>
          <h3 className="font-serif text-2xl font-bold">{plan?.name ?? 'Start with what you have'}</h3>
        </div>
        <div className="text-right">
          <span className="text-xs text-neutral-500">Saved locally</span>
          <p className="font-serif text-xl font-bold text-emerald-700">{plans.length}</p>
        </div>
      </div>

      <div className="bg-[#fdede4] border border-[#f5c6b0] rounded-2xl p-4 mb-6 flex items-center justify-between">
        <div>
          <p className="font-bold text-sm text-[#ea580c]">{plan ? 'Your meal-prep draft is ready to refine' : 'Build a plan from verified recipe sources'}</p>
          <p className="text-xs text-neutral-700">{plan ? `${plan.entries.length} user-selected meal${plan.entries.length === 1 ? '' : 's'} • ${groceryCount} grocery items` : 'Tell the AI your ingredients, then select the recipes you want.'}</p>
        </div>
        <span className="text-2xl">🥗</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {spaces.map(({ label, detail, icon: Icon, screen }) => (
          <button key={screen} type="button" onClick={() => onNavigate(screen)} className="p-4 rounded-xl border border-neutral-200 bg-white text-left shadow-sm transition hover:border-[#ea580c] hover:-translate-y-0.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#fdeee4] text-[#ea580c]"><Icon size={17} /></span>
            <h4 className="mt-3 font-serif font-bold text-base mb-1">{label}</h4>
            <p className="text-xs text-neutral-500">{detail}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
