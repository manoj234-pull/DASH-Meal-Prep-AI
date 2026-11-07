"""PDF ingestion: no embedded recipes or dietary passages."""
import hashlib,json,re,sqlite3,os
from pathlib import Path
from fractions import Fraction
from contextlib import closing
from .core import ROOT
from .providers import load_env,nebius

def normalized(text):return re.sub(r'\s+([.,;:])',r'\1',' '.join(str(text or '').split()))
def quantity(text):
    if text is None:return None
    text=str(text).strip().replace('½',' 1/2').replace('¼',' 1/4').replace('¾',' 3/4')
    if not re.fullmatch(r'\d+(?:\.\d+)?(?:\s+\d+/\d+|/\d+)?',text.strip()):return None
    try:return float(sum(Fraction(p) for p in text.split()))
    except (ValueError,ZeroDivisionError):return None

def schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,name TEXT,path TEXT,sha256 TEXT);
    CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY,document_id TEXT,page INTEGER,text TEXT);
    CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,page_id TEXT,text TEXT);
    CREATE TABLE IF NOT EXISTS recipes(id TEXT PRIMARY KEY,title TEXT,vegetarian INTEGER,meal_type TEXT,sodium REAL,record TEXT);
    CREATE TABLE IF NOT EXISTS ingredients(recipe_id TEXT,name TEXT,quantity REAL,unit TEXT);
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE IF NOT EXISTS extraction_pages(page_id TEXT PRIMARY KEY,status TEXT,detail TEXT);
    """)

def validate_recipe(raw,text,source):
    text=normalized(text)
    def anchored(v):return bool(normalized(v)) and normalized(v) in text
    if not isinstance(raw,dict) or not anchored(raw.get('title')):raise ValueError('Title absent from PDF page')
    ingredients=[]
    for item in raw.get('ingredients',[]):
        evidence=item.get('evidence');name=normalized(item.get('name')).lower()
        if not name or not anchored(evidence):raise ValueError('Ingredient lacks verbatim PDF evidence')
        amount=item.get('quantity_text');unit=item.get('unit') or ''
        if amount is not None and normalized(amount) not in normalized(evidence):raise ValueError('Amount absent from ingredient evidence')
        if unit and unit.lower() not in normalized(evidence).lower():raise ValueError('Unit absent from ingredient evidence')
        ingredients.append({'name':name,'quantity':quantity(amount),'unit':unit,'evidence':normalized(evidence)})
    if not ingredients:raise ValueError('No source-backed ingredients')
    steps=raw.get('steps',[])
    if not isinstance(steps,list) or any(not isinstance(x,str) or not anchored(x) for x in steps):raise ValueError('Cooking instruction absent from PDF page')
    def numeric(key):
        value=raw.get(key+'_text');evidence=raw.get(key+'_evidence')
        if value is None:return None
        if not anchored(evidence) or normalized(value) not in normalized(evidence):
            raw[key+'_evidence']=None
            return None
        return quantity(value)
    servings=numeric('servings');sodium=numeric('sodium');calories=numeric('calories')
    if servings is not None and servings<=0:raise ValueError('Invalid servings')
    veg=raw.get('vegetarian')
    if veg is not None and not isinstance(veg,bool):raise ValueError('Invalid dietary label')
    flags=[]
    if servings is None:flags.append('Source does not provide verified servings; quantities cannot be scaled.')
    if not steps:flags.append('Cooking instructions are missing from this PDF entry.')
    if any(i['quantity'] is None for i in ingredients):flags.append('Some ingredient amounts are missing or could not be parsed.')
    if sodium is None:flags.append('Sodium per serving is not available from the source.')
    flags.append('Automatically extracted from PDF; not independently reviewed by a person.')
    title=normalized(raw['title']);rid='recipe-'+hashlib.sha256((source['id']+title).encode()).hexdigest()[:16]
    return {'id':rid,'title':title,'source_id':source['id'],'document_id':source['document_id'],'source_file':source['source_file'],'pdf_page':source['page'],'printed_page':None,'source_version':source['sha256'][:12],'source_sha256':source['sha256'],'source_url':'/source/'+source['document_id']+'.pdf#page='+str(source['page']),'base_servings':servings,'sodium_mg_per_serving':sodium,'calories_per_serving':calories,'vegetarian':veg,'vegetarian_reason':raw.get('vegetarian_reason',''),'meal_type':raw.get('meal_type') or 'recipe','ingredients':ingredients,'steps':[normalized(x) for x in steps],'flags':flags,'review_method':'LLM extraction with verbatim evidence checks; human review not completed','field_evidence':{k:raw.get(k+'_evidence') for k in ('servings','sodium','calories')},'quantities_complete':servings is not None and all(i['quantity'] is not None for i in ingredients)}

def store_recipe(conn,record):
    conn.execute('INSERT OR REPLACE INTO recipes VALUES (?,?,?,?,?,?)',(record['id'],record['title'],record['vegetarian'],record['meal_type'],record['sodium_mg_per_serving'],json.dumps(record)))
    conn.execute('DELETE FROM ingredients WHERE recipe_id=?',(record['id'],))
    conn.executemany('INSERT INTO ingredients VALUES (?,?,?,?)',[(record['id'],x['name'],x['quantity'],x['unit']) for x in record['ingredients']])

def extract_batch(pages):
    load_env()
    response=nebius('/chat/completions',{'model':os.environ['NEBIUS_MODEL'],'temperature':0,'max_tokens':12000,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':(ROOT/'prompts/extract_recipes_v1.txt').read_text(encoding='utf-8')},{'role':'user','content':json.dumps([{'page_id':p['id'],'text':p['text']} for p in pages])}]})
    if response['choices'][0].get('finish_reason')=='length':raise ValueError('Extraction truncated; batch must be retried')
    data=json.loads(response['choices'][0]['message']['content'])
    if not isinstance(data.get('recipes'),list):raise ValueError('Extraction missing recipe array')
    recipes=data['recipes']
    if not recipes:return []
    review=nebius('/chat/completions',{'model':os.environ['NEBIUS_MODEL'],'temperature':0,'max_tokens':3000,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':(ROOT/'prompts/review_extraction_v1.txt').read_text(encoding='utf-8')},{'role':'user','content':json.dumps({'pages':pages,'candidates':[{'index':i,'recipe':r} for i,r in enumerate(recipes)]})}]})
    accepted=json.loads(review['choices'][0]['message']['content'])['accepted_indices']
    if not isinstance(accepted,list) or any(type(i) is not int or not 0<=i<len(recipes) for i in accepted):raise ValueError('Invalid extraction review')
    return [recipes[i] for i in sorted(set(accepted))]

def ingest(folder,database):
    from pypdf import PdfReader
    from concurrent.futures import ThreadPoolExecutor,as_completed
    pages=[];failures=[]
    with closing(sqlite3.connect(database)) as conn:
        schema(conn)
        paths=sorted(Path(folder).glob('*.pdf'))
        if not paths:raise ValueError('No PDFs found; refusing to replace the catalog with an empty source folder')
        active={'doc-'+hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in paths}
        for (old_id,) in conn.execute('SELECT id FROM documents').fetchall():
            if old_id not in active:
                old_recipes=[r[0] for r in conn.execute("SELECT id FROM recipes WHERE json_extract(record,'$.document_id')=?",(old_id,))]
                for rid in old_recipes:
                    conn.execute('DELETE FROM ingredients WHERE recipe_id=?',(rid,));conn.execute('DELETE FROM recipes WHERE id=?',(rid,))
                conn.execute('DELETE FROM chunks WHERE page_id IN (SELECT id FROM pages WHERE document_id=?)',(old_id,))
                conn.execute('DELETE FROM extraction_pages WHERE page_id IN (SELECT id FROM pages WHERE document_id=?)',(old_id,))
                conn.execute('DELETE FROM pages WHERE document_id=?',(old_id,));conn.execute('DELETE FROM documents WHERE id=?',(old_id,))
        for path in paths:
            digest=hashlib.sha256(path.read_bytes()).hexdigest();doc='doc-'+digest[:16]
            conn.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?,?)',(doc,path.name,str(path.resolve()),digest))
            reader=PdfReader(path)
            for number,page in enumerate(reader.pages,1):
                text=normalized(page.extract_text(extraction_mode='layout') or '')+' '+normalized(page.extract_text() or '');pid=doc+'-p'+str(number)
                source={'id':pid,'document_id':doc,'source_file':path.name,'sha256':digest,'page':number,'text':text}
                conn.execute('INSERT OR REPLACE INTO pages VALUES (?,?,?,?)',(pid,doc,number,text))
                # Page-aware chunks; source IDs and page numbers are derived from actual PDFs.
                for n,start in enumerate(range(0,len(text),1050)):
                    conn.execute('INSERT OR REPLACE INTO chunks VALUES (?,?,?)',(pid+'-c'+str(n),pid,text[start:start+1200]))
                done=conn.execute('SELECT status FROM extraction_pages WHERE page_id=?',(pid,)).fetchone()
                if text and (not done or done[0]!='complete'):pages.append(source)
            conn.commit()
        batches=[pages[i:i+1] for i in range(0,len(pages),1)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(extract_batch,b):b for b in batches}
            for future in as_completed(futures):
                batch=futures[future];lookup={p['id']:p for p in batch}
                try:
                    records=future.result();rejected=[]
                    for raw in records:
                        try:
                            source=lookup[raw['page_id']];store_recipe(conn,validate_recipe(raw,source['text'],source))
                        except (KeyError,TypeError,ValueError) as exc:rejected.append({'title':raw.get('title') if isinstance(raw,dict) else None,'reason':str(exc),'page_id':raw.get('page_id') if isinstance(raw,dict) else None})
                    for page in batch:
                        errors=[r for r in rejected if r['page_id']==page['id'] or r['page_id'] not in lookup]
                        conn.execute('INSERT OR REPLACE INTO extraction_pages VALUES (?,?,?)',(page['id'],'needs_review' if errors else 'complete',json.dumps(errors)))
                    failures.extend(rejected);conn.commit()
                    print('Extracted batch:',batch[0]['source_file'],batch[0]['page'],'recipes',len(records)-len(rejected),'rejected',len(rejected),flush=True)
                except Exception as exc:
                    for page in batch:conn.execute('INSERT OR REPLACE INTO extraction_pages VALUES (?,?,?)',(page['id'],'failed',type(exc).__name__+': '+str(exc)))
                    conn.commit();failures.append({'pages':list(lookup),'error':str(exc)})
                    print('Batch failed:',batch[0]['source_file'],batch[0]['page'],str(exc),flush=True)
        fingerprint=hashlib.sha256(''.join(row[0] for row in conn.execute('SELECT text FROM chunks ORDER BY id')).encode()).hexdigest()
        previous=conn.execute("SELECT value FROM metadata WHERE key='corpus_version'").fetchone()
        if not previous or previous[0]!=fingerprint:conn.execute("DELETE FROM metadata WHERE key IN ('pinecone_namespace','embedding_model')")
        conn.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('corpus_version',fingerprint))
        conn.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('schema_version','pdf-v1'));conn.commit()
        counts={t:conn.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','pages','chunks','recipes')}
        return {**counts,'failures':failures,'extraction_status':dict(conn.execute('SELECT status,count(*) FROM extraction_pages GROUP BY status'))}
