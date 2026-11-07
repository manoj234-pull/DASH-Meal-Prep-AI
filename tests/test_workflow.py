import copy
import unittest
from dash_app.core import get_recipe_details,search_recipes,validate_results,ingredient_match
from dash_app.providers import validate_extractive_notes


class WorkflowTests(unittest.TestCase):
    def test_source_id_alone_cannot_pass_modified_nutrition(self):
        q={'ingredients':['new potato'],'servings':2}
        r=search_recipes(q)
        r[0]['sodium_mg_per_serving']=0
        self.assertTrue(validate_results(r,q))

    def test_citation_does_not_accept_unsupported_quote(self):
        notes=[{'recipe_id':'R04','guidance_id':'G1','quote':'This recipe cures high blood pressure immediately.'}]
        with self.assertRaises(ValueError): validate_extractive_notes(notes,[{'id':'R04'}],[{'id':'G1','text':'Choose a variety of foods.'}])

    def test_exact_quote_is_traceable(self):
        quote='Choose a variety of foods from the recommended food groups.'
        n=[{'recipe_id':'R04','guidance_id':'G1','quote':quote}]
        self.assertEqual(validate_extractive_notes(n,[{'id':'R04'}],[{'id':'G1','text':quote}]),n)

    def test_source_ingredients_have_no_assumed_staples(self):
        r=get_recipe_details('R04');m=ingredient_match(r,['new potato'])
        self.assertEqual(m['match_percent'],20)
        self.assertIn('olive oil',m['missing'])



if __name__=='__main__': unittest.main()

from tests.catalog_fixture import catalog_fixture
def setUpModule():
    global _catalog_context
    _catalog_context=catalog_fixture();_catalog_context.__enter__()
def tearDownModule():_catalog_context.__exit__(None,None,None)
