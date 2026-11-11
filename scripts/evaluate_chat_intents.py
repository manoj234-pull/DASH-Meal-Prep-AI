"""Live conversation evaluation. Requires configured providers; incurs API usage."""
import json,sys,time,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dash_app.chat import run_chat,ChatStore
from dash_app.core import search_recipes
from dash_app.recipe_view import recipe_term_matches

def assess(response,expected):
    errors=[]; context=response['context']; result=response.get('result') or {}; rows=result.get('recipes',[]); view=response.get('result_view',{})
    if response['status']!='completed':
        errors.append('Conversation did not complete')
        return errors
    for key in ('diet','servings','exclusions'):
        if key in expected and context.get(key)!=expected[key]:errors.append('Incorrect remembered '+key)
    if expected.get('empty_pantry') and context['ingredients']:errors.append('Invented pantry')
    if expected.get('no_results') and rows:errors.append('Unexpected recipes')
    if 'plan_entries' in expected and len((response.get('plan') or {}).get('entries',[]))!=expected['plan_entries']:
        errors.append('Weekly plan has the wrong number of entries')
    if expected.get('grocery_nonempty') and not response.get('grocery_list'):
        errors.append('Weekly plan did not produce a grocery list')
    if 'nutrition_days' in expected and len((response.get('nutrition_summary') or {}).get('days',{}))!=expected['nutrition_days']:
        errors.append('Weekly plan nutrition summary has the wrong number of days')
    normalize=lambda text:str(text).casefold().replace('’',"'").replace('‘',"'")
    reply=normalize(response.get('reply',''))
    if 'reply_contains_any' in expected and not any(normalize(term) in reply for term in expected['reply_contains_any']):errors.append('Reply missed the expected boundary or redirect')
    if any(normalize(term) in reply for term in expected.get('reply_excludes',[])):errors.append('Reply repeated or supplied unsafe detail')
    if expected.get('no_clarification') and ('?' in response.get('reply','') or response['status']!='completed'):
        errors.append('Asked an unnecessary clarification or did not complete')
    exact_selection=any(k in expected for k in ('min_match','min_pantry_match','max_sodium','sort','limit','unlimited','recipe_vegetarian'))
    if exact_selection or any(k in expected for k in ('include_ingredients','exclude_ingredients','title_contains')):
        if not rows:errors.append('Expected actual recipe results')
        # Independent expected selection from the base pantry query, not apply_view.
        oracle=search_recipes(context)
        if 'min_match' in expected:
            threshold=expected['min_match'];strict=expected.get('strict',False)
            oracle=[r for r in oracle if r['match_percent']>threshold if strict] if strict else [r for r in oracle if r['match_percent']>=threshold]
        if 'min_pantry_match' in expected:
            threshold=expected['min_pantry_match'];oracle=[r for r in oracle if r['pantry_match_percent']>=threshold]
        if 'include_ingredients' in expected:
            wanted=expected['include_ingredients']
            oracle=[r for r in oracle if all(recipe_term_matches(r,name) for name in wanted)]
            if view.get('include_ingredients')!=wanted:errors.append('Ingredient filter was not saved')
            if any(not all(recipe_term_matches(r,name) for name in wanted) for r in rows):errors.append('Displayed recipe violates recipe-content filter')
        if 'exclude_ingredients' in expected:
            unwanted=expected['exclude_ingredients']
            oracle=[r for r in oracle if not any(recipe_term_matches(r,name) for name in unwanted)]
            if view.get('exclude_ingredients')!=unwanted:errors.append('Ingredient exclusion was not saved')
            if any(any(recipe_term_matches(r,name) for name in unwanted) for r in rows):errors.append('Displayed recipe violates recipe-content exclusion')
        if 'title_contains' in expected:
            wanted=expected['title_contains'];oracle=[r for r in oracle if wanted.casefold() in r['title'].casefold()]
            if view.get('title_contains')!=wanted:errors.append('Recipe-title filter was not saved')
            if any(wanted.casefold() not in r['title'].casefold() for r in rows):errors.append('Displayed recipe violates title filter')
        if 'recipe_vegetarian' in expected:
            wanted=expected['recipe_vegetarian'];oracle=[r for r in oracle if r.get('vegetarian') is wanted]
            saved=any(f.get('field')=='vegetarian' and f.get('operator')=='eq' and f.get('value') is wanted for f in view.get('filters',[]))
            if not saved:errors.append('Vegetarian result filter was not saved')
            if any(r.get('vegetarian') is not wanted for r in rows):errors.append('Displayed recipe violates vegetarian result filter')
        if 'max_sodium' in expected:
            n=expected['max_sodium'];oracle=[r for r in oracle if r['sodium_mg_per_serving'] is not None and (r['sodium_mg_per_serving']<n if expected.get('strict_sodium') else r['sodium_mg_per_serving']<=n)]
        sort=expected.get('sort','pantry_match_percent' if 'min_pantry_match' in expected else 'match_percent');reverse=expected.get('direction','desc')=='desc'
        known=sorted([r for r in oracle if r.get(sort) is not None],key=lambda r:r['id']);known.sort(key=lambda r:r[sort],reverse=reverse)
        oracle=known+sorted([r for r in oracle if r.get(sort) is None],key=lambda r:r['id'])
        if exact_selection:
            if result.get('total_count')!=len(oracle):errors.append('Total count disagrees with expected full match set')
            if expected.get('limit'):oracle=oracle[:expected['limit']]
            if [r['id'] for r in rows]!=[r['id'] for r in oracle]:errors.append('Displayed recipes/order differ from expected selection')
        if 'limit' in expected and view.get('limit')!=expected['limit']:errors.append('Display limit not saved')
        if expected.get('unlimited') and view.get('limit') is not None:errors.append('Display limit not removed')
    forbidden=expected.get('forbidden_ingredient_words',[])
    for row in rows:
        words=set(re.findall(r'[a-z]+',' '.join(i['name'] for i in row.get('ingredients',[])).lower()))
        if words.intersection(forbidden):
            errors.append('Displayed recipe violates an ingredient exclusion: '+row['id'])
    if rows and any(r['requested_servings']!=context['servings'] for r in rows):errors.append('Cards have stale portions')
    return errors

def main():
    root=Path(__file__).resolve().parents[1]
    cases=json.loads((root/'tests/fixtures/chat_intent_cases.json').read_text())['cases'];results=[]
    for case in cases:
        store=ChatStore();token=None;turns=[]
        for turn in case['turns']:
            started=time.monotonic();response=run_chat({'message':turn['message'],'session_id':token},store=store);token=response['session_id']
            errors=assess(response,turn['expect'])
            turns.append({'message':turn['message'],'expected':turn['expect'],'errors':errors,'status':response['status'],'reply':response['reply'],'context':response['context'],'view':response.get('result_view'), 'count':(response.get('result') or {}).get('count'),'latency_ms':round((time.monotonic()-started)*1000)})
            print(case['id'],len(turns),'PASS' if not errors else 'FAIL: '+'; '.join(errors),flush=True)
        results.append({'id':case['id'],'origin':case['origin'],'passed':all(not t['errors'] for t in turns),'turns':turns})
        report={'scope':'Live intent plus result/state checks; no clinical or full factual accuracy claim. Narrative quality needs review.','cases':results,'passed':sum(r['passed'] for r in results),'total':len(results)}
        (root/'reports/chat-intent-live.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Completed',report['passed'],'/',report['total'],flush=True)
if __name__=='__main__':main()
