'use client';

import React from 'react';
import { ShoppingBasket } from 'lucide-react';
import { useAppState } from '../../../../state';
import type { ActiveScreen } from '../../../types/culinary';

export function GroceryListView({ onNavigate }: { onNavigate: (screen: ActiveScreen) => void }) {
  const { chat } = useAppState();
  const items = chat?.grocery_list ?? [];

  return <div className="w-full rounded-3xl bg-[#fffdfa] p-6 text-[#180e07] shadow-2xl animate-fadeIn md:p-8">
    <p className="text-xs font-bold uppercase tracking-wider text-[#ea580c]">Current plan</p>
    <h3 className="mt-1 font-serif text-2xl font-bold">Grocery list</h3>
    <p className="mt-1 text-xs text-neutral-500">{chat?.plan?.name ?? 'No plan selected'}</p>
    {!items.length ? <div className="mt-8 rounded-2xl border border-neutral-200 bg-white p-8 text-center"><ShoppingBasket className="mx-auto text-[#ea580c]"/><h4 className="mt-3 font-serif text-xl font-bold">Your list is waiting for a plan</h4><p className="mt-2 text-sm text-neutral-500">Select recipes and create a weekly draft first.</p><button onClick={() => onNavigate('ai')} className="mt-5 rounded-full bg-[#ea580c] px-5 py-2.5 text-sm font-bold text-white">Plan with AI</button></div> : <div className="mt-6 overflow-hidden rounded-2xl border border-neutral-200 bg-white">{items.map((item) => <div key={`${item.name}-${item.unit}`} className="flex items-center justify-between gap-5 border-b border-neutral-100 px-5 py-4 last:border-0"><span className="font-semibold">{item.name}</span><span className="text-right text-sm text-neutral-500">{item.quantity_known && item.quantity !== null ? `${item.quantity} ${item.unit}` : 'Check recipe amount'}</span></div>)}</div>}
  </div>;
}
