"""PDF ingestion: no embedded recipes or dietary passages."""
import hashlib,json,re,sqlite3,os
from pathlib import Path
from fractions import Fraction
from contextlib import closing
from .core import ROOT
from .providers import load_env,nebius

def normalized(text):
    text=re.sub(r'[\u02da\u00ba](?=\s*[FC]\b)', '\u00b0', str(text or ''))
    text=re.sub(r'\s*([\u2013\u2014])\s*',r'\1',text)
    text=re.sub(r'(?<=[A-Za-z])-\s+(?=[A-Za-z])','-',text)
    return re.sub(r'\s+([.,;:])',r'\1',' '.join(text.split()))

def extract_page_text(page, *, use_text_flow=False):
    """Read upright text; separate a whole number from a smaller raised numerator.

    Uses PDF character geometry, not recipe-specific substitutions. The original
    publication is unchanged. A smaller numerator touching a full-size digit is
    a mixed fraction; an ordinary same-size 11/2 is not silently rewritten.
    """
    import pdfplumber
    chars=[dict(c) for c in page.chars if c.get('upright',True)]
    for i,c in enumerate(chars):
        if not c['text'].isdigit():continue
        previous=chars[i-1] if i else None
        following=chars[i+1] if i+1<len(chars) else None
        if (previous and following and previous['text'].isdigit()
            and following['text']=='/' and c['size']<previous['size']*.8
            and abs(c['x0']-previous['x1'])<2
            and abs(c['top']-previous['top'])<previous['size']*.5):
            c['text']=' '+c['text']
    if use_text_flow:
        return pdfplumber.utils.text.chars_to_textmap(chars,use_text_flow=True,x_tolerance=1,y_tolerance=3).as_string
    return pdfplumber.utils.extract_text(chars,y_tolerance=5) or ''

def quantity(text):
    if text is None:return None
    import unicodedata
    parts=[]
    for char in str(text).strip():
        if 'VULGAR FRACTION' in unicodedata.name(char,''):
            parts.append(' '+str(Fraction(unicodedata.numeric(char)).limit_denominator(100)))
        else:parts.append(char)
    text=''.join(parts).strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?(?:\s+\d+/\d+|/\d+)?',text):return None
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

def source_nutrients(block):
    # Labels/units are schema, never recipe values. Values come from this recipe's table.
    labels={'calcium_mg':'Calcium','magnesium_mg':'Magnesium','potassium_mg':'Potassium','sodium_mg':'Sodium','calories_kcal':'Calories','fiber_g':'Fiber','protein_g':'Protein','total_fat_g':'Total Fat','saturated_fat_g':'Saturated Fat','carbohydrate_g':'Carbohydrate'}
    table=block.split('Makes ',1)[-1];result={}
    for key,label in labels.items():
        m=re.search(r'\b'+re.escape(label)+r'\s+(<?\d+(?:\.\d+)?)\s*'+('mg' if key.endswith('_mg') else ('g' if key.endswith('_g') else '')),table)
        if m:result[key]={'value':float(m[1].lstrip('<')),'qualifier':'less_than' if m[1].startswith('<') else 'equal','evidence':m[0]}
    return result

def source_steps(block):
    if 'Makes ' not in block:return []
    method=block.split('Makes ',1)[0]
    matches=list(re.finditer(r'(?m)^\s*(\d+)\.\s+',method))
    if not matches or [int(m[1]) for m in matches]!=list(range(1,len(matches)+1)):return []
    return [normalized(method[m.end():matches[i+1].start() if i+1<len(matches) else len(method)]) for i,m in enumerate(matches)]

def recipe_block(text,title):
    lines=text.splitlines()
    start=next((i for i,line in enumerate(lines) if normalized(line)==normalized(title)),None)
    if start is None:return text
    end=next((i for i in range(start+1,len(lines)) if re.fullmatch(r'Day\s+\d+',lines[i].strip())),len(lines))
    return '\n'.join(lines[start:end])

def validate_recipe(raw,text,source):
    block=recipe_block(text,raw.get('title','')) if isinstance(raw,dict) else text
    exact_steps=source_steps(block)
    text=normalized(block)
    def anchored(v):return bool(normalized(v)) and normalized(v) in text
    if not isinstance(raw,dict) or not anchored(raw.get('title')):raise ValueError('Title absent from PDF page')
    ingredients=[]
    for item in raw.get('ingredients',[]):
        evidence=item.get('evidence');name=normalized(item.get('name')).lower()
        if not name or not anchored(evidence):raise ValueError('Ingredient lacks verbatim PDF evidence')
        amount=item.get('quantity_text');unit=item.get('unit') or ''
        if amount is not None and normalized(amount) not in normalized(evidence):raise ValueError('Amount absent from ingredient evidence')
        if unit and unit.lower() not in normalized(evidence).lower():raise ValueError('Unit absent from ingredient evidence')
        # Source description keeps preparation details that the LLM may omit.
        description=normalized(evidence)
        prefix=normalized(str(amount or '')+' '+unit)
        if prefix and description.lower().startswith(prefix.lower()):
            name=description[len(prefix):].strip().replace('*','').lower() or name
        ingredients.append({'name':name,'quantity':quantity(amount),'unit':unit,'evidence':normalized(evidence)})
    if not ingredients:raise ValueError('No source-backed ingredients')
    steps=exact_steps or raw.get('steps',[])
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
    return {'id':rid,'title':title,'source_id':source['id'],'document_id':source['document_id'],'source_file':source['source_file'],'pdf_page':source['page'],'printed_page':None,'source_version':source['sha256'][:12],'source_sha256':source['sha256'],'source_url':'/source/'+source['document_id']+'.pdf#page='+str(source['page']),'base_servings':servings,'sodium_mg_per_serving':sodium,'calories_per_serving':calories,'vegetarian':veg,'vegetarian_reason':raw.get('vegetarian_reason',''),'meal_type':raw.get('meal_type') or 'recipe','ingredients':ingredients,'steps':[normalized(x) for x in steps],'flags':flags,'review_method':'LLM extraction with verbatim evidence checks; human review not completed','field_evidence':{k:raw.get(k+'_evidence') for k in ('servings','sodium','calories')},'nutrition_per_serving':source_nutrients(block),'quantities_complete':servings is not None and all(i['quantity'] is not None for i in ingredients)}

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
    import pdfplumber
    from concurrent.futures import ThreadPoolExecutor,as_completed
    pages=[];failures=[]
    with closing(sqlite3.connect(database)) as conn:
        schema(conn)
        paths=sorted(Path(folder).glob('*.pdf'))
        if not paths:raise ValueError('No PDFs found; refusing to replace the catalog with an empty source folder')
        active={'doc-'+hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in paths}
        for (old_id,) in conn.execute('SELECT id FROM documents').fetchall():
            if old_id not in active and not conn.execute('SELECT value FROM metadata WHERE key=?',('candidate_document_'+old_id,)).fetchone():
                old_recipes=[r[0] for r in conn.execute("SELECT id FROM recipes WHERE json_extract(record,'$.document_id')=?",(old_id,))]
                for rid in old_recipes:
                    conn.execute('DELETE FROM ingredients WHERE recipe_id=?',(rid,));conn.execute('DELETE FROM recipes WHERE id=?',(rid,))
                conn.execute('DELETE FROM chunks WHERE page_id IN (SELECT id FROM pages WHERE document_id=?)',(old_id,))
                conn.execute('DELETE FROM extraction_pages WHERE page_id IN (SELECT id FROM pages WHERE document_id=?)',(old_id,))
                conn.execute('DELETE FROM pages WHERE document_id=?',(old_id,));conn.execute('DELETE FROM documents WHERE id=?',(old_id,))
        for path in paths:
            digest=hashlib.sha256(path.read_bytes()).hexdigest();doc='doc-'+digest[:16]
            conn.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?,?)',(doc,path.name,str(path.resolve()),digest))
            reader=pdfplumber.open(path)
            for number,page in enumerate(reader.pages,1):
                text=extract_page_text(page);pid=doc+'-p'+str(number)
                source={'id':pid,'document_id':doc,'source_file':path.name,'sha256':digest,'page':number,'text':text}
                conn.execute('INSERT OR REPLACE INTO pages VALUES (?,?,?,?)',(pid,doc,number,text))
                conn.execute('DELETE FROM chunks WHERE page_id=?',(pid,))
                # Page-aware chunks; source IDs and page numbers are derived from actual PDFs.
                for n,start in enumerate(range(0,len(text),1050)):
                    conn.execute('INSERT OR REPLACE INTO chunks VALUES (?,?,?)',(pid+'-c'+str(n),pid,text[start:start+1200]))
                done=conn.execute('SELECT status FROM extraction_pages WHERE page_id=?',(pid,)).fetchone()
                if text and (not done or done[0]!='complete'):pages.append(source)
            reader.close()
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
