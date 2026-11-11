import { BookOpen, Check, CheckCircle2, ChefHat, Plus, ShoppingBasket } from 'lucide-react';
import type { Recipe } from './types';

interface RecipeCardProps {
  recipe: Recipe;
  onOpen: (recipe: Recipe) => void;
  selected: boolean;
  onToggleSelection: (recipeId: string, selected: boolean) => void;
}

export function RecipeCard({ recipe, onOpen, selected, onToggleSelection }: RecipeCardProps) {
  return (
    <article className="overflow-hidden rounded-[2rem] border border-cream-300 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="relative flex min-h-24 items-end justify-between overflow-hidden bg-gradient-to-br from-walnut-800 to-walnut-600 p-5 text-white">
        <div className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-saffron-500/25 blur-2xl" />
        <div>
          <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-200"><ChefHat size={12} />
            {recipe.vegetarian === true ? 'Vegetarian' : recipe.vegetarian === false ? 'Contains meat or fish' : 'Food preference unconfirmed'}
          </p>
          <h3 className="relative mt-1 text-lg font-bold leading-snug">{recipe.title}</h3>
        </div>
        <div className="relative shrink-0 rounded-2xl bg-white/10 px-3 py-2 text-right backdrop-blur-sm">
          <p className="text-xl font-extrabold text-white">{recipe.match_percent}%</p>
          <p className="text-[10px] text-cream-300">match</p>
        </div>
      </div>

      <div className="p-4"><div className="grid gap-2 text-xs sm:grid-cols-2">
        <div className="rounded-2xl bg-cream-100 p-3">
          <p className="flex items-center gap-1.5 font-bold text-walnut-800"><CheckCircle2 size={14} /> You have</p>
          <p className="mt-1 text-muted-clay">{recipe.matched.length ? recipe.matched.join(', ') : 'No listed ingredients matched'}</p>
        </div>
        <div className="rounded-2xl bg-cream-100 p-3">
          <p className="flex items-center gap-1.5 font-bold text-walnut-800"><ShoppingBasket size={14} /> Still needed</p>
          <p className="mt-1 text-muted-clay">{recipe.missing.length ? recipe.missing.join(', ') : 'All ingredient names are present'}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-clay">
        <span className="rounded-full bg-cream-200 px-2.5 py-1">{recipe.requested_servings} portions</span>
        <span className="rounded-full bg-cream-200 px-2.5 py-1">
          {recipe.sodium_mg_per_serving === null ? 'Sodium unavailable' : `${recipe.sodium_mg_per_serving} mg sodium / source serving`}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2"><button type="button" onClick={() => onOpen(recipe)} className="flex items-center justify-center gap-2 rounded-xl bg-cream-200 px-3 py-2.5 text-xs font-bold"><BookOpen size={14}/>View recipe</button><button type="button" onClick={()=>onToggleSelection(recipe.id,!selected)} className={`flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-xs font-bold ${selected?'bg-walnut-800 text-white':'bg-saffron-500 text-white'}`}>{selected?<><Check size={14}/>Selected</>:<><Plus size={14}/>Select for plan</>}</button></div>
      </div>
    </article>
  );
}
