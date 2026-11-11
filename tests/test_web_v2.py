import unittest
import tempfile
from pathlib import Path
from dash_app.core import ROOT
from app import static_response


class VersionTwoWebTests(unittest.TestCase):
    def test_start_script_uses_existing_uv_when_local_python_is_missing(self):
        script=(ROOT/'START.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('Get-Command uv',script)
        self.assertIn("run --no-project python",script)

    def test_workspace_has_plan_grocery_prep_and_nutrition_views(self):
        hub=(ROOT/'UI/Animated UI/components/culinary/CulinaryPlateHub.tsx').read_text(encoding='utf-8')
        for view in ('WeeklyPlanView','GroceryListView','PrepDayView','PlanHistoryView'):
            self.assertIn(view,hub)
        source=''.join(path.read_text(encoding='utf-8') for path in
                       (ROOT/'UI/Animated UI/components/culinary/views').glob('*.tsx'))
        for field in ('grocery_list','prep_timeline','nutrition_summary'):
            self.assertIn(field,source)

    def test_react_build_is_preferred_and_unknown_routes_return_the_app(self):
        source=(ROOT/'app.py').read_text(encoding='utf-8')
        self.assertIn("root/'UI'/'dist'",source)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'UI/dist/assets').mkdir(parents=True);(root/'web').mkdir()
            (root/'UI/dist/index.html').write_text('react app',encoding='utf-8')
            (root/'UI/dist/assets/app.js').write_text('javascript',encoding='utf-8')
            (root/'web/index.html').write_text('fallback app',encoding='utf-8')
            self.assertEqual(static_response(root,'/')[0],b'react app')
            self.assertEqual(static_response(root,'/assets/app.js')[0],b'javascript')
            self.assertEqual(static_response(root,'/weekly-plan')[0],b'react app')

    def test_existing_web_app_is_used_when_react_build_is_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'web').mkdir();(root/'web/index.html').write_text('fallback app',encoding='utf-8')
            (root/'web/chat.js').write_text('script',encoding='utf-8')
            self.assertEqual(static_response(root,'/')[0],b'fallback app')
            self.assertEqual(static_response(root,'/chat.js')[0],b'script')


if __name__=='__main__':unittest.main()
