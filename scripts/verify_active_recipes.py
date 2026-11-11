"""Verify every active recipe through runtime tools and retained source evidence."""
import sys,json,sqlite3,hashlib,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dash_app.core import search_recipes,validate_results,recipe_evidence
from dash_app.dash_screening import screen,check_source_facts

def main():
 c=sqlite3.connect(ROOT/'data/pdf_catalog.sqlite');rows=[json.loads(r[0]) for r in c.execute('SELECT record FROM recipes')];failures=[]
 for r in rows:
  q={'ingredients':[i['name'] for i in r['ingredients']],'servings':2,'diet':'any','match_mode':'all'}
  try:
   matches=[m for m in search_recipes(q) if m['id']==r['id']]
   issues=validate_results(matches,q)
   if len(matches)!=1:issues.append('Recipe not returned for its own full pantry')
   if r.get('dash_screening'):
    if screen(r)['status']!='qualified':issues.append('Screening failed')
    issues+=check_source_facts(r,recipe_evidence(r))
   if issues:failures.append({'title':r['title'],'issues':issues})
  except Exception as e:failures.append({'title':r['title'],'error':str(e)})
 for name,path,digest in c.execute('SELECT name,path,sha256 FROM documents'):
  if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:failures.append({'document':name,'error':'PDF checksum mismatch'})
 c.close();report={'checked':len(rows),'failures':failures,'date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Runtime pantry matching, scaling, numeric/source support and unchanged PDFs; not clinical approval or overall LLM accuracy'}
 (ROOT/'reports/active-recipes-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));return bool(failures)
if __name__=='__main__':sys.exit(main())
