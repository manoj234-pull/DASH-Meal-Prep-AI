import unittest,sqlite3,tempfile,json,zipfile
from pathlib import Path
from contextlib import closing
from dash_app.nutrition import import_archive,search_foods,get_food_nutrition

class NutritionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"catalog.sqlite";self.archive=Path(self.tmp.name)/"foods.zip"
        rows=[{"fdcId":123,"description":"Beans, cooked, no salt","dataType":"Foundation","foodCategory":{"description":"Legumes"},"foodNutrients":[{"nutrient":{"id":1093,"name":"Sodium, Na","unitName":"mg"},"amount":4},{"nutrient":{"id":1092,"name":"Potassium, K","unitName":"mg"},"amount":0}],"foodPortions":[{"amount":1,"gramWeight":180,"modifier":"cup"}]}]
        with zipfile.ZipFile(self.archive,'w') as z:z.writestr('foods.json',json.dumps({'FoundationFoods':rows}))
    def test_import_and_scale_keep_missing_separate_from_zero(self):
        import_archive(self.archive,self.db,source_url='https://fdc.nal.usda.gov/test.zip',release='test')
        result=get_food_nutrition(123,50,self.db)
        nutrients={x['name']:x['amount'] for x in result['nutrients']}
        self.assertEqual(nutrients['Sodium, Na'],2)
        self.assertEqual(nutrients['Potassium, K'],0)
        self.assertNotIn('Calcium, Ca',nutrients)
        self.assertEqual(result['basis_grams'],50)
        self.assertEqual(result['source_release'],'test')
    def test_search_is_candidates_not_automatic_mapping(self):
        import_archive(self.archive,self.db,source_url='https://fdc.nal.usda.gov/test.zip',release='test')
        self.assertEqual(search_foods('beans cooked',database=self.db)[0]['fdc_id'],123)
        self.assertEqual(search_foods('unknownzzz',database=self.db),[])
        with self.assertRaises(ValueError):get_food_nutrition(123,-1,self.db)
    def test_reimport_does_not_duplicate(self):
        for _ in range(2):import_archive(self.archive,self.db,source_url='https://fdc.nal.usda.gov/test.zip',release='test')
        with closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute('select count(*) from food_nutrients').fetchone()[0],2)

    def test_negative_source_value_is_preserved_but_not_used_as_intake(self):
        with zipfile.ZipFile(self.archive) as z:data=json.loads(z.read('foods.json'))
        data['FoundationFoods'][0]['foodNutrients'][0]['amount']=-0.4
        with zipfile.ZipFile(self.archive,'w') as z:z.writestr('foods.json',json.dumps(data))
        import_archive(self.archive,self.db,source_url='https://fdc.nal.usda.gov/test.zip',release='test')
        n=next(x for x in get_food_nutrition(123,database=self.db)['nutrients'] if x['nutrient_id']==1093)
        self.assertIsNone(n['amount'])
        self.assertEqual(n['per_100g'],-0.4)
        self.assertEqual(n['quality'],'negative_source_value')
