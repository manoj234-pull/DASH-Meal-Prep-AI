import unittest
from unittest.mock import patch
from dash_app.agent import run_agent, SessionStore
from tests.test_agent import call, fake

class DecisionTests(unittest.TestCase):
    def run_flow(self, ingredients, calls, **filters):
        with patch('dash_app.agent.trace'):
            return run_agent(dict(ingredients=ingredients, **filters), model=fake(calls), store=SessionStore())

    def test_model_interprets_synonym_from_catalog(self):
        r=self.run_flow(['rolled oat'], [call('inspect_catalog'), call('resolve_ingredient', ingredient='rolled oat', catalog_name='rolled oats', kind='pantry', reason='Singular form of same ingredient'), call('search_recipes'), call('finish', recipe_ids=['R07'], notes=[])])
        self.assertEqual(r['status'], 'completed')
        self.assertEqual(r['recipes'][0]['id'], 'R07')

    def test_question_not_limited_to_four_foods(self):
        r=self.run_flow(['potato'], [call('inspect_catalog'), call('ask_clarification', ingredient='potato', question='Are these new potatoes?', choices=['new potato'])])
        self.assertEqual(r['status'], 'clarification')
        self.assertEqual(r['question']['choices'], ['new potato', 'Not sure'])

    def test_model_selects_subset(self):
        r=self.run_flow(['cooked brown rice'], [call('search_recipes'), call('finish', recipe_ids=['R09'], notes=[])])
        self.assertEqual(r['status'], 'completed')
        self.assertEqual(r['agent_recommended_ids'], ['R09'])
        self.assertEqual([x['id'] for x in r['recipes']], ['R09','R05'])

    def test_no_coded_alias_conversion(self):
        from dash_app.core import canonical
        self.assertEqual(canonical('green onions'), 'green onions')

    def test_unknown_catalog_target_rejected(self):
        r=self.run_flow(['moonberry'], [call('inspect_catalog'), call('resolve_ingredient', ingredient='moonberry', catalog_name='invented food', kind='pantry', reason='guess'), call('search_recipes'), call('finish', recipe_ids=[], notes=[])])
        self.assertEqual(r['status'], 'no_match')
        self.assertTrue(any(x['step']=='resolve_ingredient' and x['status']=='rejected' for x in r['steps']))

    def test_invalid_optional_note_does_not_discard_valid_selection(self):
        r=self.run_flow(['new potato'], [call('search_recipes'),call('finish',recipe_ids=['R04'],notes=[{'recipe_id':'R04','guidance_id':'missing','quote':'Unsupported statement that must never be shown.'}])])
        self.assertEqual(r['status'],'completed')
        self.assertEqual(r['recipes'][0]['id'],'R04')
        self.assertEqual(r['notes'],[])
        self.assertTrue(any('omitted' in w for w in r['warnings']))

    def test_clarification_can_include_food_not_in_catalog(self):
        r=self.run_flow(['oil'], [call('ask_clarification', ingredient='oil', question='Which type of cooking oil do you have?', choices=['olive oil','sunflower oil','Not sure'])])
        self.assertEqual(r['status'],'clarification')
        self.assertEqual(r['question']['choices'],['olive oil','sunflower oil','Not sure'])

    def test_some_mode_shows_partial_matches_not_only_recommendation(self):
        r=self.run_flow(['new potato','olive oil','scallion','black pepper','dried dill'],[call('search_recipes'),call('finish',recipe_ids=['R04'],notes=[])],diet='vegetarian',match_mode='some')
        self.assertEqual({x['id'] for x in r['recipes']},{'R04','R03','R08','R02'})
        self.assertEqual(r['agent_recommended_ids'],['R04'])
        self.assertTrue(next(x for x in r['recipes'] if x['id']=='R03')['missing'])

from tests.catalog_fixture import catalog_fixture
def setUpModule():
    global _catalog_context
    _catalog_context=catalog_fixture();_catalog_context.__enter__()
def tearDownModule():_catalog_context.__exit__(None,None,None)
