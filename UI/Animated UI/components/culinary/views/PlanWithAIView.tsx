'use client';

import React, { useState } from 'react';
import { RotateCcw, Send } from 'lucide-react';
import { useAppState } from '../../../../state';
import { RecipeCard } from '../../../../RecipeCard';
import type { ActiveScreen } from '../../../types/culinary';

export function PlanWithAIView({ onNavigate }: { onNavigate: (screen: ActiveScreen) => void }) {
  const [inputVal, setInputVal] = useState('');
  const { chat, busy, error, sendMessage, newChat, chooseRecipe, toggleRecipeSelection } = useAppState();
  const messages = chat?.messages ?? [];
  const recipes = chat?.result?.recipes ?? [];
  const selectedIds = new Set(chat?.selected_recipe_ids ?? []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const message = inputVal.trim();
    if (!message || busy) return;
    setInputVal('');
    await sendMessage(message);
  }

  return (
    <div className="culinary-view-stack w-full space-y-6 animate-fadeIn">
    <section className="culinary-view culinary-view-ai w-full bg-[#fffdfa] text-[#180e07] rounded-3xl p-6 md:p-8">
      <div className="flex items-center gap-3 pb-4 border-b border-neutral-200 mb-6">
        <div className="w-10 h-10 rounded-full bg-[#f59e0b] text-[#180e07] font-bold flex items-center justify-center text-lg">
          👨‍🍳
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-serif font-bold text-lg">DASH Meal Prep AI</h3>
          <p className="text-xs text-neutral-500">Ask for recipes, portions, filters, or plan changes</p>
        </div>
        <button type="button" onClick={newChat} disabled={busy} className="inline-flex items-center gap-1 rounded-full bg-[#f7f5f2] px-3 py-2 text-xs font-bold text-neutral-700"><RotateCcw size={13}/>New chat</button>
      </div>

      <div className="max-h-80 space-y-4 overflow-y-auto pr-1 mb-6" aria-live="polite">
        {!messages.length && <div className="bg-[#f7f5f2] p-4 rounded-2xl max-w-xl text-sm text-neutral-800">Tell me what ingredients you have, how many portions you need, and any food preference.</div>}
        {messages.filter((message) => message.role === 'user' || message.role === 'assistant').map((message, index) => (
          <div key={`${message.role}-${index}`} className={`p-4 rounded-2xl max-w-xl text-sm ${message.role === 'user' ? 'ml-auto bg-[#fdede4] text-[#b7440c] font-medium' : 'bg-[#f7f5f2] text-neutral-800'}`}>
            {message.content}
          </div>
        ))}
      </div>

      <form onSubmit={submit} className="flex items-center gap-2 border border-neutral-300 rounded-full p-2 bg-white">
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Tell us what you have or ask to change your plan..."
          className="w-full px-4 text-sm outline-none bg-transparent text-[#180e07]"
        />
        <button disabled={busy || !inputVal.trim()} className="inline-flex items-center gap-1 px-5 py-2 rounded-full bg-[#ea580c] text-white text-xs font-bold hover:bg-[#c2410c] transition disabled:opacity-50">
          {busy ? 'Working…' : 'Send'} <Send size={13}/>
        </button>
      </form>
      {error && <p className="mt-3 text-sm font-medium text-[#c2410c]">{error}</p>}
      {!!chat && <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-neutral-500"><span className="rounded-full bg-[#f7f5f2] px-3 py-1.5">{chat.context.ingredients.length ? chat.context.ingredients.join(', ') : 'No ingredients yet'}</span><span className="rounded-full bg-[#f7f5f2] px-3 py-1.5">{chat.context.servings} portions</span><span className="rounded-full bg-[#f7f5f2] px-3 py-1.5">{selectedIds.size} selected</span></div>}
    </section>

    {!!recipes.length && <section className="w-full rounded-3xl bg-[#fffdfa] p-6 text-[#180e07] shadow-2xl md:p-8"><div className="mb-5 flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-wider text-[#ea580c]">Verified recipe matches</p><h3 className="font-serif text-2xl font-bold">{chat?.result?.count ?? recipes.length} recipes</h3></div><span className="text-xs text-neutral-500">Select only what you want in your week</span></div><div className="grid gap-4 lg:grid-cols-2">{recipes.map((recipe) => <RecipeCard key={recipe.id} recipe={recipe} selected={selectedIds.has(recipe.id)} onOpen={(next) => {chooseRecipe(next);onNavigate('recipe');}} onToggleSelection={toggleRecipeSelection}/>)}</div></section>}
    </div>
  );
}
