"""Run with python app.py. Local-only form UI, no extra server dependencies."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
from dash_app.core import ROOT,DATA,all_recipes,document_path,read_pdf_page,list_documents,preparation_complete
from dash_app.providers import status
from dash_app.agent import run_agent
from dash_app.chat import run_chat, STORE as CHAT_STORE, public as chat_public, set_recipe_selection, open_saved_plan
from dash_app.planner import PLAN_DB, list_plans, load_plan, duplicate_plan, rename_plan, delete_plan, save_plan


def plan_api(method,path,payload=None,database=PLAN_DB):
    parts=[part for part in path.split('/') if part]
    if parts==['api','plans'] and method=='GET':return {'plans':list_plans(database=database)}
    if len(parts)<3 or parts[:2]!=['api','plans']:raise ValueError('Saved plan not found')
    plan_id=parts[2]
    if len(parts)==3 and method=='GET':return {'plan':load_plan(plan_id,database=database)}
    if method!='POST' or len(parts)!=4:raise ValueError('Unsupported plan action')
    action=parts[3];payload=payload or {}
    if action=='duplicate':return {'plan':duplicate_plan(plan_id,database=database)}
    if action=='rename':return {'plan':rename_plan(plan_id,payload.get('name'),database=database)}
    if action=='finalize':
        plan=load_plan(plan_id,database=database)
        return {'plan':save_plan(plan,'finalized',database=database)}
    if action=='delete':delete_plan(plan_id,database=database);return {'deleted':True}
    raise ValueError('Unsupported plan action')


def static_response(root, request_path):
    """Return (bytes, content type) for the React build or the legacy UI fallback."""
    react_root=(root/'UI'/'dist').resolve()
    react_index=react_root/'index.html'
    if react_index.exists():
        relative=request_path.lstrip('/') or 'index.html'
        candidate=(react_root/relative).resolve()
        if candidate.is_relative_to(react_root) and candidate.is_file():
            content_type=mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
            if content_type.startswith('text/') or content_type in ('application/javascript','application/json'):
                content_type+='; charset=utf-8'
            return candidate.read_bytes(),content_type
        return react_index.read_bytes(),'text/html; charset=utf-8'
    legacy_root=(root/'web').resolve()
    relative=request_path.lstrip('/') or 'index.html'
    candidate=(legacy_root/relative).resolve()
    if candidate.is_relative_to(legacy_root) and candidate.is_file():
        content_type=mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
        if content_type.startswith('text/') or content_type in ('application/javascript','application/json'):
            content_type+='; charset=utf-8'
        return candidate.read_bytes(),content_type
    return None


class Handler(BaseHTTPRequestHandler):
    def send(self,code,body,content_type='application/json; charset=utf-8'):
        if not isinstance(body,bytes): body=json.dumps(body).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)

    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/plans' or path.startswith('/api/plans/'):
            try:return self.send(200,plan_api('GET',path))
            except ValueError as exc:return self.send(404,{'error':str(exc)})
        if path.startswith('/api/chat/'):
            try:
                token=path.rsplit('/',1)[-1]
                return self.send(200,chat_public(CHAT_STORE.snapshot(token),token))
            except ValueError as exc: return self.send(404,{'error':str(exc)})
        if path.startswith('/source/') and path.endswith('.pdf'):
            try:return self.send(200,document_path(path.rsplit('/',1)[-1][:-4]).read_bytes(),'application/pdf')
            except ValueError as exc:return self.send(404,{'error':str(exc)})
        if path=='/agent-evaluation':
            p=ROOT/'reports/agent-evaluation.html'
            return self.send(200,p.read_bytes(),'text/html; charset=utf-8') if p.exists() else self.send(404,{'error':'Agent checks not run yet'})
        if path=='/evaluation':
            p=ROOT/'reports/evaluation-all.html'
            return self.send(200,p.read_bytes(),'text/html; charset=utf-8') if p.exists() else self.send(404,{'error':'Run evaluation first'})
        if path=='/api/health': return self.send(200,{'ok':True,'recipes':len(all_recipes()),'providers':status()})
        if path=='/api/catalog':
            recipes=[r for r in all_recipes() if preparation_complete(r)]
            return self.send(200,{'ingredients':sorted({i['name'] for r in recipes for i in r['ingredients']}),
             'recipe_count':len(recipes),'documents':list_documents(),'providers':status()})
        if path=='/api/evaluation':
            p=ROOT/'reports/evaluation-all.json'
            return self.send(200,json.loads(p.read_text()) if p.exists() else {'status':'not_run'})
        if path.startswith('/api/source/'):
            try:
                page=read_pdf_page(path.rsplit('/',1)[-1]);page.pop('path',None)
                return self.send(200,page)
            except ValueError as exc:return self.send(404,{'error':str(exc)})
        static=static_response(ROOT,path)
        if static:return self.send(200,*static)
        return self.send(404,{'error':'Not found'})

    def do_POST(self):
        path=urlparse(self.path).path
        if path not in ('/api/search','/api/chat','/api/chat/reset','/api/chat/select','/api/chat/open-plan') and not path.startswith('/api/plans/'): return self.send(404,{'error':'Not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<1 or size>20000: raise ValueError('Invalid request size')
            payload=json.loads(self.rfile.read(size))
            if path.startswith('/api/plans/'):return self.send(200,plan_api('POST',path,payload))
            if path=='/api/chat/select':
                if not isinstance(payload,dict) or set(payload)!={'session_id','recipe_id','selected'}:raise ValueError('Invalid recipe selection')
                return self.send(200,set_recipe_selection(CHAT_STORE,payload['session_id'],payload['recipe_id'],payload['selected']))
            if path=='/api/chat/open-plan':
                if not isinstance(payload,dict) or set(payload)!={'session_id','plan_id'}:raise ValueError('Invalid saved plan')
                return self.send(200,open_saved_plan(CHAT_STORE,payload.get('session_id'),payload['plan_id']))
            if path=='/api/chat/reset':
                if not isinstance(payload,dict) or set(payload)!={'session_id'} or not isinstance(payload['session_id'],str): raise ValueError('Invalid conversation')
                CHAT_STORE.delete(payload['session_id'])
                return self.send(200,{'ok':True})
            return self.send(200,run_chat(payload) if path=='/api/chat' else run_agent(payload))
        except (ValueError,TypeError) as e: return self.send(400,{'error':str(e)})
        except Exception:
            return self.send(500,{'error':'Unexpected error. Check data preparation and local server logs.'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8767);args=p.parse_args()
    all_recipes()
    print(f'DASH Meal Prep AI: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
