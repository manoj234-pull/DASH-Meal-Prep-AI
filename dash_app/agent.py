"""Bounded tool-calling agent. All mutable runtime state lives in this project."""
import json, time, threading, hashlib
from datetime import datetime, timezone
from uuid import uuid4
from .core import ROOT, validate_request, search_recipes, validate_results, canonical, all_recipes, list_documents, read_pdf_page
from .providers import load_env, nebius, retrieve_guidance, validate_extractive_notes, trace, HTTP_DEADLINE
import os

load_env()
MAX_TURNS=int(os.getenv("AGENT_MAX_TURNS","16"))
MAX_TOOLS=int(os.getenv("AGENT_MAX_TOOLS","24"))
MAX_GUIDANCE=2
MAX_CLARIFICATIONS=2
MAX_SECONDS=90
PROMPT_PATH=ROOT/'prompts/agent_system_v1.txt'
TOOLS_PATH=ROOT/'prompts/tools_v1.json'

class SessionStore:
    def __init__(self): self.items={};self.lock=threading.Lock()
    def put(self,state):
        with self.lock:
            now=time.monotonic()
            self.items={k:v for k,v in self.items.items() if v[0]>now}
            if len(self.items)>=64: raise ValueError('Too many waiting questions; please try again later')
            token=str(uuid4());self.items[token]=(now+1800,state);return token
    def resume(self,token,choice):
        with self.lock:
            item=self.items.get(token)
            if not item or item[0]<time.monotonic():
                self.items.pop(token,None);raise ValueError('This question expired or was already answered. Start a new search.')
            state=item[1]
            if isinstance(choice,bool) or not isinstance(choice,int) or not 0<=choice<len(state['pending']['choices']):raise ValueError('Choose one of the displayed answers')
            del self.items[token]
            return state
STORE=SessionStore()

def model_message(history):
    load_env()
    model=os.getenv('NEBIUS_MODEL')
    if not model: raise RuntimeError('NEBIUS_MODEL is not configured')
    response=nebius('/chat/completions',{'model':model,'temperature':0,'max_tokens':1400,
        'messages':history,'tools':json.loads(TOOLS_PATH.read_text(encoding='utf-8')),
        'tool_choice':'required','parallel_tool_calls':False})
    msg=response['choices'][0]['message']
    return {**msg,'_usage':response.get('usage',{})}

def compact(r):
    fields=['id','title','vegetarian','ingredients','missing','matched','requested_servings','scaled_ingredients','sodium_mg_per_serving','source_id','pdf_page','flags','source_url','document_id']
    return {k:r[k] for k in fields}

def run_agent(payload,model=None,retrieval=None,store=None):
    token=HTTP_DEADLINE.set(time.monotonic()+MAX_SECONDS)
    try:return _run_agent(payload,model,retrieval,store)
    finally:HTTP_DEADLINE.reset(token)

def _run_agent(payload,model=None,retrieval=None,store=None):
    model=model or model_message;retrieval=retrieval or retrieve_guidance;store=store or STORE
    if not isinstance(payload,dict):raise ValueError('Expected a request object')
    started=time.monotonic()
    if 'session_id' in payload:
        if set(payload)!={'session_id','choice'} or not isinstance(payload['session_id'],str):raise ValueError('Invalid clarification response')
        state=store.resume(payload['session_id'],payload['choice'])
        pending=state.pop('pending');replacement=pending['choices'][payload['choice']]
        ingredient=pending['ingredient']
        if replacement!='Not sure':
            state['request']['ingredients']=[replacement if x==ingredient else x for x in state['request']['ingredients']]
            state['request']=validate_request(state['request'])
        state['answered'].append(ingredient)
        state['matches']=None;state['guidance']={}
        state['messages'].append({'role':'user','content':json.dumps({'explicit_user_choice':replacement,'authoritative_request':state['request']})})
    else:
        request=validate_request(payload)
        state={'run_id':str(uuid4()),'request':request,'messages':[{'role':'system','content':PROMPT_PATH.read_text(encoding='utf-8')},
            {'role':'user','content':json.dumps({'authoritative_request':request,'instruction':'Use inspect_catalog to discover ingredient names and facts when interpretation is needed.'})}],
            'catalog':None,'interpretations':[],'original_request':request.copy(),'turns':0,'calls':0,'retrievals':0,'clarifications':0,'answered':[],'matches':None,'guidance':{},'steps':[], 'warnings':[], 'usage':[]}
    def event(step,status,detail):
        entry={'run_id':state['run_id'],'timestamp':datetime.now(timezone.utc).isoformat(),'step':step,'status':status,'detail':detail,'elapsed_ms':round((time.monotonic()-started)*1000,2)}
        state['steps'].append(entry)
        path=ROOT/'reports';path.mkdir(exist_ok=True)
        with (path/'agent-steps.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry)+'\n')
    event('agent_turn','started','Authoritative filters validated; tools selected by model')
    terminal=None;notes=[];selected=[];recommended=[];question=None;token=None
    schemas={t['function']['name']:t['function']['parameters'] for t in json.loads(TOOLS_PATH.read_text(encoding='utf-8'))}
    while state['turns']<MAX_TURNS and state['calls']<MAX_TOOLS and time.monotonic()-started<MAX_SECONDS:
        try:
            state['turns']+=1
            event('model','started',f"Decision {state['turns']}/{MAX_TURNS}")
            msg=model(state['messages'])
            usage=msg.pop('_usage',{})
            if usage:state['usage'].append(usage)
            calls=msg.get('tool_calls')
            if not isinstance(calls,list) or len(calls)!=1:
                event('model','rejected','Expected exactly one tool call')
                state['messages'].append({'role':'user','content':'Call exactly one listed tool. Do not answer in prose.'});continue
            call=calls[0];name=call['function']['name'];raw=call['function']['arguments']
            if not isinstance(raw,str) or len(raw)>12000:raise ValueError('Tool arguments are malformed or too large')
            clean={'role':'assistant','content':msg.get('content'),'tool_calls':calls}
            state['messages'].append(clean);state['calls']+=1
            try:
                args=json.loads(raw);schema=schemas.get(name)
                if not schema or not isinstance(args,dict) or (not set(schema['required']).issubset(args) or not set(args).issubset(schema['properties'])):raise ValueError('Unknown tool or unexpected arguments; filters cannot be overridden')
                if time.monotonic()-started>=MAX_SECONDS:raise ValueError('Run time budget exhausted')
                if name=='list_documents':
                    output={'documents':list_documents()}
                elif name=='read_pdf_page':
                    output=read_pdf_page(args['page_id']);output.pop('path',None)
                elif name=='inspect_catalog':
                    rows=all_recipes()
                    state['catalog']=sorted({canonical(i['name']) for r in rows for i in r['ingredients']})
                    output={'ingredients':state['catalog'], 'recipes':[{'id':r['id'],'title':r['title'],'ingredients':[i['name'] for i in r['ingredients']], 'vegetarian':r['vegetarian']} for r in rows]}
                elif name=='resolve_ingredient':
                    ingredient=args['ingredient'];target=args['catalog_name'];kind=args['kind'];reason=args['reason']
                    if kind not in ('pantry','exclusion'):raise ValueError('Kind must be pantry or exclusion')
                    field='ingredients' if kind=='pantry' else 'exclusions'
                    if not isinstance(ingredient,str) or ingredient not in state['request'][field]:raise ValueError('Interpret only an existing user ingredient or exclusion')
                    if not isinstance(target,str) or target not in (state['catalog'] or []):raise ValueError('Inspect the catalog first and use a retrieved ingredient name')
                    if not isinstance(reason,str) or not 1<=len(reason.strip())<=500:raise ValueError('Explain the equivalent meaning briefly')
                    if ingredient in state['answered']:raise ValueError('Do not reinterpret an answered clarification')
                    if kind=='pantry':state['request'][field]=[target if x==ingredient else x for x in state['request'][field]]
                    else:state['request'][field]=sorted(set(state['request'][field]+[target]))
                    interpretation={'ingredient':ingredient,'catalog_name':target,'kind':kind,'reason':reason}
                    state['interpretations'].append(interpretation)
                    state['request']=validate_request(state['request'])
                    state['matches']=None
                    output={'interpretation':interpretation,'request':state['request']}
                elif name=='search_recipes':
                    state['matches']=search_recipes(state['request'])
                    output={'recipes':[compact(r) for r in state['matches']],'count':len(state['matches'])}
                elif name=='get_recipe_details':
                    if not isinstance(args['recipe_id'],str):raise ValueError('Recipe ID must be text')
                    row=next((r for r in state['matches'] or [] if r['id']==args['recipe_id']),None)
                    if not row:raise ValueError('Search first and select a returned recipe ID')
                    output=row
                elif name=='retrieve_guidance':
                    query=args['query']
                    if not isinstance(query,str) or not 1<=len(query.strip())<=500:raise ValueError('Guidance query must contain 1-500 characters')
                    if state['retrievals']>=MAX_GUIDANCE:raise ValueError('Guidance search limit reached; use existing evidence or finish without notes')
                    state['retrievals']+=1
                    passages,mode=retrieval(query)
                    for passage in passages:state['guidance'][passage['id']]=passage
                    output={'mode':mode,'passages':passages,'remaining_searches':MAX_GUIDANCE-state['retrievals']}
                elif name=='ask_clarification':
                    ingredient=args['ingredient'];question=args['question']
                    if not isinstance(ingredient,str) or ingredient not in state['request']['ingredients'] or ingredient in state['answered']:raise ValueError('Ask about an unanswered ingredient in the user request')
                    choices=args['choices']
                    if not isinstance(choices,list) or not 1<=len(choices)<=7 or any(not isinstance(x,str) or not x.strip() or len(x)>100 for x in choices):raise ValueError('Supply a short list of food descriptions, each 1-100 characters')
                    choices=list(dict.fromkeys(canonical(x) for x in choices if canonical(x)!='not sure'))
                    if not 1<=len(choices)<=6:raise ValueError('Supply 1-6 distinct food descriptions; Not sure is added automatically')
                    if not isinstance(question,str) or not 1<=len(question.strip())<=300:raise ValueError('Ask a short question')
                    if state['turns']>MAX_TURNS-2 or state['calls']>MAX_TOOLS-2:raise ValueError('Not enough remaining decisions to resume a question; finish with available evidence')
                    if state['clarifications']>=MAX_CLARIFICATIONS:raise ValueError('Clarification limit reached')
                    state['clarifications']+=1
                    state['pending']={'ingredient':ingredient,'choices':choices+['Not sure'],'question':question}
                    output={'waiting_for_user':True,'question':question,'choices':state['pending']['choices']}
                    terminal='clarification'
                elif name=='finish':
                    ids=args['recipe_ids'];notes=args['notes']
                    if state['matches'] is None:raise ValueError('Run recipe search before finishing')
                    if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids) or len(ids)!=len(set(ids)):raise ValueError('Recipe IDs must be a list of unique strings')
                    if not set(ids).issubset({r['id'] for r in state['matches']}):raise ValueError('Select only recipes returned by the latest search')
                    recommended=ids
                    selected=[next(r for r in state['matches'] if r['id']==id) for id in ids]
                    if state['request']['match_mode']=='some':
                        selected += [r for r in state['matches'] if r['id'] not in ids]
                    issues=validate_results(selected,state['request'])
                    if issues:raise ValueError('Recipe validation failed')
                    try:
                        validate_extractive_notes(notes,selected,list(state['guidance'].values()))
                    except (ValueError,TypeError,KeyError):
                        notes=[]
                        event('verify_notes','rejected','Optional DASH notes failed source verification; validated recipe selection retained')
                        state['warnings'].append('The optional DASH explanation was omitted because its source support could not be verified. Recipe facts passed validation.')
                    terminal='completed' if selected else ('no_match' if not state['matches'] else 'no_selection')
                    output={'validated':True,'count':len(selected)}
                event(name,'passed',json.dumps({'count':output.get('count'), 'passages':len(output.get('passages',[])), 'waiting_for_user':output.get('waiting_for_user',False), 'interpretation':output.get('interpretation'), 'question':output.get('question'), 'choices':output.get('choices')}))
                state['messages'].append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(output)})
                if terminal:break
            except (ValueError,RuntimeError,TypeError,KeyError) as exc:
                notes=[];selected=[];terminal=None
                detail=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Malformed tool arguments or output'
                event(name,'rejected',detail)
                state['messages'].append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'error':detail})})
        except (RuntimeError,ValueError,KeyError,TypeError,StopIteration) as exc:
            terminal='error';event('model','failed','Model/provider failed or returned an invalid response')
            state['warnings'].append('The agent could not complete this request. Please retry; no recipe result was invented.');break
    if not terminal:
        terminal='limit_reached';selected=[];notes=[]
        state['warnings'].append('The agent reached its decision limit. Try a more specific ingredient list.')
    if terminal=='clarification':
        token=store.put(state);question=state['pending']
    if terminal=='no_selection':state['warnings'].append('The agent chose not to recommend the available candidates; this does not mean the catalog search found zero matches.')
    if selected and not notes:state['warnings'].append('No source-supported DASH note was selected. Recipe facts are available; DASH suitability is not certified.')
    result={'status':terminal,'session_id':token,'question':question,'run_id':state['run_id'],'count':len(selected),'recipes':selected,'agent_recommended_ids':[r['id'] for r in selected if r['id'] in recommended],
        'guidance':list(state['guidance'].values()),'notes':notes,'steps':state['steps'],'warnings':state['warnings'],
        'interpretations':state['interpretations'],'original_request':state['original_request'],'effective_request':state['request'],'candidate_count':len(state['matches'] or []),
        'model_turns':state['turns'],'tool_calls':state['calls'],'guidance_calls':state['retrievals'],'usage':state['usage'],
        'retrieval_mode':'Agent-selected evidence tools','explanation_mode':'Validated recipe facts; optional exact source quotations',
        'latency_ms':round((time.monotonic()-started)*1000,2),
        'prompt_version':'agent_system_v1','prompt_sha256':hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()}
    event('agent_turn','finished',terminal)
    try:trace(state['request'],{k:result[k] for k in ['status','run_id','model_turns','tool_calls','guidance_calls','usage','steps','prompt_sha256']})
    except (RuntimeError,ValueError,TypeError):result['warnings'].append('Remote tracing unavailable; local agent logs retained.')
    result['latency_ms']=round((time.monotonic()-started)*1000,2)
    with (ROOT/'reports/agent-runs.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result)+'\n')
    return result
