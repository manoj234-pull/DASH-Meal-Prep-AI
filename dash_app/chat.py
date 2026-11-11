"""Conversation-scoped memory and source-backed tools; no new dependencies."""
import copy
import json
import os
import math
import threading
import time
from uuid import uuid4
from .core import ROOT, validate_request, search_recipes, validate_results, all_recipes, read_pdf_page, get_recipe_details as read_recipe_details
from .recipe_view import validate_view, apply_view, DEFAULT_VIEW
from .providers import load_env, nebius, retrieve_guidance, HTTP_DEADLINE
from .planner import build_plan, build_grocery_list, plan_nutrition_summary, validate_prep_timeline, save_plan, load_plan
from .nutrition import search_foods, get_food_nutrition

PROMPT = ROOT / 'prompts/chat_system_v2.txt'
TOOLS = ROOT / 'prompts/chat_tools_v2.json'
DEFAULT_CONTEXT = {'ingredients': [], 'servings': 2, 'diet': 'any', 'exclusions': [], 'match_mode': 'some', 'max_sodium_mg': None, 'minimum_match_percent':0, 'match_inclusive':True}
CHAT_DEFAULT_VIEW=copy.deepcopy(DEFAULT_VIEW)

class ChatStore:
    def __init__(self, ttl=1800, capacity=64):
        self.ttl, self.capacity = ttl, capacity
        self.items = {}
        self.lock = threading.RLock()
    def create(self):
        with self.lock:
            now = time.monotonic()
            self.items = {k:v for k,v in self.items.items() if v['expires']>now or v['busy']}
            if len(self.items)>=self.capacity: raise ValueError('Too many active chats. Please try again shortly.')
            token = str(uuid4())
            self.items[token] = {'expires': now+self.ttl, 'busy': False, 'state': {
                'context':copy.deepcopy(DEFAULT_CONTEXT), 'messages':[], 'result':None,
                'memory':[], 'memory_through':0, 'result_view':copy.deepcopy(CHAT_DEFAULT_VIEW),
                'matching_preference_confirmed':False,
                'selected_recipe_ids':[],
                'tool_cache':{},
                'plan':None, 'grocery_list':[], 'prep_timeline':[],
                'nutrition_summary':None, 'saved_plan_id':None}}
            return token
    def _item(self, token):
        item = self.items.get(token)
        if not item or (item['expires']<time.monotonic() and not item['busy']):
            self.items.pop(token,None)
            raise ValueError('This conversation has expired. Start a new chat.')
        return item
    def snapshot(self, token):
        with self.lock: return copy.deepcopy(self._item(token)['state'])
    def acquire(self, token):
        with self.lock:
            item = self._item(token)
            if item['busy']: raise ValueError('Please wait for the current reply.')
            item['busy']=True
            return copy.deepcopy(item['state'])
    def release(self, token, state):
        with self.lock:
            item=self.items.get(token)
            if item:
                item.update(state=copy.deepcopy(state),busy=False,expires=time.monotonic()+self.ttl)
    def delete(self, token):
        with self.lock:
            item=self._item(token)
            if item['busy']: raise ValueError('Please wait for the current reply before starting again.')
            del self.items[token]

STORE=ChatStore()

def model_message(history):
    load_env()
    if not os.getenv('NEBIUS_MODEL'): raise RuntimeError('Model is not configured')
    response=nebius('/chat/completions', {'model':os.environ['NEBIUS_MODEL'], 'temperature':0, 'max_tokens':1800,
        'messages':history, 'tools':json.loads(TOOLS.read_text(encoding='utf-8-sig')), 'tool_choice':'required', 'parallel_tool_calls':False})
    return response['choices'][0]['message']

def verify_reply(reply, history, state):
    evidence=[m for m in history if m['role'] in ('user','tool')]
    tool_names={call['id']:call['function']['name'] for message in history if message.get('role')=='assistant'
                for call in message.get('tool_calls',[]) if isinstance(call,dict) and call.get('id') and call.get('function',{}).get('name')}
    successful_tools=[]
    for message in history:
        if message.get('role')!='tool' or message.get('tool_call_id') not in tool_names:continue
        try: content=json.loads(message.get('content','{}'))
        except (TypeError,json.JSONDecodeError):continue
        if not isinstance(content,dict) or 'error' in content:continue
        successful_tools.append(tool_names[message['tool_call_id']])
    response=nebius('/chat/completions', {'model':os.environ['NEBIUS_MODEL'], 'temperature':0, 'max_tokens':800,
        'response_format':{'type':'json_object'}, 'messages':[
            {'role':'system','content':(ROOT/'prompts/chat_verify_v2.txt').read_text(encoding='utf-8-sig')},
            {'role':'user','content':json.dumps({'reply':reply,'context':state['context'],'results':brief_result(state['result']),
                'plan':brief_plan(state), 'successful_tools':successful_tools,
                'matching_preference_confirmed':state.get('matching_preference_confirmed',False),
                'selected_recipes':brief_selection(state),
                'evidence':evidence, 'older_user_notes':state.get('memory',[])})}]})
    return json.loads(response['choices'][0]['message']['content']).get('supported') is True

def review_result_exclusions(user_message, result, view):
    if not view.get('exclude_ingredients') or not result:return {'exclude_recipe_ids':[]}
    recipes=[{'id':row['id'],'title':row['title'],
              'ingredients':[item.get('name','') for item in row.get('ingredients',[])]}
             for row in result.get('recipes',[])]
    response=nebius('/chat/completions', {'model':os.environ['NEBIUS_MODEL'], 'temperature':0, 'max_tokens':1200,
        'response_format':{'type':'json_object'}, 'messages':[
            {'role':'system','content':(ROOT/'prompts/chat_filter_review_v2.txt').read_text(encoding='utf-8-sig')},
            {'role':'user','content':json.dumps({'user_request':user_message,
                'exclude_terms':view['exclude_ingredients'],'recipes':recipes})}]})
    payload=json.loads(response['choices'][0]['message']['content'])
    ids=payload.get('exclude_recipe_ids',[])
    if not isinstance(ids,list):return {'exclude_recipe_ids':[]}
    allowed={row['id'] for row in result.get('recipes',[])}
    return {'exclude_recipe_ids':[recipe_id for recipe_id in ids
            if isinstance(recipe_id,str) and recipe_id in allowed][:100]}

def public(state, token, status='ready', reply=None):
    return {'session_id':token, 'status':status, 'reply':reply, 'context':state['context'],
        'matching_preference_confirmed':state.get('matching_preference_confirmed',False),
        'selected_recipe_ids':state.get('selected_recipe_ids',[]),
        'messages':state['messages'], 'result':state['result'],
        'result_view':state.get('result_view',CHAT_DEFAULT_VIEW), 'plan':state.get('plan'),
        'grocery_list':state.get('grocery_list',[]), 'prep_timeline':state.get('prep_timeline',[]),
        'nutrition_summary':state.get('nutrition_summary'), 'saved_plan_id':state.get('saved_plan_id')}

def set_recipe_selection(store,token,recipe_id,selected):
    if not isinstance(recipe_id,str) or len(recipe_id)>100 or not isinstance(selected,bool):raise ValueError('Invalid recipe selection')
    state=store.acquire(token)
    try:
        candidates={row['id'] for row in (state.get('result') or {}).get('recipes',[])}
        current=list(state.get('selected_recipe_ids',[]))
        if selected and recipe_id not in candidates and recipe_id not in current:raise ValueError('Choose a recipe from the current results')
        if selected and recipe_id not in current:current.append(recipe_id)
        if not selected:current=[value for value in current if value!=recipe_id]
        state['selected_recipe_ids']=current
    finally:store.release(token,state)
    return public(state,token)

def open_saved_plan(store,token,plan_id,loader=load_plan):
    token=token or store.create();state=store.acquire(token)
    try:
        plan=loader(plan_id)
        state['plan']=plan;state['saved_plan_id']=plan['plan_id']
        state['selected_recipe_ids']=list(dict.fromkeys(entry['recipe_id'] for entry in plan.get('entries',[])))
        state['grocery_list']=plan.get('grocery_list') or build_grocery_list(plan)
        state['nutrition_summary']=plan.get('nutrition_summary') or plan_nutrition_summary(plan)
        state['prep_timeline']=plan.get('prep_timeline',[])
    finally:store.release(token,state)
    return public(state,token)

def brief_plan(state):
    plan=state.get('plan')
    if not plan:return None
    return {'name':plan['name'], 'sodium_target_mg':plan.get('sodium_target_mg'),
        'entries':[{k:e.get(k) for k in ('day','meal','recipe_id','title','servings')} for e in plan['entries']],
        'prep_timeline':state.get('prep_timeline',[]), 'saved_plan_id':state.get('saved_plan_id')}

def brief_result(result):
    if not result: return None
    return {'count':result['count'], 'total_count':result.get('total_count',result['count']), 'applied_view':result.get('applied_view'), 'recipes':[{'id':r['id'],'title':r['title'],'match_percent':r['match_percent'],'pantry_match_percent':r['pantry_match_percent'],'sodium_mg_per_serving':r['sodium_mg_per_serving'],'vegetarian':r['vegetarian'],'matched':r['matched'],'missing':r['missing']} for r in result['recipes']]}

def brief_selection(state):
    selected=list(state.get('selected_recipe_ids',[]))
    if not selected:return []
    titles={row.get('id'):row.get('title') for row in (state.get('result') or {}).get('recipes',[])}
    for entry in (state.get('plan') or {}).get('entries',[]):
        titles.setdefault(entry.get('recipe_id'),entry.get('title'))
    return [{'id':recipe_id,'title':titles.get(recipe_id) or 'Selected recipe'} for recipe_id in selected]

def update_context(current, patch):
    if not patch or not set(patch).issubset(DEFAULT_CONTEXT): raise ValueError('Provide only supported preference fields')
    candidate={**current,**patch}
    # Empty pantry is valid conversation state, but cannot be searched.
    empty=candidate['ingredients']==[]
    checked=validate_request({**candidate,'ingredients':['validation placeholder']} if empty else candidate)
    if empty: checked['ingredients']=[]
    minimum=candidate.get('minimum_match_percent',0); inclusive=candidate.get('match_inclusive',True)
    filter_matches([],minimum,inclusive)
    return {**checked,'minimum_match_percent':minimum,'match_inclusive':inclusive}

def filter_matches(rows, minimum, inclusive):
    if isinstance(minimum,bool) or not isinstance(minimum,(int,float)) or not math.isfinite(minimum) or not 0<=minimum<=100:
        raise ValueError('Ingredient match percentage must be between 0 and 100')
    if not isinstance(inclusive,bool):raise ValueError('Specify whether the threshold is inclusive')
    return [r for r in rows if r['match_percent'] is not None and (r['match_percent']>=minimum if inclusive else r['match_percent']>minimum)]

def valid_match_clarification(reply, state):
    """Validate the required choice without asking a second LLM for a subjective verdict."""
    if state.get('matching_preference_confirmed',False) or not state.get('context',{}).get('ingredients'):
        return False
    if not isinstance(reply,str) or len(reply)>500 or '?' not in reply:
        return False
    text=reply.casefold()
    return ('exact' in text and 'partial' in text and ('every' in text or 'all' in text)
            and 'some' in text and 'missing' in text and 'grocer' in text)

def simple_clarification(reply):
    if not isinstance(reply,str) or not reply.strip().endswith('?') or len(reply)>500:return False
    text=reply.casefold()
    evidence_terms=(' mg','sodium','dash','nutrition','calorie','recipe contains','source','pdf','percent','%')
    return not any(term in text for term in evidence_terms)

def cache_read(state,key):
    value=state.get('tool_cache',{}).get(key)
    return copy.deepcopy(value) if value is not None else None

def cache_write(state,key,value):
    cache=state.setdefault('tool_cache',{})
    if len(cache)>=24:cache.pop(next(iter(cache)))
    cache[key]=copy.deepcopy(value)

def search_context(context, view=None):
    request=validate_request(context);rows=search_recipes(request)
    if validate_results(rows,request):raise ValueError('Recipe source validation failed')
    rows=filter_matches(rows,context.get('minimum_match_percent',0),context.get('match_inclusive',True))
    rows,total=apply_view(rows,view or DEFAULT_VIEW)
    return {'total_count':total,'applied_view':view or DEFAULT_VIEW,'status':'completed' if rows else 'no_match','count':len(rows),'recipes':rows,'notes':[],'guidance':[], 'warnings':[], 'interpretations':[],
            'match_filter':{'minimum_percent':context.get('minimum_match_percent',0),'inclusive':context.get('match_inclusive',True)}}

def checked_memory(notes, messages):
    """Retain only verbatim user quotes, never model-invented memories."""
    if not isinstance(notes,list): return []
    valid=[]
    for note in notes[:30]:
        if not isinstance(note,dict): continue
        i=note.get('message_index'); quote=note.get('quote')
        if isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(messages): continue
        if messages[i]['role']!='user' or not isinstance(quote,str) or not 1<=len(quote)<=500: continue
        if quote not in messages[i]['content']: continue
        item={'message_index':i,'quote':quote}
        if item not in valid:valid.append(item)
    return valid

def summarize_choices(messages, previous):
    response=nebius('/chat/completions',{'model':os.environ['NEBIUS_MODEL'],'temperature':0,'max_tokens':2400,
        'response_format':{'type':'json_object'},'messages':[
        {'role':'system','content':(ROOT/'prompts/chat_memory_v2.txt').read_text(encoding='utf-8-sig')},
        {'role':'user','content':json.dumps({'previous_notes':previous,'older_messages':messages})}]})
    return json.loads(response['choices'][0]['message']['content']).get('notes',[])

def refresh_memory(state, summarizer):
    messages=state['messages']; boundary=max(0,len(messages)-16)
    through=state.get('memory_through',0)
    if boundary-through<16:return
    # Process incremental blocks; never resend the entire growing conversation.
    end=min(boundary,through+16)
    batch=[{'message_index':i,**messages[i]} for i in range(through,end) if messages[i]['role']=='user']
    try:
        notes=summarizer(batch,state.get('memory',[]))
        checked=checked_memory(notes,messages)
        if checked or not state.get('memory'):
            state['memory']=checked
        state['memory_through']=end
    except Exception:
        # Exact history and structured choices stay available if summarization fails.
        pass

def recall_conversation(messages, query='', offset=0):
    if not isinstance(query,str) or len(query)>200:raise ValueError('Use a short conversation query')
    if isinstance(offset,bool) or not isinstance(offset,int) or offset<0:raise ValueError('Invalid history offset')
    terms=query.casefold().split()
    rows=[{'message_index':i,**m} for i,m in enumerate(messages) if all(t in m['content'].casefold() for t in terms)]
    return {'messages':rows[offset:offset+8],'total':len(rows),'next_offset':offset+8 if offset+8<len(rows) else None}

def run_chat(payload, store=None, model=None, retrieval=None, verifier=None, summarizer=None, filter_reviewer=None):
    store=store or STORE; model=model or model_message; retrieval=retrieval or retrieve_guidance; verifier=verifier or verify_reply; summarizer=summarizer or summarize_choices; filter_reviewer=filter_reviewer or review_result_exclusions
    if not isinstance(payload,dict) or not set(payload).issubset({'session_id','message'}): raise ValueError('Invalid chat request')
    message=payload.get('message')
    if not isinstance(message,str) or not 1<=len(message.strip())<=2000: raise ValueError('Write a message of 1–2,000 characters.')
    session_id=payload.get('session_id')
    if session_id is not None and (not isinstance(session_id,str) or len(session_id)>100): raise ValueError('Invalid conversation')
    token=session_id or store.create()
    state=store.acquire(token); original=copy.deepcopy(state)
    started=time.monotonic(); deadline=HTTP_DEADLINE.set(started+90)
    reply=None; status='completed'; steps=[]
    try:
        refresh_memory(state,summarizer)
        history=[{'role':'system','content':PROMPT.read_text(encoding='utf-8-sig')},
                 {'role':'system','content':json.dumps({'session_context':state['context'], 'result_view':state.get('result_view',CHAT_DEFAULT_VIEW),
                    'matching_preference_confirmed':state.get('matching_preference_confirmed',False),
                    'selected_recipe_ids':state.get('selected_recipe_ids',[]),
                    'selected_recipes':brief_selection(state),
                    'latest_results':brief_result(state['result']), 'latest_plan':brief_plan(state),
                    'older_user_notes':state.get('memory',[]), 'total_messages':len(state['messages'])})}]
        history.extend(state['messages'][-16:])
        history.append({'role':'user','content':message.strip()})
        schemas={t['function']['name']:t['function']['parameters'] for t in json.loads(TOOLS.read_text(encoding='utf-8-sig'))}
        retrieved=0;seen_calls=set()
        for turn in range(10):
            if time.monotonic()-started>=90: break
            msg=model(history); calls=msg.get('tool_calls') or []
            if not calls and isinstance(msg.get('content'),str):
                calls=[{'id':'reply_'+str(turn),'type':'function','function':{'name':'respond','arguments':json.dumps({'message':msg['content']})}}]
            if len(calls)!=1:
                history.append({'role':'user','content':'Please choose exactly one available tool.'})
                continue
            call=calls[0]; name=call['function']['name']
            history.append({'role':'assistant','content':msg.get('content'),'tool_calls':calls})
            try:
                args=json.loads(call['function']['arguments']); schema=schemas.get(name)
                if not schema or not isinstance(args,dict) or not set(schema.get('required',[])).issubset(args) or not set(args).issubset(schema['properties']): raise ValueError('Invalid tool arguments')
                progress={'context':state['context'],'view':state.get('result_view'),'selected':state.get('selected_recipe_ids',[]),
                          'plan_id':state.get('saved_plan_id'),'has_result':state.get('result') is not None,
                          'matching_preference_confirmed':state.get('matching_preference_confirmed',False)}
                signature=json.dumps({'tool':name,'args':args,'progress':progress},sort_keys=True)
                if signature in seen_calls:raise ValueError('This tool call repeated without making progress. Use the existing result, choose a different tool, ask one clear question, or finish the response.')
                seen_calls.add(signature)
                if name=='update_context':
                    updated=update_context(state['context'],args)
                    if updated!=state['context']: state['result']=None
                    state['context']=updated; output={'context':updated}
                    if 'match_mode' in args:state['matching_preference_confirmed']=True
                elif name=='recall_conversation':
                    output=recall_conversation(state['messages'],args.get('query',''),args.get('offset',0))
                elif name=='inspect_catalog':
                    query=args.get('query','')
                    if not isinstance(query,str) or len(query)>100:raise ValueError('Use a short catalog query')
                    rows=all_recipes(); q=query.casefold()
                    names=sorted({i['name'] for r in rows for i in r['ingredients'] if q in i['name'].casefold()})
                    recipes=[{'id':r['id'],'title':r['title']} for r in rows if not q or q in r['title'].casefold()]
                    output={'ingredients':names[:100], 'ingredient_count':len(names), 'recipes':recipes[:110], 'recipe_count':len(recipes), 'note':'Narrow the query if ingredient names are truncated.'}
                elif name=='search_recipes':
                    if not state.get('matching_preference_confirmed',False):
                        raise ValueError('Recipe search is waiting for the match choice to be saved. Re-read the newest user message: if it allows extra or missing ingredients, call update_context with match_mode "some"; if it requires every listed ingredient, call update_context with match_mode "all". Ask the match question only when the user has not answered it yet.')
                    cache_key='recipes:'+json.dumps({'context':state['context'],'view':state.get('result_view')},sort_keys=True)
                    state['result']=cache_read(state,cache_key)
                    if state['result'] is None:
                        state['result']=search_context(state['context'],state.get('result_view'))
                        cache_write(state,cache_key,state['result'])
                    output=brief_result(state['result'])
                elif name=='query_recipe_results':
                    if not state.get('matching_preference_confirmed',False):
                        raise ValueError('Recipe search is waiting for the match choice to be saved. Re-read the newest user message: if it allows extra or missing ingredients, call update_context with match_mode "some"; if it requires every listed ingredient, call update_context with match_mode "all". Ask the match question only when the user has not answered it yet.')
                    view=validate_view(state.get('result_view',{}),args)
                    context={**state['context'],'minimum_match_percent':0,'match_inclusive':True}
                    result=search_context(context,view)
                    reviewed=filter_reviewer(message.strip(),result,view)
                    reviewed_ids=reviewed.get('exclude_recipe_ids',[]) if isinstance(reviewed,dict) else []
                    reviewed_ids=[recipe_id for recipe_id in reviewed_ids
                                  if recipe_id not in view.get('exclude_recipe_ids',[])]
                    if reviewed_ids:
                        combined=list(dict.fromkeys(view.get('exclude_recipe_ids',[])+reviewed_ids))
                        view=validate_view(view,{'exclude_recipe_ids':combined})
                        result=search_context(context,view)
                    state['context']=context;state['result_view']=view;state['result']=result
                    output=brief_result(result)
                elif name=='get_recipe_details':
                    recipe_id=args['recipe_id']
                    allowed={r['id'] for r in (state.get('result') or {}).get('recipes',[])}
                    allowed.update(entry.get('recipe_id') for entry in (state.get('plan') or {}).get('entries',[]))
                    allowed.update(state.get('selected_recipe_ids',[]))
                    if recipe_id not in allowed: raise ValueError('Use a recipe ID from current results, selections, or the current plan')
                    output=read_recipe_details(recipe_id)
                elif name=='retrieve_guidance':
                    q=args['query']
                    if not isinstance(q,str) or not 1<=len(q)<=500:raise ValueError('Use a short guidance query')
                    if retrieved>=2:raise ValueError('Use the evidence already retrieved or explain what is missing')
                    retrieved+=1;cache_key='guidance:'+q.strip().casefold();cached=cache_read(state,cache_key)
                    if cached is None:
                        passages,mode=retrieval(q);cached={'passages':passages,'mode':mode};cache_write(state,cache_key,cached)
                    passages,mode=cached['passages'],cached['mode']
                    output={'passages':passages,'mode':mode}
                elif name=='read_pdf_page':
                    if not isinstance(args['page_id'],str):raise ValueError('Use a source page ID')
                    output=read_pdf_page(args['page_id']);output.pop('path',None)
                elif name=='set_weekly_plan':
                    requested_ids={entry.get('recipe_id') for entry in args.get('entries',[]) if isinstance(entry,dict)}
                    selected_ids=set(state.get('selected_recipe_ids',[]))
                    if not requested_ids or not requested_ids.issubset(selected_ids):
                        raise ValueError('The user must select every recipe before it can be added to the weekly plan')
                    plan=build_plan(args)
                    saved=save_plan({**plan,**({'plan_id':state['saved_plan_id']} if state.get('saved_plan_id') else {})},'draft')
                    state['plan']=saved
                    state['grocery_list']=build_grocery_list(plan)
                    state['nutrition_summary']=plan_nutrition_summary(plan)
                    state['prep_timeline']=[]
                    state['saved_plan_id']=saved['plan_id']
                    output={**brief_plan(state), 'grocery_item_count':len(state['grocery_list']),
                        'nutrition_summary':state['nutrition_summary']}
                elif name=='set_prep_timeline':
                    if not state.get('plan'):raise ValueError('Create a weekly plan first')
                    state['prep_timeline']=validate_prep_timeline(state['plan'],args['tasks'])
                    save_plan({**state['plan'],'plan_id':state['saved_plan_id'],'grocery_list':state.get('grocery_list',[]),
                               'nutrition_summary':state.get('nutrition_summary'),'prep_timeline':state['prep_timeline']},'draft')
                    output={'tasks':state['prep_timeline']}
                elif name=='save_weekly_plan':
                    if not state.get('plan'):raise ValueError('Create a weekly plan first')
                    saved=save_plan({**state['plan'], 'grocery_list':state.get('grocery_list',[]),
                        'prep_timeline':state.get('prep_timeline',[]),
                        'nutrition_summary':state.get('nutrition_summary')})
                    state['saved_plan_id']=saved['plan_id']
                    output={'saved':True,'plan_id':saved['plan_id']}
                elif name=='search_usda_foods':
                    output={'foods':search_foods(args['query'],args.get('limit',10))}
                elif name=='get_usda_food_nutrition':
                    output=get_food_nutrition(args['fdc_id'],args.get('grams',100))
                elif name=='respond':
                    candidate=args['message']
                    if not isinstance(candidate,str) or not 1<=len(candidate.strip())<=2000:raise ValueError('Use a short reply')
                    pending_match_question=(not state.get('matching_preference_confirmed',False)
                                            and bool(state['context'].get('ingredients')))
                    simple_without_state=(simple_clarification(candidate)
                                          and not state.get('selected_recipe_ids')
                                          and state.get('result') is None
                                          and state.get('plan') is None)
                    supported=(valid_match_clarification(candidate,state)
                               or verifier(candidate,history,state)) if pending_match_question else (simple_without_state or verifier(candidate,history,state))
                    if not supported:
                        if not state.get('matching_preference_confirmed',False) and state['context'].get('ingredients'):
                            raise ValueError('Reply verifier rejected the clarification. Ask one clear question defining exact as every listed ingredient and partial as some listed ingredients with missing groceries shown. Wait for the user before searching or planning.')
                        raise ValueError('Reply was not supported by the evidence. Ask a clarification or use only retrieved facts.')
                    reply=candidate;steps.append({'tool':'verify_reply','ok':True})
                    break
                steps.append({'tool':name,'ok':True})
            except (ValueError,KeyError,TypeError,RuntimeError) as exc:
                output={'error':str(exc)}; steps.append({'tool':name,'ok':False})
            history.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(output)})
        if reply is None:
            completed_tools={step['tool'] for step in steps if step.get('ok')}
            if 'set_prep_timeline' in completed_tools:
                status='completed';reply='Your weekly plan and prep timeline are ready.'
            elif 'set_weekly_plan' in completed_tools:
                status='completed';reply='Your weekly plan and grocery list are ready.'
            elif 'query_recipe_results' in completed_tools:
                status='completed';reply='Your requested recipe filters are applied below.'
            elif 'search_recipes' in completed_tools:
                status='completed';reply='Matching recipes are displayed below.'
            else:
                status='limit_reached';reply='I couldn’t finish that request. Your preferences are still here; please try again.'
        state['messages']=(state['messages']+[{'role':'user','content':message.strip()},{'role':'assistant','content':reply}])
    except Exception as exc:
        steps.append({'tool':'chat','ok':False,'error_type':type(exc).__name__,'error':str(exc)[:300]})
        state=original; status='error'; reply='I couldn’t connect to finish that request. Your previous preferences are safe. Please try again.'
        state['messages']=(state['messages']+[{'role':'user','content':message.strip()},{'role':'assistant','content':reply}])
    finally:
        store.release(token,state);HTTP_DEADLINE.reset(deadline)
    # Operational log deliberately excludes conversation contents and session tokens.
    reports=ROOT/'reports';reports.mkdir(exist_ok=True)
    with (reports/'chat-runs.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'run_id':str(uuid4()),'status':status,'steps':steps,'latency_ms':round((time.monotonic()-started)*1000)})+'\n')
    return public(state,token,status,reply)

