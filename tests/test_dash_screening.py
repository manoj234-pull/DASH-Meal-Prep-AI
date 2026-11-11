import unittest
from dash_app.dash_screening import screen, check_source_facts
class ScreeningTests(unittest.TestCase):
 def valid(self):return {'base_servings':4,'ingredients':[{'quantity':1,'name':'beans'}],'steps':['Cook.'],'sodium_mg_per_serving':200,'nutrition_per_serving':{'saturated_fat_g':{'value':1}},'source_review':{'complete':True,'ingredients_suitable':True,'evidence_supported':True}}
 def test_qualifies(self):self.assertEqual(screen(self.valid())['status'],'qualified')
 def test_missing_fat_is_unknown_not_zero(self):
  r=self.valid();r['nutrition_per_serving']={};self.assertEqual(screen(r)['status'],'held')
 def test_exceeds_sodium_limit(self):
  r=self.valid();r['sodium_mg_per_serving']=601;self.assertEqual(screen(r)['status'],'excluded')
 def test_incomplete_method_cannot_pass(self):
  r=self.valid();r['source_review']['complete']=False;self.assertEqual(screen(r)['status'],'held')
 def test_unsupported_values_cannot_pass(self):
  r=self.valid();r['source_review']['evidence_supported']=False;self.assertEqual(screen(r)['status'],'held')

 def test_fraction_substring_is_not_valid_amount_support(self):
  r=self.valid();r['ingredients']=[{'name':'beans','quantity':1,'evidence':'1/4 cup beans'}]
  self.assertIn('Ingredient quantity differs from its source line',check_source_facts(r,'Makes 4 servings Sodium 200 mg Saturated Fat 1 g'))
 def test_nutrition_must_match_source_number(self):
  r=self.valid();r['ingredients']=[{'name':'beans','quantity':1,'evidence':'1 cup beans'}]
  self.assertIn('Sodium does not have one matching source value',check_source_facts(r,'Makes 4 servings Sodium 800 mg Saturated Fat 1 g'))
