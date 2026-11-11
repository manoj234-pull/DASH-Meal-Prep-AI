import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  answerSearchClarification,
  deleteSavedPlan,
  duplicateSavedPlan,
  finalizeSavedPlan,
  getCatalog,
  getPlans,
  openSavedPlan,
  renameSavedPlan,
  resetChat as resetChatRequest,
  resumeChat,
  searchRecipes,
  sendChat,
  selectRecipe,
} from './api';
import type { Catalog, ChatState, Recipe, SavedPlan, SearchRequest, SearchResult } from './types';

const SESSION_KEY = 'dash-chat-token';
const PLAN_KEY = 'dash-current-plan-id';

interface AppStateValue {
  chat: ChatState | null;
  catalog: Catalog | null;
  searchResult: SearchResult | null;
  selectedRecipe: Recipe | null;
  busy: boolean;
  error: string;
  plans: SavedPlan[];
  sendMessage: (message: string) => Promise<void>;
  newChat: () => Promise<void>;
  runSearch: (request: SearchRequest) => Promise<void>;
  answerClarification: (sessionId: string, choice: number) => Promise<void>;
  chooseRecipe: (recipe: Recipe | null) => void;
  clearError: () => void;
  toggleRecipeSelection: (recipeId: string, selected: boolean) => Promise<void>;
  openPlan: (planId: string) => Promise<void>;
  duplicatePlan: (planId: string) => Promise<void>;
  renamePlan: (planId: string, name: string) => Promise<void>;
  finalizePlan: (planId: string) => Promise<void>;
  deletePlan: (planId: string) => Promise<void>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [chat, setChat] = useState<ChatState | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [plans, setPlans] = useState<SavedPlan[]>([]);

  async function refreshPlans() {
    const response = await getPlans();setPlans(response.plans);
  }

  function acceptChat(next: ChatState) {
    setChat(next);
    setSelectedRecipe((current) => {
      if (!current) return null;
      return next.result?.recipes.find((recipe) => recipe.id === current.id) ?? current;
    });
    sessionStorage.setItem(SESSION_KEY,next.session_id);
    if (next.saved_plan_id) localStorage.setItem(PLAN_KEY,next.saved_plan_id);
  }

  async function restorePlanAfterExpiredChat(planId: string) {
    const next = await openSavedPlan(null, planId);
    acceptChat(next);
    return next;
  }

  useEffect(() => {
    getCatalog().then(setCatalog).catch((cause) => setError(cause.message));
    refreshPlans().catch((cause) => setError(cause.message));
    const token=sessionStorage.getItem(SESSION_KEY);const planId=localStorage.getItem(PLAN_KEY);
    if (!token && !planId) return;
    setBusy(true);
    (token ? resumeChat(token).catch(() => planId ? restorePlanAfterExpiredChat(planId) : Promise.reject()) : openSavedPlan(null,planId!))
      .then(acceptChat)
      .catch(() => {sessionStorage.removeItem(SESSION_KEY);if (!planId) localStorage.removeItem(PLAN_KEY);})
      .finally(() => setBusy(false));
  }, []);

  async function sendMessage(message: string) {
    const clean = message.trim();
    if (!clean || busy) return;
    setBusy(true);
    setError('');
    try {
      let next: ChatState;
      try {
        next = await sendChat(chat?.session_id ?? null, clean);
      } catch (cause) {
        const planId=localStorage.getItem(PLAN_KEY);
        if (!(cause instanceof Error) || !cause.message.toLowerCase().includes('expired') || !planId) throw cause;
        const restored=await restorePlanAfterExpiredChat(planId);
        next=await sendChat(restored.session_id,clean);
      }
      acceptChat(next);
      if (next.saved_plan_id) {localStorage.setItem(PLAN_KEY,next.saved_plan_id);await refreshPlans();}
      setSearchResult(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function toggleRecipeSelection(recipeId:string,selected:boolean) {
    if (!chat?.session_id || busy) return;setBusy(true);setError('');
    try {setChat(await selectRecipe(chat.session_id,recipeId,selected));}
    catch (cause) {setError(cause instanceof Error?cause.message:'Please try again.');}
    finally {setBusy(false);}
  }

  async function openPlan(planId:string) {
    setBusy(true);setError('');
    try {const next=await openSavedPlan(chat?.session_id??null,planId);setChat(next);sessionStorage.setItem(SESSION_KEY,next.session_id);localStorage.setItem(PLAN_KEY,planId);}
    catch (cause) {setError(cause instanceof Error?cause.message:'Please try again.');}
    finally {setBusy(false);}
  }
  async function duplicatePlan(planId:string) {const result=await duplicateSavedPlan(planId);await refreshPlans();await openPlan(result.plan.plan_id);}
  async function renamePlan(planId:string,name:string) {await renameSavedPlan(planId,name);await refreshPlans();if (chat?.saved_plan_id===planId) await openPlan(planId);}
  async function finalizePlan(planId:string) {await finalizeSavedPlan(planId);await refreshPlans();if (chat?.saved_plan_id===planId) await openPlan(planId);}
  async function deletePlan(planId:string) {await deleteSavedPlan(planId);await refreshPlans();if (chat?.saved_plan_id===planId) {localStorage.removeItem(PLAN_KEY);setChat(null);}}

  async function newChat() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      if (chat?.session_id) await resetChatRequest(chat.session_id);
    } catch (cause) {
      if (!(cause instanceof Error) || !cause.message.includes('expired')) setError(String(cause));
    } finally {
      sessionStorage.removeItem(SESSION_KEY);
      localStorage.removeItem(PLAN_KEY);
      setChat(null);
      setSearchResult(null);
      setSelectedRecipe(null);
      setBusy(false);
    }
  }

  async function runSearch(payload: SearchRequest) {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      setSearchResult(await searchRecipes(payload));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function answerClarification(sessionId: string, choice: number) {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      setSearchResult(await answerSearchClarification(sessionId, choice));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Please try again.');
    } finally {
      setBusy(false);
    }
  }

  const value = useMemo<AppStateValue>(() => ({
    chat,
    catalog,
    searchResult,
    selectedRecipe,
    busy,
    error,
    plans,
    sendMessage,
    newChat,
    runSearch,
    answerClarification,
    chooseRecipe: setSelectedRecipe,
    clearError: () => setError(''),
    toggleRecipeSelection,openPlan,duplicatePlan,renamePlan,finalizePlan,deletePlan,
  }), [chat, catalog, searchResult, selectedRecipe, busy, error, plans]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const value = useContext(AppStateContext);
  if (!value) throw new Error('useAppState must be used inside AppStateProvider');
  return value;
}
