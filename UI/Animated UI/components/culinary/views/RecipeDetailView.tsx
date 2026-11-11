'use client';

import React from 'react';
import { ArrowLeft, ExternalLink, Minus, Plus } from 'lucide-react';
import { useAppState } from '../../../../state';
import type { ActiveScreen } from '../../../types/culinary';

export function RecipeDetailView({ onNavigate, onBack }: { onNavigate: (screen: ActiveScreen) => void; onBack: () => void }) {
  const { selectedRecipe: recipe, busy, sendMessage, toggleRecipeSelection, chat } = useAppState();

  if (!recipe) return <section className="culinary-view culinary-view-empty culinary-view-recipe">
    <div className="culinary-empty-icon">📖</div><h3>Choose a recipe first</h3>
    <p>Search your ingredients, then open a recipe to see its verified details.</p>
    <button type="button" onClick={() => onNavigate('ai')} className="culinary-primary-action">Plan with AI</button>
  </section>;

  const servings = recipe.requested_servings;
  const selected = (chat?.selected_recipe_ids ?? []).includes(recipe.id);

  return <article className="culinary-view culinary-view-recipe">
    <div className="culinary-view-heading">
      <div><span className="culinary-eyebrow">Recipe details</span><h2>{recipe.title}</h2></div>
      <span className="culinary-score">{recipe.match_percent}% match</span>
    </div>

    <div className="culinary-stat-row">
      <div><small>Portions</small><strong>{servings}</strong></div>
      <div><small>Sodium</small><strong>{recipe.sodium_mg_per_serving === null ? 'Unknown' : `${recipe.sodium_mg_per_serving} mg`}</strong></div>
      <div><small>Ingredients</small><strong>{recipe.matched_count}/{recipe.required_count}</strong></div>
    </div>

    <div className="culinary-portion-row">
      <span><small>Adjust portions</small><strong>{servings} servings</strong></span>
      <span className="culinary-stepper">
        <button type="button" disabled={busy || servings <= 1} onClick={() => sendMessage(`Change my requested portions to ${Math.max(1, servings - 1)} and refresh the current recipe results.`)}><Minus size={13}/></button>
        <button type="button" disabled={busy} onClick={() => sendMessage(`Change my requested portions to ${servings + 1} and refresh the current recipe results.`)}><Plus size={13}/></button>
      </span>
    </div>

    <div className="culinary-detail-grid">
      <section><h3>Ingredient quantities</h3><div className="culinary-ingredient-list">{recipe.scaled_ingredients.map((ingredient, index) => <div key={`${ingredient.name}-${index}`}><span>{ingredient.source_description || ingredient.name}</span><strong>{ingredient.quantity === null ? 'Amount unavailable' : `${ingredient.quantity} ${ingredient.unit}`}</strong></div>)}</div></section>
      <section><h3>Preparation instructions</h3><ol className="culinary-steps">{recipe.steps.map((step, index) => <li key={index}><span>{index + 1}</span><p>{step}</p></li>)}</ol></section>
    </div>

    <div className="culinary-view-actions">
      <button type="button" onClick={onBack} className="culinary-secondary-action"><ArrowLeft size={13}/>Return to previous screen</button>
      <button type="button" disabled={busy} onClick={() => toggleRecipeSelection(recipe.id, !selected)} className="culinary-primary-action">{selected ? 'Remove from plan' : 'Select for plan'}</button>
      <a href={recipe.source_url} target="_blank" rel="noreferrer" className="culinary-link-action"><ExternalLink size={13}/>Source PDF · page {recipe.pdf_page}</a>
    </div>
  </article>;
}
