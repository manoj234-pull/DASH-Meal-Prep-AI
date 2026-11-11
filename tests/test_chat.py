import json, unittest
from unittest.mock import patch
from dash_app.chat import ChatStore, run_chat
from dash_app import chat as chat_module
from tests.catalog_fixture import catalog_fixture

def call(tool_name, **args):
    return {'role':'assistant','content':None,'tool_calls':[{'id':'c_'+tool_name,'type':'function','function':{'name':tool_name,'arguments':json.dumps(args)}}]}

def model(*steps):
    it=iter(steps)
    return lambda history: next(it)

class ChatTests(unittest.TestCase):
    def setUp(self):
        self.store=ChatStore()
        self.fixture=catalog_fixture(); self.fixture.__enter__()
    def tearDown(self): self.fixture.__exit__(None,None,None)
    def run_turn(self, message, steps, session_id=None):
        return run_chat({'message':message, 'session_id':session_id},store=self.store,model=model(*steps),verifier=lambda *args: True)

    def test_reply_verifier_receives_successful_tool_names(self):
        history=[call('query_recipe_results',include_ingredients=['chicken']),
                 {'role':'tool','tool_call_id':'c_query_recipe_results','content':'{"count": 2}'}]
        response={'choices':[{'message':{'content':'{"supported": true}'}}]}
        state={'context':{},'result':None,'plan':None,'prep_timeline':[],'memory':[]}
        with patch.object(chat_module,'nebius',return_value=response) as request, patch.dict(chat_module.os.environ,{'NEBIUS_MODEL':'test'}):
            self.assertTrue(chat_module.verify_reply('Filtered recipes are displayed below.',history,state))
        payload=json.loads(request.call_args.args[1]['messages'][1]['content'])
        self.assertEqual(payload['successful_tools'],['query_recipe_results'])
        self.assertFalse(payload['matching_preference_confirmed'])
    def test_followup_preserves_preferences_and_scales(self):
        first=self.run_turn('I have new potato, vegetarian, exclude garlic, 2 portions',[
            call('update_context',ingredients=['new potato'],diet='vegetarian',exclusions=['garlic'],servings=2,match_mode='some'),
            call('search_recipes'),call('respond',message='Here are your recipes.')])
        second=self.run_turn('Make it 4 portions',[
            call('update_context',servings=4),call('search_recipes'),call('respond',message='Updated.')],first['session_id'])
        self.assertEqual(second['context']['servings'],4)
        self.assertEqual(second['context']['exclusions'],['garlic'])
        self.assertEqual(second['context']['diet'],'vegetarian')
        self.assertIsNotNone(second['result'],second)
        self.assertTrue(second['result']['recipes'])
        self.assertTrue(all(r['requested_servings']==4 for r in second['result']['recipes']))
    def test_sessions_are_isolated_and_reset(self):
        a=self.run_turn('Potatoes please',[call('update_context',ingredients=['new potato']),call('respond',message='For how many?')])
        b=self.run_turn('Hello',[call('respond',message='What ingredients do you have?')])
        self.assertEqual(b['context']['ingredients'],[])
        self.store.delete(a['session_id'])
        with self.assertRaises(ValueError):self.store.snapshot(a['session_id'])
    def test_invalid_update_does_not_destroy_context(self):
        r=self.run_turn('new potato',[
            call('update_context',ingredients=['new potato']),call('update_context',servings=-1),
            call('respond',message='How many portions?')])
        self.assertEqual(r['context']['ingredients'],['new potato'])
        self.assertEqual(r['context']['servings'],2)
    def test_memory_is_passed_to_next_model_call(self):
        a=self.run_turn('I avoid garlic',[call('update_context',exclusions=['garlic']),call('respond',message='Noted.')])
        captured=[]
        def reply(history):
            captured.extend(history)
            return call('respond',message='You asked to avoid garlic.')
        run_chat({'session_id':a['session_id'],'message':'What do I avoid?'},store=self.store,model=reply,verifier=lambda *args: True)
        self.assertIn('garlic',json.dumps(captured))
        self.assertIn('I avoid garlic',json.dumps(captured))
    def test_expired_session_is_not_silently_replaced(self):
        s=ChatStore(ttl=-1); token=s.create()
        with self.assertRaises(ValueError):s.snapshot(token)
    def test_provider_error_preserves_previous_context(self):
        a=self.run_turn('Potatoes',[call('update_context',ingredients=['new potato']),call('respond',message='Noted.')])
        def fail(h):raise RuntimeError('offline')
        r=run_chat({'session_id':a['session_id'],'message':'Find recipes'},store=self.store,model=fail,verifier=lambda *args: True)
        self.assertEqual(r['status'],'error')
        self.assertEqual(r['context']['ingredients'],['new potato'])
    def test_no_invented_recipe_ids(self):
        r=self.run_turn('Show fake recipe',[call('get_recipe_details',recipe_id='FAKE'),call('respond',message='I could not find that recipe.')])
        self.assertIsNone(r['result'])
    def test_context_change_clears_stale_results(self):
        a=self.run_turn('Potatoes with partial matches',[call('update_context',ingredients=['new potato'],match_mode='some'),call('search_recipes'),call('respond',message='Found recipes.')])
        b=self.run_turn('Now vegetarian',[call('update_context',diet='vegetarian'),call('respond',message='Preference updated.')],a['session_id'])
        self.assertIsNone(b['result'])

    def test_first_recipe_search_requires_exact_or_partial_choice(self):
        result=self.run_turn('I have chicken, garlic, and olive oil',[
            call('update_context',ingredients=['chicken','garlic','olive oil']),
            call('search_recipes'),
            call('respond',message='Would you like recipes using all of those ingredients, or recipes using some of them with missing groceries shown?')])
        self.assertIsNone(result['result'])
        self.assertFalse(result['matching_preference_confirmed'])
        self.assertIn('all of those ingredients',result['reply'])

    def test_exact_choice_is_remembered_before_searching(self):
        first=self.run_turn('I have new potato, olive oil, scallion, black pepper, and dried dill',[
            call('update_context',ingredients=['new potato','olive oil','scallion','black pepper','dried dill']),
            call('respond',message='Do you want an exact match or partial matches?')])
        second=self.run_turn('Exact match only',[
            call('update_context',match_mode='all'),call('search_recipes'),
            call('respond',message='Here are the exact matches.')],first['session_id'])
        self.assertTrue(second['matching_preference_confirmed'])
        self.assertEqual(second['context']['match_mode'],'all')
        self.assertTrue(second['result']['recipes'])
        self.assertTrue(all(not recipe['missing'] for recipe in second['result']['recipes']))

    def test_partial_choice_recovers_when_model_searches_before_saving_choice(self):
        first=self.run_turn('I have chicken, garlic, and tomatoes. Find recipes for three dinners for two people.',[
            call('update_context',ingredients=['chicken','garlic','tomatoes'],servings=2),
            call('respond',message='Do you want an exact match using every listed ingredient, or a partial match using some listed ingredients with missing groceries shown?')])
        attempts=[]
        def recovering_model(history):
            attempts.append(history)
            if len(attempts)==1:
                return call('search_recipes')
            feedback=json.loads(history[-1]['content']).get('error','')
            if 'call update_context with match_mode' in feedback:
                return call('update_context',match_mode='some')
            if len(attempts)==3:
                return call('search_recipes')
            return call('respond',message='Matching recipes are displayed below.')
        found={'id':'r1','title':'Chicken dinner','match_percent':50,'pantry_match_percent':100,
            'sodium_mg_per_serving':200,'vegetarian':False,'matched':['chicken'],'missing':['onion']}
        search_result={'count':1,'total_count':1,'recipes':[found],'applied_view':{}}
        with patch.object(chat_module,'search_context',return_value=search_result):
            second=run_chat({'session_id':first['session_id'],'message':'Additional items are fine.'},
                store=self.store,model=recovering_model,verifier=lambda *args:True)
        self.assertEqual(second['status'],'completed')
        self.assertEqual(second['context']['match_mode'],'some')
        self.assertTrue(second['matching_preference_confirmed'])
        self.assertIsNotNone(second['result'],second)
        self.assertTrue(second['result']['recipes'])
        self.assertLessEqual(len(attempts),4)

    def test_no_exact_match_stays_exact_until_user_accepts_partial_options(self):
        exact=self.run_turn('Use an exact match for chicken, garlic, and olive oil',[
            call('update_context',ingredients=['chicken','garlic','olive oil'],match_mode='all'),
            call('search_recipes'),
            call('respond',message='There are no exact matches. Would you like recipes using some of those ingredients instead?')])
        self.assertEqual(exact['context']['match_mode'],'all')
        self.assertEqual(exact['result']['count'],0)
        partial=self.run_turn('Yes, show partial alternatives',[
            call('update_context',match_mode='some'),call('search_recipes'),
            call('respond',message='Here are the partial alternatives.')],exact['session_id'])
        self.assertEqual(partial['context']['match_mode'],'some')
        self.assertTrue(partial['result']['recipes'])

    def test_unsupported_reply_is_rejected(self):
        r=run_chat({'message':'Tell me the sodium'},store=self.store,
            model=model(call('respond',message='This has zero sodium.')),
            verifier=lambda *args: False)
        self.assertNotIn('zero sodium',r['reply'])

    def test_rejected_match_question_receives_actionable_repair_feedback(self):
        attempts=[]
        def repairing_model(history):
            attempts.append(history)
            if len(attempts)==1:
                return call('update_context',ingredients=['chicken','garlic','tomatoes'])
            feedback=history[-1].get('content','') if history[-1].get('role')=='tool' else ''
            if 'partial as some listed ingredients with missing groceries shown' in feedback:
                return call('respond',message='Do you want an exact match using every listed ingredient, or a partial match using some listed ingredients with missing groceries shown?')
            return call('respond',message='Would you like exact or partial?')
        result=run_chat({'message':'Give me a recipe for chicken, garlic, and tomatoes, and plan it as a 3-meal plan.'},
            store=self.store,model=repairing_model,
            verifier=lambda reply,*args:'some listed ingredients with missing groceries shown' in reply)
        self.assertEqual(result['status'],'completed')
        self.assertIn('some listed ingredients',result['reply'])
        self.assertLessEqual(len(attempts),3)

    def test_match_clarification_keeps_pending_plan_size_in_conversation(self):
        prompt=(chat_module.ROOT/'prompts/chat_verify_v2.txt').read_text(encoding='utf-8-sig')
        self.assertIn('requested number of meals or days is a pending plan instruction',prompt)
        self.assertIn('does not need a structured context field before the matching clarification',prompt)

    def test_clear_match_question_does_not_depend_on_nondeterministic_ai_judge(self):
        def verifier_must_not_run(*args):
            raise AssertionError('AI verifier should not judge the structured match-choice question')
        result=run_chat({'message':'Give me a recipe for chicken, garlic, and tomatoes, and plan three meals.'},
            store=self.store,
            model=model(
                call('update_context',ingredients=['chicken','garlic','tomatoes']),
                call('respond',message='Do you want an exact match using every listed ingredient, or a partial match using some listed ingredients with missing groceries shown?')),
            verifier=verifier_must_not_run)
        self.assertEqual(result['status'],'completed')
        self.assertIn('partial match',result['reply'])

    def test_invalid_reply_on_last_turn_is_not_accepted(self):
        steps=[call('update_context',servings=2)]*9+[call('respond',message='x'*2001)]
        r=self.run_turn('Hello',steps)
        self.assertEqual(r['status'],'limit_reached')
        self.assertLess(len(r['reply']),2001)
    def test_plain_model_reply_uses_same_verification(self):
        r=run_chat({'message':'Hello'},store=self.store,
            model=model({'role':'assistant','content':'What ingredients do you have?','tool_calls':[]}),
            verifier=lambda *args: True)
        self.assertEqual(r['reply'],'What ingredients do you have?')

    def test_full_transcript_survives_long_chat(self):
        a=self.run_turn('I avoid garlic',[call('update_context',exclusions=['garlic']),call('respond',message='Noted.')])
        for i in range(18):
            a=run_chat({'session_id':a['session_id'],'message':f'Followup {i}'},store=self.store,
                model=model(call('respond',message='Ready.')),verifier=lambda *args:True,summarizer=lambda messages,previous:[])
        self.assertEqual(len(a['messages']),38)
        self.assertEqual(a['messages'][0]['content'],'I avoid garlic')
        self.assertEqual(a['context']['exclusions'],['garlic'])
        self.assertEqual(len(self.store.snapshot(a['session_id'])['messages']),38)
    def test_old_messages_can_be_retrieved(self):
        a=self.run_turn('I prefer mild flavors',[call('respond',message='Noted.')])
        for i in range(14):
            a=run_chat({'session_id':a['session_id'],'message':f'Question {i}'},store=self.store,model=model(call('respond',message='Ready.')),verifier=lambda *args:True,summarizer=lambda m,p:[])
        seen=[]
        steps=iter([call('recall_conversation',query='mild',offset=0),call('respond',message='You prefer mild flavors.')])
        def inspect(h):seen.extend(h);return next(steps)
        run_chat({'session_id':a['session_id'],'message':'What flavors did I prefer?'},store=self.store,model=inspect,verifier=lambda *args:True,summarizer=lambda m,p:[])
        self.assertTrue(any(m['role']=='tool' and 'mild flavors' in m['content'] for m in seen))
    def test_summary_rejects_invented_memory(self):
        from dash_app.chat import checked_memory
        messages=[{'role':'user','content':'I prefer mild flavors'}]
        self.assertEqual(checked_memory([{'message_index':0,'quote':'I like hot peppers'}],messages),[])
        self.assertEqual(checked_memory([{'message_index':0,'quote':'mild flavors'}],messages),[{'message_index':0,'quote':'mild flavors'}])

    def test_match_filter_changes_visible_results_and_persists(self):
        a=self.run_turn('I have olive oil; partial matches are fine', [call('update_context',ingredients=['olive oil'],match_mode='some'),call('search_recipes'),call('respond',message='Recipes are below.')])
        b=self.run_turn('Only over 20 percent', [call('query_recipe_results',filters=[{'field':'match_percent','operator':'gt','value':20}]),call('respond',message='Filtered recipes are below.')],a['session_id'])
        self.assertEqual(b['status'],'completed')
        self.assertTrue(all(r['match_percent']>20 for r in b['result']['recipes']))
        c=self.run_turn('Make it four', [call('update_context',servings=4),call('search_recipes'),call('respond',message='Updated.')],a['session_id'])
        self.assertEqual(c['result_view']['filters'][0]['value'],20)
        self.assertTrue(all(r['match_percent']>20 for r in c['result']['recipes']))
    def test_match_filter_boundary(self):
        from dash_app.chat import filter_matches
        rows=[{'match_percent':19.9},{'match_percent':20},{'match_percent':20.1}]
        self.assertEqual(len(filter_matches(rows,20,False)),1)
        self.assertEqual(len(filter_matches(rows,20,True)),2)

    def test_new_chat_has_no_fixed_filter_or_result_limit(self):
        token=self.store.create(); state=self.store.snapshot(token)
        self.assertEqual(state['result_view']['filters'],[])
        self.assertIsNone(state['result_view']['limit'])

    def test_followup_can_show_only_recipes_with_named_ingredient(self):
        a=self.run_turn('I have chicken, garlic, and olive oil', [
            call('update_context',ingredients=['chicken','garlic','olive oil'],match_mode='some'),call('search_recipes'),call('respond',message='Recipes are below.')])
        b=self.run_turn('Show me only chicken recipes', [
            call('query_recipe_results',include_ingredients=['chicken']),call('respond',message='Chicken recipes are displayed below.')],a['session_id'])
        self.assertTrue(b['result']['recipes'])
        self.assertEqual(b['result_view']['include_ingredients'],['chicken'])
        self.assertTrue(all('chicken' in recipe['title'].casefold() or
                            any('chicken' in ingredient['name'].casefold() for ingredient in recipe['ingredients'])
                            for recipe in b['result']['recipes']))

    def test_followup_can_exclude_recipes_by_title_or_ingredient(self):
        a=self.run_turn('I have olive oil', [
            call('update_context',ingredients=['olive oil'],match_mode='some'),call('search_recipes'),call('respond',message='Recipes are below.')])
        terms=['fish','salmon','tuna','cod','snapper','tilapia']
        b=run_chat({'session_id':a['session_id'],'message':'Remove recipes with fish'},store=self.store,
            model=model(call('query_recipe_results',exclude_ingredients=terms),
                        call('respond',message='Recipes containing fish are removed.')),
            verifier=lambda *args:True,
            filter_reviewer=lambda *args:{'exclude_recipe_ids':[]})
        self.assertEqual(b['result_view']['exclude_ingredients'],terms)
        self.assertTrue(all(not any(term in (' '.join([recipe['title']]+[i['name'] for i in recipe['ingredients']])).casefold()
                                    for term in terms) for recipe in b['result']['recipes']))

    def test_filter_judge_can_remove_semantic_category_members_without_fixed_food_map(self):
        a=self.run_turn('I have olive oil', [
            call('update_context',ingredients=['olive oil'],match_mode='some'),call('search_recipes'),call('respond',message='Recipes are below.')])
        candidate_id=a['result']['recipes'][0]['id']
        b=run_chat({'session_id':a['session_id'],'message':'Remove a broad food category'},store=self.store,
            model=model(call('query_recipe_results',exclude_ingredients=['category']),call('respond',message='Filtered.')),
            verifier=lambda *args:True,
            filter_reviewer=lambda *args:{'exclude_recipe_ids':[candidate_id]})
        self.assertIn(candidate_id,b['result_view']['exclude_recipe_ids'])
        self.assertNotIn(candidate_id,[recipe['id'] for recipe in b['result']['recipes']])

    def test_llm_can_build_and_refine_weekly_plan(self):
        search=self.run_turn('Show partial chicken and potato recipes',[
            call('update_context',ingredients=['chicken','new potato'],match_mode='some'),call('search_recipes'),call('respond',message='Choose recipes below.')])
        from dash_app.chat import set_recipe_selection
        set_recipe_selection(self.store,search['session_id'],'R01',True)
        set_recipe_selection(self.store,search['session_id'],'R04',True)
        a=self.run_turn('Plan my two selected meals',[
            call('set_weekly_plan',name='My week',sodium_target_mg=2300,entries=[
                {'day':'Monday','meal':'lunch','recipe_id':'R01','servings':2},
                {'day':'Tuesday','meal':'dinner','recipe_id':'R04','servings':3}]),
            call('respond',message='Your draft weekly plan is ready.')],search['session_id'])
        self.assertEqual(len(a['plan']['entries']),2)
        self.assertTrue(a['grocery_list'])
        self.assertEqual(a['nutrition_summary']['days']['Monday']['sodium_mg'],179)
        b=self.run_turn('Add a prep timeline',[
            call('set_prep_timeline',tasks=[{'title':'Prepare the chicken', 'sources':[{'recipe_id':'R01','step_number':1}]}]),
            call('respond',message='The prep timeline is ready.')],a['session_id'])
        self.assertEqual(b['prep_timeline'][0]['sources'][0]['recipe_id'],'R01')

    def test_search_results_are_candidates_not_selected_recipes(self):
        result=self.run_turn('Show partial chicken recipes',[
            call('update_context',ingredients=['chicken'],match_mode='some'),call('search_recipes'),call('respond',message='Choose recipes below.')])
        self.assertGreater(result['result']['count'],0)
        self.assertEqual(result['selected_recipe_ids'],[])

    def test_weekly_plan_rejects_unselected_recipe(self):
        result=self.run_turn('Plan a meal',[
            call('set_weekly_plan',name='My week',entries=[{'day':'Monday','meal':'dinner','recipe_id':'R01','servings':2}]),
            call('respond',message='Please select a recipe first.')])
        self.assertIsNone(result['plan'])

    def test_user_can_select_and_remove_recipe_candidate(self):
        result=self.run_turn('Show partial chicken recipes',[
            call('update_context',ingredients=['chicken'],match_mode='some'),call('search_recipes'),call('respond',message='Choose recipes below.')])
        from dash_app.chat import set_recipe_selection
        selected=set_recipe_selection(self.store,result['session_id'],'R01',True)
        self.assertEqual(selected['selected_recipe_ids'],['R01'])
        cleared=set_recipe_selection(self.store,result['session_id'],'R01',False)
        self.assertEqual(cleared['selected_recipe_ids'],[])

    def test_selected_recipe_details_are_passed_to_the_agent(self):
        result=self.run_turn('Show partial chicken recipes',[
            call('update_context',ingredients=['chicken'],match_mode='some'),call('search_recipes'),call('respond',message='Choose recipes below.')])
        from dash_app.chat import set_recipe_selection
        set_recipe_selection(self.store,result['session_id'],'R01',True)
        observed={}
        def inspect_context(history):
            observed.update(json.loads(history[1]['content']))
            return call('respond',message='Which day should I use for Chicken Salad?')
        run_chat({'session_id':result['session_id'],'message':'Build my selected recipe'},store=self.store,
            model=inspect_context,verifier=lambda *args:True)
        self.assertEqual(observed['selected_recipes'],[{'id':'R01','title':'Chicken Salad'}])

    def test_reply_about_an_existing_selection_is_verified(self):
        result=self.run_turn('Show partial chicken recipes',[
            call('update_context',ingredients=['chicken'],match_mode='some'),call('search_recipes'),call('respond',message='Choose recipes below.')])
        from dash_app.chat import set_recipe_selection
        set_recipe_selection(self.store,result['session_id'],'R01',True)
        verified=[]
        run_chat({'session_id':result['session_id'],'message':'Build my selected recipe'},store=self.store,
            model=model(call('respond',message='You have not selected a recipe yet. Which recipe do you want?')),
            verifier=lambda *args:verified.append(True) or True)
        self.assertEqual(verified,[True])

    def test_loading_saved_plan_restores_selected_recipes(self):
        from dash_app.chat import open_saved_plan
        saved={'plan_id':'plan-1','name':'Last week','status':'draft','entries':[
            {'day':'Monday','meal':'dinner','recipe_id':'R01','title':'Chicken Salad','servings':2,
             'base_servings':5,'source_url':'/source/test.pdf','sodium_mg_per_serving':179,
             'steps':['Prepare chicken.'],'scaled_ingredients':[]}]}
        result=open_saved_plan(self.store,None,'plan-1',loader=lambda plan_id:saved)
        self.assertEqual(result['saved_plan_id'],'plan-1')
        self.assertEqual(result['selected_recipe_ids'],['R01'])
        self.assertEqual(result['plan']['name'],'Last week')

    def test_prep_generation_can_read_recipe_details_from_reopened_plan(self):
        from dash_app.chat import open_saved_plan
        expected_steps=['Use cooked, cubed, chilled chicken breast.',
                        'Combine the remaining ingredients, fold in the chicken, and mix.']
        saved={'plan_id':'plan-1','name':'Last week','status':'draft','entries':[
            {'day':'Monday','meal':'dinner','recipe_id':'R01','title':'Chicken Salad','servings':2,
             'base_servings':5,'source_url':'/source/test.pdf','sodium_mg_per_serving':179,
             'steps':expected_steps,'scaled_ingredients':[]}]}
        opened=open_saved_plan(self.store,None,'plan-1',loader=lambda plan_id:saved)
        observed=[]
        steps=iter([call('get_recipe_details',recipe_id='R01'),
                    call('set_prep_timeline',tasks=[{'title':'Prepare the chicken','sources':[{'recipe_id':'R01','step_number':1}]}]),
                    call('respond',message='Your prep timeline is ready.')])
        def inspect(history):
            if history[-1].get('role')=='tool':observed.append(json.loads(history[-1]['content']))
            return next(steps)
        result=run_chat({'session_id':opened['session_id'],'message':'Generate a prep timeline for my current weekly plan'},
            store=self.store,model=inspect,verifier=lambda *args:True)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(observed[0]['steps'],expected_steps)
        self.assertEqual(result['prep_timeline'][0]['source_texts'],[expected_steps[0]])

    def test_identical_recipe_search_is_reused_during_session(self):
        with patch.object(chat_module,'search_context',wraps=chat_module.search_context) as search:
            first=self.run_turn('Show partial chicken recipes',[
                call('update_context',ingredients=['chicken'],match_mode='some'),call('search_recipes'),call('respond',message='Recipes are below.')])
            self.run_turn('Show those matches again',[call('search_recipes'),call('respond',message='Recipes are below.')],first['session_id'])
        self.assertEqual(search.call_count,1)

    def test_context_change_invalidates_recipe_search_cache(self):
        with patch.object(chat_module,'search_context',wraps=chat_module.search_context) as search:
            first=self.run_turn('Show partial chicken recipes',[
                call('update_context',ingredients=['chicken'],match_mode='some'),call('search_recipes'),call('respond',message='Recipes are below.')])
            self.run_turn('Make it four portions',[call('update_context',servings=4),call('search_recipes'),call('respond',message='Updated.')],first['session_id'])
        self.assertEqual(search.call_count,2)

    def test_identical_guidance_query_is_reused_during_session(self):
        calls=[]
        def retrieval(query):calls.append(query);return ([{'id':'g1','text':'Use vegetables.','source_url':'/source/guide.pdf'}],'test')
        first=run_chat({'message':'What does DASH say about vegetables?'},store=self.store,
            model=model(call('retrieve_guidance',query='vegetables'),call('respond',message='The guide recommends vegetables.')),
            retrieval=retrieval,verifier=lambda *args:True)
        run_chat({'session_id':first['session_id'],'message':'Show that vegetable guidance again'},store=self.store,
            model=model(call('retrieve_guidance',query='vegetables'),call('respond',message='The guide recommends vegetables.')),
            retrieval=retrieval,verifier=lambda *args:True)
        self.assertEqual(calls,['vegetables'])

    def test_simple_clarification_skips_expensive_reply_verifier(self):
        def verifier_must_not_run(*args):raise AssertionError('simple clarification should not need evidence verification')
        result=run_chat({'message':'Help me plan'},store=self.store,
            model=model(call('respond',message='Which ingredients do you have?')),verifier=verifier_must_not_run)
        self.assertEqual(result['reply'],'Which ingredients do you have?')

    def test_repeated_no_progress_tool_call_receives_stop_feedback(self):
        seen=[];steps=iter([call('inspect_catalog',query='chicken'),call('inspect_catalog',query='chicken'),call('respond',message='I found the catalog information.')])
        def repeating(history):seen.append(json.loads(json.dumps(history)));return next(steps)
        result=run_chat({'message':'Inspect chicken'},store=self.store,model=repeating,verifier=lambda *args:True)
        tool_messages=[m['content'] for history in seen for m in history if m.get('role')=='tool']
        self.assertTrue(any('repeated without making progress' in message for message in tool_messages))
        self.assertEqual(result['status'],'completed')

    def test_completed_filter_is_not_reported_as_a_timeout_when_reply_budget_ends(self):
        first=self.run_turn('Show partial chicken recipes',[
            call('update_context',ingredients=['chicken'],match_mode='some'),call('search_recipes'),call('respond',message='Recipes are below.')])
        calls=[call('query_recipe_results',filters=[{'field':'vegetarian','operator':'eq','value':False}],
                    sort_by='match_percent',direction='desc',limit=3)]
        calls.extend([{'role':'assistant','content':None,'tool_calls':[]} for _ in range(9)])
        result=run_chat({'session_id':first['session_id'],'message':'Show the top three non-vegetarian recipes'},
            store=self.store,model=model(*calls),verifier=lambda *args:True)
        self.assertEqual(result['status'],'completed')
        self.assertLessEqual(result['result']['count'],3)
        self.assertEqual(result['result_view']['limit'],3)
        self.assertTrue(all(row['vegetarian'] is False for row in result['result']['recipes']))
        self.assertNotIn('couldn’t finish',result['reply'])

    def test_completed_plan_and_prep_are_not_reported_as_a_timeout(self):
        search=self.run_turn('Show partial chicken and potato recipes',[
            call('update_context',ingredients=['chicken','new potato'],match_mode='some'),call('search_recipes'),call('respond',message='Choose recipes below.')])
        from dash_app.chat import set_recipe_selection
        set_recipe_selection(self.store,search['session_id'],'R01',True)
        calls=[
            call('set_weekly_plan',name='My week',sodium_target_mg=2300,entries=[
                {'day':'Monday','meal':'dinner','recipe_id':'R01','servings':2}]),
            call('set_prep_timeline',tasks=[{'title':'Prepare the chicken','sources':[{'recipe_id':'R01','step_number':1}]}]),
        ]
        calls.extend([{'role':'assistant','content':None,'tool_calls':[]} for _ in range(8)])
        result=run_chat({'session_id':search['session_id'],'message':'Create my weekly plan and prep timeline'},
            store=self.store,model=model(*calls),verifier=lambda *args:True)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(result['plan']['entries']),1)
        self.assertEqual(len(result['prep_timeline']),1)
        self.assertNotIn('couldn’t finish',result['reply'])
