import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import test from 'node:test';

const root = fileURLToPath(new URL('..', import.meta.url));
const read = (name) => readFileSync(join(root, name), 'utf8');

test('live integration modules and workspace screens exist', () => {
  for (const name of [
    'api.ts',
    'types.ts',
    'state.tsx',
    'Animated UI/components/culinary/views/GroceryListView.tsx',
    'Animated UI/components/culinary/views/PrepDayView.tsx',
  ]) {
    assert.equal(existsSync(join(root, name)), true, `${name} is required`);
  }
});

test('recipe details remain inside the original framed workspace', () => {
  const app = read('Animated UI/components/culinary/CulinaryPlateHub.tsx');
  const modal = read('Animated UI/components/culinary/views/RecipeDetailView.tsx');
  assert.equal(app.includes('backgroundScreen'), true, 'the current workspace must remain behind the recipe');
  assert.equal(modal.includes('culinary-view-recipe'), true, 'recipe details must use the original framed presentation');
  assert.equal(modal.includes('fixed inset-0'), false, 'recipe details must not replace the culinary shell');
  assert.equal(modal.includes('onBack'), true, 'recipe details must return to the previous workspace');
});

test('recipe details follow refreshed serving quantities after a chat update', () => {
  const state = read('state.tsx');
  assert.equal(state.includes('next.result?.recipes.find((recipe) => recipe.id === current.id)'), true,
    'the open recipe must be replaced by its newly scaled result after changing portions');
});

test('reference visual language is applied to live workspaces', () => {
  const source = [
    'App.tsx',
    'RecipeCard.tsx',
    'Animated UI/components/culinary/CulinaryPlateHub.tsx',
    'Animated UI/components/culinary/views/WeeklyPlanView.tsx',
    'Animated UI/components/culinary/views/GroceryListView.tsx',
  ]
    .map(read)
    .join('\n');
  for (const marker of ['Current plan', 'Grocery list', 'rounded-[2rem]', 'bg-cream-200', 'text-[#ea580c]']) {
    assert.equal(source.includes(marker), true, `reference styling marker is required: ${marker}`);
  }
});

test('navigation preserves all implemented meal prep workspaces', () => {
  const source = [
    'Animated UI/components/culinary/CulinaryPlateHub.tsx',
    'Animated UI/components/culinary/DimensionalPlate.tsx',
    'Animated UI/components/culinary/views/DiningTableView.tsx',
  ].map(read).join('\n');
  for (const label of ['Plan with AI', 'Weekly plan', 'Grocery list', 'Prep timeline']) {
    assert.equal(source.includes(label), true, `${label} navigation is required`);
  }
});

test('react client uses the existing chat search and catalog APIs', () => {
  const source = read('api.ts');
  for (const endpoint of ['/api/catalog', '/api/search', '/api/chat', '/api/chat/reset']) {
    assert.equal(source.includes(endpoint), true, `${endpoint} is required`);
  }
});

test('development and preview servers both forward app data requests', () => {
  const source = read('vite.config.ts');
  assert.equal(source.includes('server:'), true, 'development proxy is required');
  assert.equal(source.includes('preview:'), true, 'preview proxy is required');
  assert.equal((source.match(/127\.0\.0\.1:8770/g) || []).length >= 4, true,
    'both servers must forward /api and /source requests');
});

test('plan history and recipe selection use live backend endpoints', () => {
  const api = read('api.ts');
  const state = read('state.tsx');
  assert.equal(existsSync(join(root, 'Animated UI/components/culinary/views/PlanHistoryView.tsx')), true, 'plan history screen is required');
  for (const endpoint of ['/api/plans', '/api/chat/select', '/api/chat/open-plan']) {
    assert.equal(api.includes(endpoint), true, `${endpoint} is required`);
  }
  for (const action of ['toggleRecipeSelection', 'openPlan', 'duplicatePlan', 'deletePlan']) {
    assert.equal(state.includes(action), true, `${action} state action is required`);
  }
});

test('professional workspaces expose every live planning surface', () => {
  const source = [
    'Animated UI/components/culinary/CulinaryPlateHub.tsx',
    'Animated UI/components/culinary/views/PlanWithAIView.tsx',
    'Animated UI/components/culinary/views/WeeklyPlanView.tsx',
    'Animated UI/components/culinary/views/GroceryListView.tsx',
    'Animated UI/components/culinary/views/PrepDayView.tsx',
  ].map(read).join('\n');
  for (const marker of ['Plan with AI', 'No weekly plan yet', 'Grocery list', 'Generate prep timeline', 'Current plan']) {
    assert.equal(source.includes(marker), true, `live workspace marker is required: ${marker}`);
  }
});

test('recipe cards require explicit user selection', () => {
  const card = read('RecipeCard.tsx');
  for (const marker of ['Select for plan', 'Selected', 'onToggleSelection']) {
    assert.equal(card.includes(marker), true, `${marker} is required`);
  }
});

test('empty workspaces explain missing data without silent navigation', () => {
  const weekly = read('Animated UI/components/culinary/views/WeeklyPlanView.tsx');
  const grocery = read('Animated UI/components/culinary/views/GroceryListView.tsx');
  const prep = read('Animated UI/components/culinary/views/PrepDayView.tsx');
  assert.equal(weekly.includes('No weekly plan yet'), true);
  assert.equal(grocery.includes('Your list is waiting for a plan'), true);
  assert.equal(prep.includes('Choose recipes first'), true);
});

test('home screen tolerates sessions saved before grocery and prep fields existed', () => {
  const home = read('Animated UI/components/culinary/views/DiningTableView.tsx');
  assert.equal(home.includes('chat?.grocery_list?.length'), true,
    'legacy chat sessions may not contain grocery_list');
  assert.equal(home.includes('chat?.prep_timeline?.length'), true,
    'legacy chat sessions may not contain prep_timeline');
});

test('animated plate design is the live app shell and uses live application data', () => {
  const app = read('App.tsx');
  const animatedFiles = [
    'Animated UI/components/culinary/CulinaryPlateHub.tsx',
    'Animated UI/components/culinary/DimensionalPlate.tsx',
    'Animated UI/components/culinary/views/DiningTableView.tsx',
    'Animated UI/components/culinary/views/PlanWithAIView.tsx',
    'Animated UI/components/culinary/views/RecipeDetailView.tsx',
    'Animated UI/components/culinary/views/WeeklyPlanView.tsx',
  ];
  const source = animatedFiles.map(read).join('\n');

  assert.equal(app.includes("./Animated UI/components/culinary/CulinaryPlateHub"), true,
    'the supplied animated design must be the live application shell');
  for (const liveBoundary of ['useAppState', 'chat?.plan', 'chat?.result', 'grocery_list', 'prep_timeline']) {
    assert.equal(source.includes(liveBoundary), true, `live application data is required: ${liveBoundary}`);
  }
});

test('animated design expands on desktop and retains its mobile switch', () => {
  const hub = read('Animated UI/components/culinary/CulinaryPlateHub.tsx');
  const controls = read('Animated UI/components/culinary/AudioControls.tsx');
  const styles = read('index.css');
  assert.equal(styles.includes('.culinary-mode-desktop'), true, 'desktop layout must use the supplied wide workspace');
  assert.equal(styles.includes('.culinary-mode-mobile'), true, 'mobile preview must remain available');
  assert.equal(controls.includes("value: 'desktop'"), true, 'desktop view switch must remain wired');
  assert.equal(controls.includes("value: 'mobile'"), true, 'mobile view switch must remain wired');
  assert.equal(hub.includes('data-device-mode={viewportMode}'), true, 'the selected mode must reach the live workspace');
});

test('tailwind compiles every class used by the Animated UI folder', () => {
  const config = read('tailwind.config.js');
  assert.equal(config.includes("./Animated UI/**/*.{js,ts,jsx,tsx,mdx}"), true,
    'Animated UI must be included in Tailwind content scanning');
});

test('plate navigation follows the recorded chef orbit transition', () => {
  const transition = read('Animated UI/components/culinary/VortexTransition.tsx');
  const hub = read('Animated UI/components/culinary/CulinaryPlateHub.tsx');
  for (const marker of ['chefOrbitFlip', 'foodOrbitInward', 'segmentedRingExpand', 'transition-banner', 'VORTEX_ITEMS', '🍋', '🥑', '🥦', '🍅', '🥕', '🧄', '👨‍🍳', 'activeBladeName']) {
    assert.equal(transition.includes(marker), true, `chef transition marker is required: ${marker}`);
  }
  assert.equal(transition.includes('backdrop-blur-[3px]'), true,
    'the selected plate must remain visible behind the transition');
  assert.equal((transition.match(/culinary-vortex-ring/g) ?? []).length >= 3, true,
    'the transition needs multiple expanding segmented rings');
  assert.equal(transition.includes('Preparing your workspace'), false,
    'the recorded transition uses the rotating banner instead of a separate status block');
  assert.equal(hub.includes('transitionTarget'), true, 'the clicked meal-prep space must be named in the transition');
  assert.equal(hub.includes('1100'), true, 'the full supplied transition must remain visible before navigation completes');
});

test('an expired conversation restores the saved plan before Prep generation', () => {
  const state = read('state.tsx');
  assert.equal(state.includes('restorePlanAfterExpiredChat'), true,
    'saved-plan recovery helper is required');
  assert.equal(state.includes('openSavedPlan(null, planId)'), true,
    'expired chat must reopen the saved plan in a fresh conversation');
});

test('live shell preserves the original culinary frame and responsive presentation', () => {
  const hub = read('Animated UI/components/culinary/CulinaryPlateHub.tsx');
  const plate = read('Animated UI/components/culinary/DimensionalPlate.tsx');
  for (const marker of [
    'data-culinary-shell',
    'data-workspace-frame',
    'data-device-mode',
    'culinary-device-notch',
    'culinary-shell-footer',
  ]) {
    assert.equal(hub.includes(marker), true, `original culinary frame marker is required: ${marker}`);
  }
  assert.equal(plate.includes('data-plate-hub'), true, 'the four-quadrant plate must remain the visual home');
  assert.equal(plate.includes('culinary-cutlery'), true, 'desktop plate must retain its place-setting treatment');
});

test('desktop plate gives its labels room and keeps the place setting visible', () => {
  const plate = read('Animated UI/components/culinary/DimensionalPlate.tsx');
  const styles = read('index.css');
  assert.equal(plate.includes('data-plate-mode={viewportMode}'), true,
    'the plate must expose the selected display mode');
  assert.equal(styles.includes('width: min(460px,82vw)'), true,
    'the desktop plate must be large enough for its four labels');
  assert.equal(styles.includes('[data-plate-mode="auto"] .culinary-cutlery'), true,
    'only responsive narrow mode may hide the place setting');
  assert.equal(styles.includes('max-width: 136px'), true,
    'quadrant details need enough width to remain readable');
});
