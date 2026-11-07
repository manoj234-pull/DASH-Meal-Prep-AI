import unittest
from dash_app.ingestion import quantity, validate_recipe
class IngestionTests(unittest.TestCase):
    def test_fraction(self):self.assertEqual(quantity('1 1/2'),1.5)
    def test_missing_amount_not_invented(self):self.assertIsNone(quantity(None))
    def test_unanchored_recipe_is_rejected(self):
        with self.assertRaises(ValueError):validate_recipe({'title':'Invented soup'},'Unrelated PDF text',{})

    def test_missing_database_never_imports_json(self):
        from unittest.mock import patch
        from pathlib import Path
        from dash_app import core
        with patch.object(core,'DB',Path('not-an-ingested-catalog.sqlite')):
            with self.assertRaises(RuntimeError):core.ensure_current()

    def test_source_values_are_extracted_not_recipe_defaults(self):
        raw={'title':'Test dish','ingredients':[{'name':'test grain','quantity_text':'1/2','unit':'cup','evidence':'1/2 cup test grain'}],'steps':['Mix and serve.'],'servings_text':'3','servings_evidence':'Makes 3 servings','sodium_text':None,'calories_text':None,'vegetarian':None}
        source={'id':'page-x','document_id':'document-x','source_file':'test.pdf','page':7,'sha256':'testhash'}
        recipe=validate_recipe(raw,'Test dish 1/2 cup test grain Mix and serve. Makes 3 servings',source)
        self.assertEqual(recipe['ingredients'][0]['quantity'],.5)
        self.assertEqual(recipe['base_servings'],3)
        self.assertEqual(recipe['source_url'],'/source/document-x.pdf#page=7')
        self.assertIsNone(recipe['sodium_mg_per_serving'])

    def test_invalid_numeric_support_stays_unknown(self):
        raw={'title':'Test dish','ingredients':[{'name':'grain','quantity_text':'1','unit':'cup','evidence':'1 cup grain'}],'steps':[],'servings_text':'99','servings_evidence':'Invented servings'}
        source={'id':'page-x','document_id':'document-x','source_file':'test.pdf','page':7,'sha256':'testhash'}
        self.assertIsNone(validate_recipe(raw,'Test dish 1 cup grain',source)['base_servings'])
