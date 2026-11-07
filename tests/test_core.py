import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from dash_app.core import ingredient_match, scale_recipe, validate_request


class CoreTests(unittest.TestCase):
    def test_fraction_not_confidence(self):
        r = {'ingredients': [{'name': n, 'quantity': 1, 'unit': 'cup'} for n in ['onion', 'garlic', 'zucchini']]}
        m = ingredient_match(r, ['onion', 'garlic', 'garlic'])
        self.assertEqual(m['matched_count'], 2)
        self.assertEqual(m['required_count'], 3)
        self.assertAlmostEqual(m['match_percent'], 66.67)

    def test_scaling(self):
        r = {'base_servings': 4, 'ingredients': [{'name': 'lentils', 'quantity': 200, 'unit': 'g'}]}
        self.assertEqual(scale_recipe(r, 6)[0]['quantity'], 300)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            validate_request({'ingredients': [], 'servings': 0})

    def test_catalog_queries_current_sqlite_records(self):
        import sqlite3
        from dash_app import core
        with sqlite3.connect(core.DB) as c:
            row=json.loads(c.execute("SELECT record FROM recipes WHERE id='R01'").fetchone()[0]);row['title']='Updated golden title'
            c.execute("UPDATE recipes SET record=? WHERE id='R01'",(json.dumps(row),))
        c.close()
        self.assertEqual(core.get_recipe_details('R01')['title'],'Updated golden title')

    def test_incomplete_recipe_not_returned_in_either_match_mode(self):
        import sqlite3
        from dash_app import core
        from contextlib import closing
        original=core.get_recipe_details('R04')
        variants=[dict(original,steps=[]),dict(original,base_servings=None),dict(original,ingredients=[dict(x,quantity=None) for x in original['ingredients']])]
        try:
            for record in variants:
                with closing(sqlite3.connect(core.DB)) as c,c:
                    c.execute("UPDATE recipes SET record=? WHERE id='R04'",(json.dumps(record),))
                for mode in ('some','all'):
                    results=core.search_recipes({'ingredients':[x['name'] for x in original['ingredients']],'match_mode':mode})
                    self.assertNotIn('R04',[x['id'] for x in results])
        finally:
            with closing(sqlite3.connect(core.DB)) as c,c:
                c.execute("UPDATE recipes SET record=? WHERE id='R04'",(json.dumps(original),))


if __name__ == '__main__': unittest.main()

from tests.catalog_fixture import catalog_fixture
def setUpModule():
    global _catalog_context
    _catalog_context=catalog_fixture();_catalog_context.__enter__()
def tearDownModule():_catalog_context.__exit__(None,None,None)
