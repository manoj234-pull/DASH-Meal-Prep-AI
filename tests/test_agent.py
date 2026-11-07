import unittest,json
from unittest.mock import patch
from dash_app.agent import run_agent, SessionStore, MAX_TURNS

def call(name, **args):
    return {'role':'assistant','content':None,'tool_calls':[{'id':'call_'+name,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}

def fake(messages):
    responses=iter(messages)
    return lambda history: next(responses)

class AgentTests(unittest.TestCase):
    def setUp(self): self.store=SessionStore()
    def run_flow(self,payload,messages,retrieval=None):
        with patch('dash_app.agent.trace'):
            return run_agent(payload,model=fake(messages),retrieval=retrieval or (lambda query: ([], 'test evidence')),store=self.store)
    def test_agent_chooses_search_then_finish(self):
        r=self.run_flow({'ingredients':['new potato']},[call('search_recipes'),call('finish',recipe_ids=['R04'],notes=[])])
        self.assertEqual(r['status'],'completed');self.assertEqual(r['count'],1)
        self.assertEqual(r['tool_calls'],2)
    def test_retries_retrieval_when_first_has_no_evidence(self):
        queries=[]
        def retrieve(q):queries.append(q);return [],'test'
        r=self.run_flow({'ingredients':['new potato']},[call('search_recipes'),call('retrieve_guidance',query='potatoes'),call('retrieve_guidance',query='DASH vegetables'),call('finish',recipe_ids=['R04'],notes=[])],retrieve)
        self.assertEqual(len(queries),2);self.assertEqual(r['status'],'completed')
    def test_clarification_and_resume(self):
        r=self.run_flow({'ingredients':['rice']},[call('inspect_catalog'),call('ask_clarification',ingredient='rice',question='What kind of rice do you have?',choices=['cooked brown rice'])])
        self.assertEqual(r['status'],'clarification')
        follow=self.run_flow({'session_id':r['session_id'],'choice':0},[call('search_recipes'),call('finish',recipe_ids=['R05','R09'],notes=[])])
        self.assertEqual(follow['status'],'completed');self.assertEqual(follow['count'],2)
        with self.assertRaises(ValueError):self.run_flow({'session_id':r['session_id'],'choice':0},[])
    def test_filters_are_not_changeable_by_model(self):
        r=self.run_flow({'ingredients':['zucchini'],'exclusions':['garlic']},[call('search_recipes',exclusions=[]),call('search_recipes'),call('finish',recipe_ids=[],notes=[])])
        self.assertEqual(r['status'],'no_match');self.assertEqual(r['count'],0)
        self.assertTrue(any(s['status']=='rejected' for s in r['steps']))
    def test_invented_recipe_cannot_finish(self):
        r=self.run_flow({'ingredients':['new potato']},[call('search_recipes'),call('finish',recipe_ids=['R99'],notes=[]),call('finish',recipe_ids=['R04'],notes=[])])
        self.assertEqual([x['id'] for x in r['recipes']],['R04'])
        self.assertTrue(any(s['status']=='rejected' for s in r['steps']))
    def test_unsupported_quote_rejected(self):
        r=self.run_flow({'ingredients':['new potato']},[call('search_recipes'),call('finish',recipe_ids=['R04'],notes=[{'recipe_id':'R04','guidance_id':'fake','quote':'This meal is guaranteed to cure hypertension.'}]),call('finish',recipe_ids=['R04'],notes=[])])
        self.assertEqual(r['notes'],[])
        self.assertTrue(any(s['status']=='rejected' for s in r['steps']))
    def test_loop_stops_at_budget(self):
        with patch('dash_app.agent.trace'):
            r=run_agent({'ingredients':['new potato']},model=lambda h:call('search_recipes'),store=self.store)
        self.assertEqual(r['status'],'limit_reached');self.assertLessEqual(r['model_turns'],MAX_TURNS)
    def test_provider_failure_explicit(self):
        def fail(h):raise RuntimeError('Provider connection failed')
        with patch('dash_app.agent.trace'):r=run_agent({'ingredients':['new potato']},model=fail,store=self.store)
        self.assertEqual(r['status'],'error');self.assertEqual(r['count'],0)
    def test_cannot_finish_before_search(self):
        r=self.run_flow({'ingredients':['moonberry']},[call('finish',recipe_ids=[],notes=[]),call('search_recipes'),call('finish',recipe_ids=[],notes=[])])
        self.assertEqual(r['status'],'no_match')
        self.assertTrue(any(s['status']=='rejected' for s in r['steps']))
    def test_bad_clarification_choice(self):
        r=self.run_flow({'ingredients':['rice']},[call('inspect_catalog'),call('ask_clarification',ingredient='rice',question='Which rice?',choices=['cooked brown rice'])])
        with self.assertRaises(ValueError):self.run_flow({'session_id':r['session_id'],'choice':99},[])

class AgentBudgetTests(unittest.TestCase):
    def test_does_not_offer_question_without_resume_budget(self):
        messages=[call('search_recipes')]*(MAX_TURNS-2)+[call('inspect_catalog'),call('ask_clarification',ingredient='rice',question='Which rice?',choices=['cooked brown rice'])]
        with patch('dash_app.agent.trace'):
            r=run_agent({'ingredients':['rice']},model=fake(messages),store=SessionStore())
        self.assertEqual(r['status'],'limit_reached')
        self.assertIsNone(r['session_id'])
    def test_http_deadline_rejects_expired_request(self):
        from dash_app.providers import HTTP_DEADLINE,request_json
        import time
        token=HTTP_DEADLINE.set(time.monotonic()-1)
        try:
            with patch('dash_app.providers.urllib.request.urlopen') as net:
                with self.assertRaises(RuntimeError):request_json('https://example.com',{})
                net.assert_not_called()
        finally:HTTP_DEADLINE.reset(token)

from tests.catalog_fixture import catalog_fixture
def setUpModule():
    global _catalog_context
    _catalog_context=catalog_fixture();_catalog_context.__enter__()
def tearDownModule():_catalog_context.__exit__(None,None,None)
