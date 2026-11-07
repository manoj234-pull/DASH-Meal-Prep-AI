"""Run with python app.py. Local-only form UI, no extra server dependencies."""
import argparse
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
from dash_app.core import ROOT,DATA,all_recipes,document_path,read_pdf_page,list_documents,preparation_complete
from dash_app.providers import status
from dash_app.agent import run_agent


class Handler(BaseHTTPRequestHandler):
    def send(self,code,body,content_type='application/json; charset=utf-8'):
        if not isinstance(body,bytes): body=json.dumps(body).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)

    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/': return self.send(200,(ROOT/'web/index.html').read_bytes(),'text/html; charset=utf-8')
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
        return self.send(404,{'error':'Not found'})

    def do_POST(self):
        if urlparse(self.path).path!='/api/search': return self.send(404,{'error':'Not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<1 or size>20000: raise ValueError('Invalid request size')
            payload=json.loads(self.rfile.read(size))
            return self.send(200,run_agent(payload))
        except (ValueError,TypeError) as e: return self.send(400,{'error':str(e)})
        except Exception:
            return self.send(500,{'error':'Unexpected error. Check data preparation and local server logs.'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8767);args=p.parse_args()
    all_recipes()
    print(f'DASH Meal Prep AI: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
