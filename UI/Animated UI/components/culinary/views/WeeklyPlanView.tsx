'use client';

import React from 'react';
import { ListChecks, ShoppingBasket } from 'lucide-react';
import { useAppState } from '../../../../state';
import type { ActiveScreen } from '../../../types/culinary';

export function WeeklyPlanView({ onNavigate }: { onNavigate: (screen: ActiveScreen) => void }) {
  const { chat } = useAppState();
  const plan = chat?.plan;

  if (!plan?.entries.length) {
    return <div className="w-full bg-[#fffdfa] text-[#180e07] rounded-3xl p-8 text-center shadow-2xl animate-fadeIn"><div className="text-4xl">📅</div><h3 className="mt-4 font-serif text-2xl font-bold">No weekly plan yet</h3><p className="mt-2 text-sm text-neutral-500">Search recipes in Plan with AI, select the meals you want, and ask the assistant to place them into your week.</p><button onClick={() => onNavigate('ai')} className="mt-5 rounded-full bg-[#ea580c] px-5 py-2.5 text-sm font-bold text-white">Plan with AI</button></div>;
  }

  const days = [...new Set(plan.entries.map((entry) => entry.day))];
  return (
    <div className="w-full bg-[#fffdfa] text-[#180e07] rounded-3xl p-6 md:p-8 shadow-2xl animate-fadeIn">
      <h3 className="font-serif text-2xl font-bold mb-1">{plan.name}</h3>
      <p className="text-xs text-neutral-500 mb-6">{plan.entries.length} user-selected meal{plan.entries.length === 1 ? '' : 's'} • {plan.status ?? 'draft'}</p>

      <div className="space-y-3">
        {days.map((day, dayIndex) => {
          const entries = plan.entries.filter((entry) => entry.day === day);
          const nutrition = chat?.nutrition_summary?.days?.[day];
          return <div key={day} className="p-4 border border-neutral-200 rounded-xl hover:border-[#ea580c] transition bg-white"><div className="flex items-start justify-between gap-4"><div className="flex items-start gap-3"><span className="w-7 h-7 rounded-full bg-[#fdeee4] text-[#ea580c] text-xs font-bold flex items-center justify-center">{dayIndex + 1}</span><div><p className="font-bold text-sm text-[#180e07]">{day}</p>{entries.map((entry, index) => <p key={`${entry.meal}-${index}`} className="mt-1 text-xs text-neutral-500"><span className="font-semibold text-neutral-700">{entry.meal}:</span> {entry.title} • {entry.servings} portions</p>)}</div></div>{nutrition && <span className="shrink-0 text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full">{nutrition.sodium_mg}mg Na</span>}</div></div>;
        })}
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-2"><button onClick={() => onNavigate('grocery')} className="inline-flex items-center justify-center gap-2 rounded-full bg-[#2c1810] px-5 py-3 text-xs font-bold text-white"><ShoppingBasket size={15}/>View grocery list</button><button onClick={() => onNavigate('prep')} className="inline-flex items-center justify-center gap-2 rounded-full bg-[#ea580c] px-5 py-3 text-xs font-bold text-white"><ListChecks size={15}/>View prep timeline</button></div>
    </div>
  );
}
