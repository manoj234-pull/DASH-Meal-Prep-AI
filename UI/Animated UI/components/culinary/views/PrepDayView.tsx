'use client';

import React from 'react';
import { ListChecks } from 'lucide-react';
import { useAppState } from '../../../../state';
import type { ActiveScreen } from '../../../types/culinary';

export function PrepDayView({ onNavigate }: { onNavigate: (screen: ActiveScreen) => void }) {
  const { chat, sendMessage, busy, error } = useAppState();
  const tasks = chat?.prep_timeline ?? [];

  return <div className="w-full rounded-3xl bg-[#fffdfa] p-6 text-[#180e07] shadow-2xl animate-fadeIn md:p-8">
    <p className="text-xs font-bold uppercase tracking-wider text-[#ea580c]">Current plan</p>
    <h3 className="mt-1 font-serif text-2xl font-bold">Prep timeline</h3>
    <p className="mt-1 text-xs text-neutral-500">{chat?.plan?.name ?? 'No plan selected'}</p>
    {!tasks.length ? <div className="mt-8 rounded-2xl border border-neutral-200 bg-white p-8 text-center"><ListChecks className="mx-auto text-[#ea580c]"/><h4 className="mt-3 font-serif text-xl font-bold">{chat?.plan ? 'Organize your prep day' : 'Choose recipes first'}</h4><p className="mt-2 text-sm text-neutral-500">{chat?.plan ? 'The AI will organize only the cooking steps from your selected recipes.' : 'Create a weekly plan before generating a prep timeline.'}</p>{chat?.plan ? <button disabled={busy} onClick={() => sendMessage('Generate a prep timeline for my current weekly plan using only its source recipe steps.')} className="mt-5 rounded-full bg-[#ea580c] px-5 py-2.5 text-sm font-bold text-white disabled:opacity-60">{busy ? 'Preparing…' : 'Generate prep timeline'}</button> : <button onClick={() => onNavigate('ai')} className="mt-5 rounded-full bg-[#ea580c] px-5 py-2.5 text-sm font-bold text-white">Plan with AI</button>}</div> : <ol className="mt-6 grid gap-4 lg:grid-cols-2">{tasks.map((task, index) => <li key={`${task.title}-${index}`} className="flex gap-4 rounded-2xl border border-neutral-200 bg-white p-5"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#fdeee4] text-sm font-extrabold text-[#ea580c]">{index + 1}</span><div><h4 className="font-serif font-bold">{task.title}</h4>{task.source_texts.map((source, sourceIndex) => <p key={sourceIndex} className="mt-2 text-sm leading-relaxed text-neutral-500">{source}</p>)}</div></li>)}</ol>}
    {error && <p className="mt-4 text-sm font-medium text-[#c2410c]">{error}</p>}
  </div>;
}
