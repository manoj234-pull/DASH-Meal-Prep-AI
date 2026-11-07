"""Run deterministic controller checks; --live opts into a small provider smoke suite."""
import sys,json,unittest,io,argparse
from pathlib import Path
from datetime import datetime,timezone
from html import escape
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dash_app.agent import run_agent,SessionStore

class Capture(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.rows=[]
    def addSuccess(self,t):super().addSuccess(t);self.rows.append({'name':t.id().split('.')[-1],'passed':True})
    def addFailure(self,t,e):super().addFailure(t,e);self.rows.append({'name':t.id().split('.')[-1],'passed':False})
    def addError(self,t,e):super().addError(t,e);self.rows.append({'name':t.id().split('.')[-1],'passed':False})

def render(report):
    def rows(items):return ''.join(f"<tr><td>{escape(r['name'])}</td><td>{'PASS' if r['passed'] else 'FAIL'}</td><td>{escape(str(r.get('status','scripted controller check')))}</td></tr>" for r in items)
    offline=report['offline'];live=report.get('live',[])
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>body{{font:14px/1.5 system-ui;color:#18352c;margin:20px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;text-align:left;border-bottom:1px solid #ddd}}.note{{background:#fff5df;padding:12px}}</style></head><body><h2>Agent behavior checks</h2><p>{sum(r['passed'] for r in offline)}/{len(offline)} offline checks passed.</p><p class='note'>Offline checks use scripted model responses. They test tool enforcement, retries, clarification and stopping, not real LLM accuracy. Live checks below are a small smoke suite, not a representative accuracy benchmark.</p><details><summary>Offline checks</summary><table><tr><th>Check</th><th>Result</th><th>Scope</th></tr>{rows(offline)}</table></details><h3>Live provider smoke checks</h3><p>{sum(r['passed'] for r in live)}/{len(live)} passed.</p><table><tr><th>Case</th><th>Result</th><th>Agent outcome</th></tr>{rows(live)}</table><p>Review source-note relevance manually. Missing evidence must stay missing. Original deterministic recipe scores are shown separately.</p><small>Run: {report['timestamp']}</small></body></html>"""

def evaluate(live=False):
    stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
    outcome=unittest.TextTestRunner(stream=stream,resultclass=Capture).run(suite)
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'offline':outcome.rows,'live':[],'scope':'Controller behavior plus optional small live smoke; not full RAG accuracy'}
    print(stream.getvalue(),flush=True)
    if live:
        from dash_app.core import all_recipes,search_recipes,validate_results
        from dash_app.providers import retrieve_guidance
        candidates=[r for r in all_recipes() if r['quantities_complete'] and r['steps']]
        if not candidates:raise RuntimeError('No complete PDF recipe available for integration checks')
        recipe=candidates[0]
        payload={'ingredients':[i['name'] for i in recipe['ingredients']],'match_mode':'all','servings':2}
        result=run_agent(payload,store=SessionStore())
        expected={r['id'] for r in search_recipes(payload)}
        good=result['status']=='completed' and bool(result['recipes']) and {r['id'] for r in result['recipes']}.issubset(expected) and not validate_results(result['recipes'],result['effective_request'])
        report['live'].append({'name':'PDF_catalog_integration','passed':good,'status':result['status'],'result':result})
        print('PDF catalog integration:',result['status'],good,flush=True)
        passages,mode=retrieve_guidance('DASH eating plan sodium vegetables')
        report['live'].append({'name':'Pinecone_PDF_citations','passed':bool(passages) and all(p.get('source_url') for p in passages),'status':mode,'result':{'steps':[],'passages':passages}})
        report['scope']='Scripted controller tests plus live integration consistency against SQLite/PDF evidence. Not independent nutrition accuracy or an end-to-end golden benchmark.'
    p=ROOT/'reports';p.mkdir(exist_ok=True)
    (p/'agent-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (p/'agent-evaluation.html').write_text(render(report),encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');args=p.parse_args()
    r=evaluate(args.live)
    sys.exit(0 if all(x['passed'] for x in r['offline']+r['live']) else 1)
