import json
import math
import re
import sqlite3
import hashlib
import threading
from contextlib import closing
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DB=DATA/'pdf_catalog.sqlite'
IMPORT_LOCK=threading.RLock()



def canonical(value):
    s=re.sub(r'\s+',' ',str(value).strip().lower())
    return s


def ensure_current():
    if not DB.is_file():raise RuntimeError('PDF catalog is not built. Run scripts/ingest_pdfs.py first.')
    with closing(sqlite3.connect(DB)) as c:
        row=c.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if not row or row[0]!='pdf-v1':raise RuntimeError('Catalog is not PDF-ingested; refusing legacy data')

def list_documents():
    ensure_current()
    with closing(sqlite3.connect(DB)) as c:
        return [dict(zip(('id','name','sha256','pages'),r)) for r in c.execute('SELECT d.id,d.name,d.sha256,count(p.id) FROM documents d LEFT JOIN pages p ON p.document_id=d.id GROUP BY d.id ORDER BY d.name')]

def read_pdf_page(page_id):
    ensure_current()
    with closing(sqlite3.connect(DB)) as c:
        row=c.execute('SELECT p.id,p.document_id,p.page,p.text,d.name,d.path,d.sha256 FROM pages p JOIN documents d ON d.id=p.document_id WHERE p.id=?',(page_id,)).fetchone()
    if not row:raise ValueError('Unknown PDF page ID')
    result=dict(zip(('id','document_id','pdf_page','text','source_file','path','sha256'),row))
    result['source_url']='/source/'+result['document_id']+'.pdf#page='+str(result['pdf_page'])
    return result

def document_path(document_id):
    ensure_current()
    with closing(sqlite3.connect(DB)) as c:
        row=c.execute('SELECT path,sha256 FROM documents WHERE id=?',(document_id,)).fetchone()
    if not row:raise ValueError('Unknown PDF document')
    path=Path(row[0])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row[1]:raise ValueError('PDF changed or unavailable; re-ingest before serving citations')
    return path


def all_recipes():
    ensure_current()
    with closing(sqlite3.connect(DB)) as c:
        return [json.loads(row[0]) for row in c.execute('SELECT record FROM recipes ORDER BY id')]


def get_recipe_details(recipe_id):
    ensure_current()
    with closing(sqlite3.connect(DB)) as c:
        row=c.execute('SELECT record FROM recipes WHERE id=?',(recipe_id,)).fetchone()
    if not row: raise ValueError('Unknown recipe ID')
    return json.loads(row[0])


def ingredient_match(recipe, pantry):
    required={canonical(i['name']) for i in recipe['ingredients']}
    available={canonical(p) for p in pantry}
    matched=sorted(required & available); missing=sorted(required-available)
    return {'matched':matched,'missing':missing,'matched_count':len(matched),'required_count':len(required),
            'match_percent':round(100*len(matched)/len(required),2) if required else None}


def scale_recipe(recipe, servings):
    if isinstance(servings,bool) or not isinstance(servings,(int,float)) or not math.isfinite(servings) or not 1<=servings<=50:
        raise ValueError('Servings must be between 1 and 50')
    factor=servings/recipe['base_servings'] if recipe['base_servings'] else None
    return [{**i,'quantity':round(i['quantity']*factor,4) if i['quantity'] is not None and factor is not None else None} for i in recipe['ingredients']]


def validate_request(payload):
    if not isinstance(payload,dict): raise ValueError('Expected a request object')
    ingredients=payload.get('ingredients',[])
    if not isinstance(ingredients,list) or any(not isinstance(x,str) for x in ingredients): raise ValueError('Ingredients must be a list of names')
    if not ingredients or not any(x.strip() for x in ingredients): raise ValueError('Choose at least one ingredient')
    if len(ingredients)>100 or any(len(x)>100 for x in ingredients): raise ValueError('Too many or overly long ingredients')
    servings=payload.get('servings',2)
    if isinstance(servings,bool) or not isinstance(servings,(int,float)) or not math.isfinite(servings) or not float(servings).is_integer() or not 1<=servings<=50: raise ValueError('Choose between 1 and 50 whole servings.')
    diet=payload.get('diet','any')
    if diet not in ('any','vegetarian'): raise ValueError('Unknown diet choice')
    exclusions=payload.get('exclusions',[])
    if not isinstance(exclusions,list) or len(exclusions)>100 or any(not isinstance(x,str) or len(x)>100 for x in exclusions): raise ValueError('Invalid exclusions')
    mode=payload.get('match_mode','some')
    if mode not in ('some','all'): raise ValueError('Invalid match mode')
    sodium=payload.get('max_sodium_mg')
    if sodium is not None and (isinstance(sodium,bool) or not isinstance(sodium,(int,float)) or not math.isfinite(sodium) or not 0<=sodium<=3000): raise ValueError('Invalid sodium limit')
    return {'ingredients':sorted({canonical(x) for x in ingredients if x.strip()}),
            'servings':servings,'diet':diet,'exclusions':sorted({canonical(x) for x in exclusions}),
            'match_mode':mode,'max_sodium_mg':sodium}


def preparation_complete(recipe):
    def positive(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0
    return (positive(recipe.get('base_servings')) and bool(recipe.get('steps'))
            and all(isinstance(step,str) and step.strip() for step in recipe['steps'])
            and bool(recipe.get('ingredients'))
            and all(positive(i.get('quantity')) for i in recipe['ingredients']))


def search_recipes(request):
    q=validate_request(request)
    results=[]
    ensure_current()
    # SQL filters the source-backed catalog, independently of vector top-k results.
    sql='SELECT record FROM recipes WHERE 1=1';params=[]
    if q['diet']=='vegetarian':sql+=' AND vegetarian=1'
    if q['max_sodium_mg'] is not None:sql+=' AND sodium IS NOT NULL AND sodium<=?';params.append(q['max_sodium_mg'])
    sql+=' AND EXISTS (SELECT 1 FROM ingredients i WHERE i.recipe_id=recipes.id AND i.name IN ('+','.join('?' for _ in q['ingredients'])+'))';params.extend(q['ingredients'])
    if q['exclusions']:
        sql+=' AND NOT EXISTS (SELECT 1 FROM ingredients i WHERE i.recipe_id=recipes.id AND i.name IN ('+','.join('?' for _ in q['exclusions'])+'))';params.extend(q['exclusions'])
    with closing(sqlite3.connect(DB)) as c:rows=[json.loads(row[0]) for row in c.execute(sql,params)]
    for r in rows:
        if not preparation_complete(r):continue
        if q['diet']=='vegetarian' and r['vegetarian'] is not True: continue
        names={canonical(i['name']) for i in r['ingredients']}
        if names & set(q['exclusions']): continue
        if q['max_sodium_mg'] is not None and (r['sodium_mg_per_serving'] is None or r['sodium_mg_per_serving']>q['max_sodium_mg']): continue
        m=ingredient_match(r,q['ingredients'])
        if m['matched_count']==0: continue
        if q['match_mode']=='all' and m['missing']: continue
        results.append({**r,**m,'requested_servings':q['servings'],
                       'scaled_ingredients':scale_recipe(r,q['servings']),
                       'batch_sodium_mg':round(r['sodium_mg_per_serving']*q['servings'],2) if r['sodium_mg_per_serving'] is not None else None,
                       'quantity_sufficiency':'not_assessed_without_pantry_amounts'})
    return sorted(results,key=lambda r:(-r['match_percent'],r['id']))


def validate_results(results,request):
    """Recheck canonical facts; valid IDs alone do not establish factual support."""
    q=validate_request(request); issues=[]
    def normalized(text):return ' '.join(str(text).split())
    for r in results:
        original=get_recipe_details(r['id'])
        if not preparation_complete(original):issues.append('Recipe lacks complete preparation details')
        for field in ['source_id','pdf_page','source_version','sodium_mg_per_serving','base_servings','steps']:
            if r[field]!=original[field]: issues.append(f"{r['id']}: unsupported {field}")
        evidence=read_pdf_page(original['source_id'])['text']
        if normalized(original['title']) not in normalized(evidence):issues.append('Recipe title lacks PDF evidence')
        for i in original['ingredients']:
            if not i.get('evidence') or normalized(i['evidence']) not in normalized(evidence):issues.append('Ingredient lacks PDF evidence')
        for step in original['steps']:
            if normalized(step) not in normalized(evidence):issues.append('Cooking step lacks PDF evidence')
        if r['ingredients']!=original['ingredients']:issues.append('Changed source ingredients')
        if q['diet']=='vegetarian' and original['vegetarian'] is not True: issues.append('dietary violation')
        if {i['name'] for i in original['ingredients']} & set(q['exclusions']): issues.append('excluded ingredient')
        if r['scaled_ingredients']!=scale_recipe(original,q['servings']): issues.append('scaling mismatch')
        if r['match_percent']!=ingredient_match(original,q['ingredients'])['match_percent']: issues.append('percentage mismatch')
        if r['batch_sodium_mg']!=(round(original['sodium_mg_per_serving']*q['servings'],2) if original['sodium_mg_per_serving'] is not None else None): issues.append('nutrition arithmetic mismatch')
    return issues
