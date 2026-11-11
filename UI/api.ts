import type { Catalog, ChatState, SavedPlan, SearchRequest, SearchResult } from './types';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => ({ error: 'The server returned an unreadable response.' }));
  if (!response.ok) {
    throw new Error(data.error || 'The request could not be completed.');
  }
  return data as T;
}

const jsonPost = <T>(url: string, body: unknown) =>
  request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const getCatalog = () => request<Catalog>('/api/catalog');

export const sendChat = (sessionId: string | null, message: string) =>
  jsonPost<ChatState>('/api/chat', { session_id: sessionId, message });

export const resumeChat = (sessionId: string) =>
  request<ChatState>(`/api/chat/${encodeURIComponent(sessionId)}`);

export const resetChat = (sessionId: string) =>
  jsonPost<{ ok: boolean }>('/api/chat/reset', { session_id: sessionId });

export const searchRecipes = (payload: SearchRequest) =>
  jsonPost<SearchResult>('/api/search', payload);

export const answerSearchClarification = (sessionId: string, choice: number) =>
  jsonPost<SearchResult>('/api/search', { session_id: sessionId, choice });

export const selectRecipe = (sessionId: string, recipeId: string, selected: boolean) =>
  jsonPost<ChatState>('/api/chat/select', { session_id: sessionId, recipe_id: recipeId, selected });

export const getPlans = () => request<{ plans: SavedPlan[] }>('/api/plans');
export const getPlan = (planId: string) => request<{ plan: SavedPlan }>(`/api/plans/${encodeURIComponent(planId)}`);
export const openSavedPlan = (sessionId: string | null, planId: string) =>
  jsonPost<ChatState>('/api/chat/open-plan', { session_id: sessionId, plan_id: planId });
export const duplicateSavedPlan = (planId: string) =>
  jsonPost<{ plan: SavedPlan }>(`/api/plans/${encodeURIComponent(planId)}/duplicate`, {});
export const renameSavedPlan = (planId: string, name: string) =>
  jsonPost<{ plan: SavedPlan }>(`/api/plans/${encodeURIComponent(planId)}/rename`, { name });
export const finalizeSavedPlan = (planId: string) =>
  jsonPost<{ plan: SavedPlan }>(`/api/plans/${encodeURIComponent(planId)}/finalize`, {});
export const deleteSavedPlan = (planId: string) =>
  jsonPost<{ deleted: boolean }>(`/api/plans/${encodeURIComponent(planId)}/delete`, {});
