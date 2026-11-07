"""Small REST adapters; credentials stay server-side. No silent cloud fallback."""
import json
import time
from contextvars import ContextVar
from contextlib import closing
HTTP_DEADLINE=ContextVar("dash_http_deadline",default=None)
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]


def load_env():
    path=ROOT/'.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line: continue
            name,value=line.split('=',1)
            os.environ.setdefault(name.strip(),value.strip().strip('"').strip("'"))


def request_json(url,payload,headers=None,method='POST'):
    if not url.startswith('https://'): raise ValueError('Provider endpoints must use HTTPS')
    request=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type':'application/json',**(headers or {})},method=method)
    deadline=HTTP_DEADLINE.get()
    remaining=deadline-time.monotonic() if deadline is not None else 30
    if remaining<=0: raise RuntimeError('Request time budget exhausted')
    try:
        with urllib.request.urlopen(request,timeout=min(30,remaining)) as response: return json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Provider returned HTTP {e.code}; check credentials, model and index configuration') from None
    except (urllib.error.URLError,TimeoutError):
        raise RuntimeError('Provider connection failed or timed out') from None


def status():
    load_env()
    names=['NEBIUS_API_KEY','NEBIUS_MODEL','NEBIUS_EMBEDDING_MODEL','PINECONE_API_KEY','PINECONE_INDEX_HOST']
    return {'mode':'pdf-backed-agent','missing_configuration':[n for n in names if not os.getenv(n)],
            'langsmith_configured':bool(os.getenv('LANGSMITH_API_KEY')),
            'live_integrations_verified':False}


def nebius(path,payload):
    load_env()
    if not os.getenv('NEBIUS_API_KEY'): raise RuntimeError('NEBIUS_API_KEY is not configured')
    return request_json(os.getenv('NEBIUS_BASE_URL','https://api.tokenfactory.nebius.com/v1').rstrip('/')+path,
        payload,{'Authorization':'Bearer '+os.environ['NEBIUS_API_KEY']})


def embed(texts):
    model=os.getenv('NEBIUS_EMBEDDING_MODEL')
    if not model: raise RuntimeError('NEBIUS_EMBEDDING_MODEL is not configured')
    response=nebius('/embeddings',{'model':model,'input':texts})
    rows=sorted(response['data'],key=lambda d:d['index'])
    if len(rows)!=len(texts): raise RuntimeError('Embedding provider returned incorrect record count')
    return [r['embedding'] for r in rows]


def pinecone(path,payload):
    host=os.getenv('PINECONE_INDEX_HOST','').rstrip('/')
    if not host or not os.getenv('PINECONE_API_KEY'): raise RuntimeError('Pinecone credentials/index host missing')
    if not host.startswith('https://'): host='https://'+host
    return request_json(host+path,payload,{'Api-Key':os.environ['PINECONE_API_KEY'],
       'X-Pinecone-API-Version':os.getenv('PINECONE_API_VERSION','2025-10')})


def index_guidance():
    from . import core
    import sqlite3,hashlib
    load_env();core.ensure_current()
    with closing(sqlite3.connect(core.DB)) as c,c:
        version=c.execute("SELECT value FROM metadata WHERE key='corpus_version'").fetchone()[0]
        # Namespace is dedicated to this content version and never overwrites another project's vectors.
        namespace='dash-pdf-'+version[:16]
        rows=c.execute('SELECT ch.id,ch.text,p.id,p.document_id,p.page,d.name,d.sha256 FROM chunks ch JOIN pages p ON p.id=ch.page_id JOIN documents d ON d.id=p.document_id ORDER BY ch.id').fetchall()
        from concurrent.futures import ThreadPoolExecutor,as_completed
        c.execute('CREATE TABLE IF NOT EXISTS indexed_chunks(namespace TEXT,model TEXT,chunk_id TEXT,PRIMARY KEY(namespace,model,chunk_id))')
        done={r[0] for r in c.execute('SELECT chunk_id FROM indexed_chunks WHERE namespace=? AND model=?',(namespace,os.environ['NEBIUS_EMBEDDING_MODEL']))}
        pending=[r for r in rows if r[0] not in done];errors=[]
        def upload(batch):
            for attempt in range(3):
                try:
                    vectors=embed([r[1] for r in batch])
                    payload={'namespace':namespace,'vectors':[{'id':r[0],'values':v,'metadata':{'text':r[1],'page_id':r[2],'document_id':r[3],'pdf_page':r[4],'source_file':r[5],'sha256':r[6],'corpus_version':version,'embedding_model':os.environ['NEBIUS_EMBEDDING_MODEL']}} for r,v in zip(batch,vectors)]}
                    pinecone('/vectors/upsert',payload)
                    return batch
                except RuntimeError:
                    if attempt==2:raise
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(upload,pending[i:i+4]) for i in range(0,len(pending),4)]
            for future in as_completed(futures):
                try:
                    batch=future.result()
                    for r in batch:c.execute('INSERT OR REPLACE INTO indexed_chunks VALUES (?,?,?)',(namespace,os.environ['NEBIUS_EMBEDDING_MODEL'],r[0]));done.add(r[0])
                    c.commit();print('Indexed PDF chunks',len(done),'/',len(rows),flush=True)
                except RuntimeError as exc:errors.append(str(exc))
        if errors:raise RuntimeError('Index incomplete; rerun to resume missing chunks. '+errors[0])
        c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('pinecone_namespace',namespace))
        c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('embedding_model',os.environ['NEBIUS_EMBEDDING_MODEL']))
        return {'namespace':namespace,'chunks':len(rows),'corpus_version':version}


def retrieve_guidance(query,k=3):
    from . import core
    import sqlite3
    load_env();core.ensure_current()
    with closing(sqlite3.connect(core.DB)) as c,c:
        metadata=dict(c.execute('SELECT key,value FROM metadata'))
        if not metadata.get('pinecone_namespace'):raise RuntimeError('PDFs have not been indexed in Pinecone')
        if metadata.get('embedding_model')!=os.getenv('NEBIUS_EMBEDDING_MODEL'):raise RuntimeError('Embedding model changed; re-index PDFs')
        result=pinecone('/query',{'namespace':metadata['pinecone_namespace'],'vector':embed([query])[0],'topK':k,'includeMetadata':True,'filter':{'corpus_version':{'$eq':metadata['corpus_version']},'embedding_model':{'$eq':metadata['embedding_model']}}})
        selected=[]
        for hit in result.get('matches',[]):
            m=hit.get('metadata',{});row=c.execute('SELECT text,page_id FROM chunks WHERE id=?',(hit['id'],)).fetchone()
            if not row or row[0]!=m.get('text') or row[1]!=m.get('page_id'):raise RuntimeError('Retrieved PDF passage does not match ingested evidence')
            page=core.read_pdf_page(row[1])
            if m.get('sha256')!=page['sha256'] or m.get('document_id')!=page['document_id'] or m.get('pdf_page')!=page['pdf_page']:raise RuntimeError('Retrieved citation does not match ingested PDF')
            selected.append({'id':hit['id'],'text':m['text'],'source_file':page['source_file'],'pdf_page':page['pdf_page'],'page_id':page['id'],'document_id':page['document_id'],'version':page['sha256'][:12],'source_url':page['source_url'],'retrieval_score':hit.get('score')})
    return selected,'Pinecone search over ingested PDF passages'


def validate_extractive_notes(notes,recipes,passages):
    if not isinstance(notes,list) or len(notes)>len(recipes): raise ValueError('Invalid explanation shape')
    allowed={r['id'] for r in recipes}; sources={p['id']:p for p in passages}; seen=set()
    for n in notes:
        if not isinstance(n,dict) or set(n)!={'recipe_id','guidance_id','quote'}: raise ValueError('Invalid source-note schema')
        if n['recipe_id'] not in allowed or n['recipe_id'] in seen: raise ValueError('Invalid or duplicate recipe reference')
        seen.add(n['recipe_id'])
        source=sources.get(n['guidance_id']); quote=n['quote']
        if not source or not isinstance(quote,str) or not 30<=len(quote)<=600 or quote not in source['text']:
            raise ValueError('Source note is not supported by its cited passage')
    return notes



def trace(inputs,outputs):
    now=datetime.now(timezone.utc).isoformat()
    run={'id':str(uuid4()),'name':'dash-recipe-workflow','run_type':'chain','start_time':now,'end_time':now,
         'inputs':inputs,'outputs':outputs,'session_name':os.getenv('LANGSMITH_PROJECT','dash-prototype')}
    path=ROOT/'reports';path.mkdir(exist_ok=True)
    with (path/'traces.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(run)+'\n')
    if os.getenv('LANGSMITH_API_KEY'):
        headers={'x-api-key':os.environ['LANGSMITH_API_KEY']}
        if os.getenv('LANGSMITH_WORKSPACE_ID'): headers['x-tenant-id']=os.environ['LANGSMITH_WORKSPACE_ID']
        request_json(os.getenv('LANGSMITH_ENDPOINT','https://api.smith.langchain.com').rstrip('/')+'/runs',run,headers)
