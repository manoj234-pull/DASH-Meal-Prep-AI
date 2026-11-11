"""Independent source-shape and arithmetic checks; not clinical approval."""
import json,re,sqlite3,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dash_app.ingestion import normalized,recipe_block,quantity,source_steps

def audit(database=ROOT/'data/pdf_catalog.sqlite'):
    c=sqlite3.connect(database);results=[]
    try:
        for (serialized,) in c.execute('SELECT record FROM recipes'):
            r=json.loads(serialized);issues=[]
            page=c.execute('SELECT text FROM pages WHERE id=?',(r['source_id'],)).fetchone()[0]
            block=recipe_block(page,r['title']);text=normalized(block)
            head=re.split(r'(?m)^\s*1\.\s',block)[0]
            source_amounts=[quantity(m[1]) for m in re.finditer(r'(?m)^\s*(\d+(?:\s+\d+/\d+|/\d+|\.\d+)?)\s+(?!servings)',head)]
            if len(source_amounts)!=len(r['ingredients']):issues.append('Ingredient count differs from source lines')
            elif source_amounts!=[i['quantity'] for i in r['ingredients']]:issues.append('Ingredient amounts differ from source lines')
            for i in r['ingredients']:
                if normalized(i['evidence']) not in text:issues.append('Ingredient evidence missing')
            method=source_steps(block)
            if method and method!=r['steps']:issues.append('Cooking steps differ from source')
            for step in r['steps']:
                if normalized(step) not in text:issues.append('Cooking step not supported')
            for label,key in [('Makes','base_servings'),('Sodium','sodium_mg_per_serving'),('Calories','calories_per_serving')]:
                m=re.search(r'\b'+label+r'\s+(\d+(?:\.\d+)?)',block)
                if not m or float(m[1])!=r[key]:issues.append(label+' differs from source')
            if not r['steps'] or not r['ingredients']:issues.append('Incomplete preparation')
            results.append({'recipe_id':r['id'],'title':r['title'],'page':r['pdf_page'],'checks_passed':not issues,'issues':issues,'vegetarian':r['vegetarian'],'vegetarian_reason':r['vegetarian_reason']})
        docs=[]
        for name,path,digest in c.execute('SELECT name,path,sha256 FROM documents'):
            docs.append({'file':name,'unchanged':hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest})
        report={'recipes_checked':len(results),'passed':sum(r['checks_passed'] for r in results),'recipes':results,'documents':docs,'scope':'Source transcription, amounts, steps, servings, sodium and calories. Not human or clinical certification.'}
        return report
    finally:c.close()
if __name__=='__main__':
    report=audit();(ROOT/'reports').mkdir(exist_ok=True);(ROOT/'reports/recipe-source-audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2));sys.exit(0 if report['passed']==report['recipes_checked'] and all(d['unchanged'] for d in report['documents']) else 1)
