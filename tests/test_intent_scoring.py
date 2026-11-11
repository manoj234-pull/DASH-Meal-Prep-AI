import unittest
from unittest.mock import patch
from scripts.evaluate_chat_intents import assess

class IntentScoringTests(unittest.TestCase):
    def test_claim_without_display_change_fails(self):
        rows=[{'id':'low','match_percent':10,'sodium_mg_per_serving':20,'requested_servings':2}, {'id':'high','match_percent':40,'sodium_mg_per_serving':30,'requested_servings':2}]
        response={'status':'completed','context':{'servings':2},'result':{'count':2,'total_count':2,'recipes':rows},'result_view':{}}
        with patch('scripts.evaluate_chat_intents.search_recipes',return_value=rows):
            self.assertTrue(assess(response,{'min_match':20,'strict':True}))
    def test_empty_result_does_not_pass_filter_check(self):
        response={'status':'completed','context':{'servings':2},'result':{'count':0,'total_count':0,'recipes':[]},'result_view':{}}
        with patch('scripts.evaluate_chat_intents.search_recipes',return_value=[]):
            self.assertIn('Expected actual recipe results',assess(response,{'min_match':20,'strict':True}))
    def test_changed_preferences_fail(self):
        response={'status':'completed','context':{'diet':'any','servings':2},'result':None,'result_view':{}}
        self.assertIn('Incorrect remembered diet',assess(response,{'diet':'vegetarian'}))

    def test_remembered_exclusion_is_not_enough(self):
        response={'status':'completed','context':{'servings':2,'exclusions':['mushrooms']},'result':{'recipes':[{'id':'bad','requested_servings':2,'ingredients':[{'name':'mushrooms, sliced'}]}]},'result_view':{}}
        self.assertTrue(assess(response,{'exclusions':['mushrooms'],'forbidden_ingredient_words':['mushroom','mushrooms']}))

    def test_weekly_plan_requires_plan_grocery_and_nutrition_outputs(self):
        response={'status':'completed','reply':'Plan ready','context':{'servings':2},'result':None,'result_view':{},
            'plan':{'entries':[{'day':'Monday'},{'day':'Tuesday'}]},
            'grocery_list':[{'name':'garlic'}],
            'nutrition_summary':{'days':{'Monday':{},'Tuesday':{}}}}
        expected={'plan_entries':2,'grocery_nonempty':True,'nutrition_days':2}
        self.assertEqual(assess(response,expected),[])
        response['grocery_list']=[]
        self.assertIn('Weekly plan did not produce a grocery list',assess(response,expected))

    def test_curly_apostrophe_refusal_is_recognized(self):
        response={'status':'completed','reply':'I can’t help with that.','context':{'servings':2,'ingredients':[]},'result':None,'result_view':{}}
        self.assertEqual(assess(response,{'reply_contains_any':["can't",'cannot']}),[])
