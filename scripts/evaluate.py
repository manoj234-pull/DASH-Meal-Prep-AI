"""Evaluate fixed gold labels. Metrics are computed, never filled in by a model."""
import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dash_app.core import search_recipes,validate_results,all_recipes
from tests.catalog_fixture import catalog_fixture
from scripts.metrics import selection_metrics
from scripts.dashboard import dashboard


def evaluate(split='all'):
    with catalog_fixture():return evaluate_golden(split)

def evaluate_golden(split='all'):
    dataset=json.loads((ROOT/'data/golden_cases.json').read_text(encoding='utf-8'))
    cases=[c for c in dataset['cases'] if split=='all' or c['split']==split]
    results=[]
    step_logs=[]
    selection_pairs=[]
    excluded_selection=[]
    for case in cases:
        e=case['expected']; errors=[]
        actual={}
        selection_completed=False
        try:
            rows=search_recipes(case['input'])
            if e.get('error'): errors.append('Expected input rejection')
            actual={r['id']:r for r in rows}
            selection_completed=True
            if set(actual)!=set(e['ids']): errors.append(f"Expected {e['ids']}, got {list(actual)}")
            if len(rows)!=e['count']: errors.append('Count/list disagreement')
            for id,percent in e.get('percentages',{}).items():
                if id not in actual or abs(actual[id]['match_percent']-percent)>.005: errors.append(f'{id}: percentage mismatch')
            for id,amounts in e.get('scaled',{}).items():
                ingredients={i['name']:i['quantity'] for i in actual.get(id,{}).get('scaled_ingredients',[])}
                for name,quantity in amounts.items():
                    if ingredients.get(name)!=quantity: errors.append(f'{id}: incorrect {name} quantity')
            for id,sodium in e.get('batch_sodium',{}).items():
                if actual.get(id,{}).get('batch_sodium_mg')!=sodium: errors.append(f'{id}: sodium arithmetic mismatch')
            errors+=validate_results(rows,case['input'])
        except ValueError as exc:
            if not e.get('error'): errors.append(str(exc))
        if not e.get('error'):
            selection_pairs.append((set(e['ids']),set(actual)))
        else:
            excluded_selection.append({'id':case['id'],'reason':'Expected input rejection' if e.get('error') else 'Query execution failed; see case errors'})
        step_logs.append({'case_id':case['id'],'category':case['category'],'steps':[{'step':'read_expected','expected_ids':e['ids'],'expected_rejection':e.get('error',False)},{'step':'run_recipe_tool','completed':selection_completed,'actual_ids':list(actual)},{'step':'compare_and_verify','passed':not errors,'errors':errors}]})
        print(f"[{case['id']}] {case['category']}: expected={e['ids']}, actual={list(actual)}, rejection_expected={e.get('error',False)} -> {'PASS' if not errors else 'FAIL'}")
        results.append({'id':case['id'],'category':case['category'],'expected_behavior':case['expected_behavior'],'split':case['split'],'description':case['description'],'passed':not errors,'errors':errors})
    passed=sum(r['passed'] for r in results)
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'split':split,'evaluated':len(results),'passed':passed,
      'pass_percent':round(100*passed/len(results),2) if results else None,
      'scope':'Frozen synthetic golden catalog only; not the current PDF catalog. Deterministic recipe selection, arithmetic, count/list consistency and source-record checks. Not end-to-end cloud RAG or clinical validation.',
      'golden_review_status':dataset['review_status'],
      'cloud_semantic_retrieval':{'status':'not_run','precision':None,'recall':None},
      'llm_faithfulness':{'status':'not_run','score':None},
      'recipes_sha256':hashlib.sha256((ROOT/'tests/fixtures/golden_recipes.json').read_bytes()).hexdigest(),
      'golden_sha256':hashlib.sha256((ROOT/'data/golden_cases.json').read_bytes()).hexdigest(),
      'cases':results}
    labels=[r['id'] for r in json.loads((ROOT/'tests/fixtures/golden_recipes.json').read_text(encoding='utf-8'))]
    report['recipe_selection_metrics']=selection_metrics(selection_pairs,labels)
    report['recipe_selection_metrics']['excluded_cases']=excluded_selection
    report['step_logs']=step_logs
    report['by_category'] = {}
    for category in sorted({r['category'] for r in results}):
        group = [r for r in results if r['category']==category]
        n = sum(r['passed'] for r in group)
        report['by_category'][category] = {'passed':n,'failed':len(group)-n,'evaluated':len(group),'pass_percent':round(100*n/len(group),2)}
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports'/f'evaluation-{split}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (ROOT/'reports'/f'evaluation-{split}.html').write_text(dashboard(report),encoding='utf-8')
    (ROOT/'reports'/f'evaluation-steps-{split}.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in step_logs),encoding='utf-8')
    with (ROOT/'reports'/f'metrics-{split}.jsonl').open('a',encoding='utf-8') as log:
        log.write(json.dumps({'timestamp':report['timestamp'],'golden_sha256':report['golden_sha256'],'recipes_sha256':report['recipes_sha256'],'metrics':report['recipe_selection_metrics']})+'\n')
    print(f'{split}: {passed}/{len(results)} cases passed ({report["pass_percent"]}%). Cloud/LLM metrics NOT RUN.')
    for r in results:
        if not r['passed']: print(r['id'],r['errors'])
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['all','development','held_out'],default='development')
    report=evaluate(p.parse_args().split)
    sys.exit(0 if report['passed']==report['evaluated'] else 1)
