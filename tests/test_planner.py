import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.catalog_fixture import catalog_fixture


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=catalog_fixture();self.fixture.__enter__()
        from dash_app import planner
        self.planner=planner
        self.tmp=tempfile.TemporaryDirectory(dir=planner.ROOT/'reports')
        self.db=Path(self.tmp.name)/'plans.sqlite'

    def tearDown(self):
        self.tmp.cleanup();self.fixture.__exit__(None,None,None)

    def sample(self):
        return {'name':'My week','sodium_target_mg':2300,'entries':[
            {'day':'Monday','meal':'lunch','recipe_id':'R01','servings':2},
            {'day':'Tuesday','meal':'dinner','recipe_id':'R04','servings':3}]}

    def test_builds_plan_from_source_recipes(self):
        plan=self.planner.build_plan(self.sample())
        self.assertEqual(len(plan['entries']),2)
        self.assertEqual(plan['entries'][0]['title'],'Chicken Salad')
        self.assertEqual(plan['entries'][0]['servings'],2)

    def test_rejects_duplicate_day_and_meal(self):
        payload=self.sample();payload['entries'][1]['day']='Monday';payload['entries'][1]['meal']='lunch'
        with self.assertRaises(ValueError):self.planner.build_plan(payload)

    def test_grocery_list_combines_same_units(self):
        plan=self.planner.build_plan(self.sample())
        groceries=self.planner.build_grocery_list(plan)
        keys={(x['name'],x['unit']) for x in groceries}
        self.assertIn(('black pepper','tsp'),keys)

    def test_daily_sodium_uses_source_per_serving(self):
        plan=self.planner.build_plan(self.sample())
        summary=self.planner.plan_nutrition_summary(plan)
        self.assertEqual(summary['days']['Monday']['sodium_mg'],179)
        self.assertEqual(summary['days']['Tuesday']['sodium_mg'],17)
        self.assertTrue(summary['days']['Monday']['within_selected_target'])

    def test_prep_timeline_requires_real_source_steps(self):
        plan=self.planner.build_plan(self.sample())
        timeline=self.planner.validate_prep_timeline(plan,[{'title':'Prepare chicken','sources':[{'recipe_id':'R01','step_number':1}]}])
        self.assertEqual(timeline[0]['source_texts'][0],plan['entries'][0]['steps'][0])
        with self.assertRaises(ValueError):self.planner.validate_prep_timeline(plan,[{'title':'Invented','sources':[{'recipe_id':'R01','step_number':99}]}])

    def test_saved_plan_can_be_loaded(self):
        plan=self.planner.build_plan(self.sample())
        saved=self.planner.save_plan(plan,database=self.db)
        loaded=self.planner.load_plan(saved['plan_id'],database=self.db)
        self.assertEqual(loaded['name'],'My week')

    def test_autosaved_draft_survives_new_store(self):
        plan=self.planner.build_plan(self.sample())
        saved=self.planner.save_plan(plan,status='draft',profile_id='local-test',database=self.db)
        loaded=self.planner.load_plan(saved['plan_id'],profile_id='local-test',database=self.db)
        self.assertEqual(loaded['status'],'draft')
        self.assertEqual(len(loaded['entries']),2)

    def test_duplicate_plan_gets_new_identity(self):
        saved=self.planner.save_plan(self.planner.build_plan(self.sample()),profile_id='local-test',database=self.db)
        duplicate=self.planner.duplicate_plan(saved['plan_id'],profile_id='local-test',database=self.db)
        self.assertNotEqual(duplicate['plan_id'],saved['plan_id'])
        self.assertEqual(duplicate['entries'],saved['entries'])
        self.assertEqual(duplicate['status'],'draft')

    def test_list_plans_orders_recent_first(self):
        first=self.planner.save_plan(self.planner.build_plan(self.sample()),profile_id='local-test',database=self.db)
        second_plan=self.planner.build_plan({**self.sample(),'name':'Next week'})
        second=self.planner.save_plan(second_plan,profile_id='local-test',database=self.db)
        rows=self.planner.list_plans(profile_id='local-test',database=self.db)
        self.assertEqual([row['plan_id'] for row in rows],[second['plan_id'],first['plan_id']])

    def test_rename_preserves_entries(self):
        saved=self.planner.save_plan(self.planner.build_plan(self.sample()),profile_id='local-test',database=self.db)
        renamed=self.planner.rename_plan(saved['plan_id'],'Family favorites',profile_id='local-test',database=self.db)
        self.assertEqual(renamed['name'],'Family favorites')
        self.assertEqual(renamed['entries'],saved['entries'])

    def test_delete_removes_only_target_plan(self):
        first=self.planner.save_plan(self.planner.build_plan(self.sample()),profile_id='local-test',database=self.db)
        second=self.planner.save_plan(self.planner.build_plan({**self.sample(),'name':'Keep me'}),profile_id='local-test',database=self.db)
        self.planner.delete_plan(first['plan_id'],profile_id='local-test',database=self.db)
        self.assertEqual([row['plan_id'] for row in self.planner.list_plans('local-test',self.db)],[second['plan_id']])
        with self.assertRaises(ValueError):self.planner.load_plan(first['plan_id'],'local-test',self.db)


if __name__=='__main__':unittest.main()
