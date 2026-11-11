export type ChatRole = 'user' | 'assistant' | 'tool' | 'system';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface MealContext {
  ingredients: string[];
  servings: number;
  diet: 'any' | 'vegetarian';
  exclusions: string[];
  match_mode: 'some' | 'all';
  max_sodium_mg: number | null;
  minimum_match_percent?: number;
  match_inclusive?: boolean;
}

export interface ScaledIngredient {
  name: string;
  source_description?: string;
  quantity: number | null;
  unit: string;
}

export interface Recipe {
  id: string;
  title: string;
  match_percent: number;
  pantry_match_percent?: number;
  matched_count: number;
  required_count: number;
  matched: string[];
  missing: string[];
  requested_servings: number;
  base_servings: number;
  sodium_mg_per_serving: number | null;
  vegetarian: boolean | null;
  scaled_ingredients: ScaledIngredient[];
  steps: string[];
  source_url: string;
  pdf_page: number;
}

export interface Clarification {
  question: string;
  choices: string[];
}

export interface SearchResult {
  status: string;
  session_id?: string | null;
  question?: Clarification | null;
  count: number;
  total_count?: number;
  recipes: Recipe[];
  warnings?: string[];
  interpretations?: Array<{ ingredient: string; catalog_name: string; kind?: string }>;
  agent_recommended_ids?: string[];
}

export interface PlanEntry {
  day: string;
  meal: string;
  recipe_id: string;
  title: string;
  servings: number;
}

export interface WeeklyPlanData {
  plan_id?: string;
  status?: 'draft' | 'finalized';
  created_utc?: string;
  updated_utc?: string;
  name: string;
  sodium_target_mg: number | null;
  entries: PlanEntry[];
}

export interface GroceryItem {
  name: string;
  quantity_known: boolean;
  quantity: number | null;
  unit: string;
  recipe_ids?: string[];
}

export interface PrepTask {
  title: string;
  source_texts: string[];
}

export interface NutritionDay {
  sodium_mg: number;
  meals_missing_sodium: number;
  selected_target_mg: number | null;
  within_selected_target: boolean | null;
}

export interface NutritionSummary {
  days: Record<string, NutritionDay>;
  scope: string;
}

export interface ChatState {
  session_id: string;
  status: string;
  reply: string | null;
  context: MealContext;
  messages: ChatMessage[];
  result: SearchResult | null;
  plan: WeeklyPlanData | null;
  grocery_list: GroceryItem[];
  prep_timeline: PrepTask[];
  nutrition_summary: NutritionSummary | null;
  saved_plan_id: string | null;
  selected_recipe_ids: string[];
}

export interface SavedPlan extends WeeklyPlanData {
  plan_id: string;
  status: 'draft' | 'finalized';
  created_utc: string;
  updated_utc: string;
  grocery_list?: GroceryItem[];
  prep_timeline?: PrepTask[];
  nutrition_summary?: NutritionSummary | null;
}

export interface Catalog {
  ingredients: string[];
  recipe_count: number;
}

export interface SearchRequest {
  ingredients: string[];
  servings: number;
  diet: 'any' | 'vegetarian';
  match_mode: 'some' | 'all';
  exclusions: string[];
  max_sodium_mg: number | null;
}
