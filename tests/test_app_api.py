import tempfile
import unittest
from pathlib import Path
from tests.catalog_fixture import catalog_fixture


class PlanApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture=catalog_fixture();self.fixture.__enter__()
        from dash_app import planner
        from app import plan_api
        self.planner=planner;self.plan_api=plan_api
        self.tmp=tempfile.TemporaryDirectory(dir=planner.ROOT/'reports')
        self.db=Path(self.tmp.name)/'plans.sqlite'
        payload={'name':'My week','entries':[{'day':'Monday','meal':'dinner','recipe_id':'R01','servings':2}]}
        self.saved=planner.save_plan(planner.build_plan(payload),database=self.db)

    def tearDown(self):
        self.tmp.cleanup();self.fixture.__exit__(None,None,None)

    def test_list_and_load_plan(self):
        listed=self.plan_api('GET','/api/plans',None,self.db)
        loaded=self.plan_api('GET',f"/api/plans/{self.saved['plan_id']}",None,self.db)
        self.assertEqual(listed['plans'][0]['plan_id'],self.saved['plan_id'])
        self.assertEqual(loaded['plan']['name'],'My week')

    def test_duplicate_rename_finalize_and_delete(self):
        copied=self.plan_api('POST',f"/api/plans/{self.saved['plan_id']}/duplicate",{},self.db)['plan']
        renamed=self.plan_api('POST',f"/api/plans/{copied['plan_id']}/rename",{'name':'Next week'},self.db)['plan']
        finalized=self.plan_api('POST',f"/api/plans/{copied['plan_id']}/finalize",{},self.db)['plan']
        self.assertEqual(renamed['name'],'Next week')
        self.assertEqual(finalized['status'],'finalized')
        self.assertEqual(self.plan_api('POST',f"/api/plans/{copied['plan_id']}/delete",{},self.db),{'deleted':True})
        with self.assertRaises(ValueError):self.plan_api('GET',f"/api/plans/{copied['plan_id']}",None,self.db)


if __name__=='__main__':unittest.main()
