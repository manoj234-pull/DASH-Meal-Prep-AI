import unittest
from dash_app.recipe_view import apply_view, validate_view

class RecipeViewTests(unittest.TestCase):
    def setUp(self):
        self.rows=[{'id':'a','match_percent':20,'sodium_mg_per_serving':100,'vegetarian':True,'missing':['x'],'ingredients':[{'name':'olive oil'}]},
                   {'id':'b','match_percent':40,'sodium_mg_per_serving':200,'vegetarian':True,'missing':[],'ingredients':[{'name':'boneless chicken breast'}]},
                   {'id':'c','match_percent':60,'sodium_mg_per_serving':None,'vegetarian':False,'missing':['x','y'],'ingredients':[{'name':'salmon fillet'}]},
                   {'id':'d','match_percent':30,'sodium_mg_per_serving':50,'vegetarian':True,'missing':['y'],'ingredients':[{'name':'chicken thighs'},{'name':'garlic'}]}]
    def test_combined_filter_sort_and_limit(self):
        view=validate_view({}, {'filters':[{'field':'match_percent','operator':'gt','value':20},{'field':'vegetarian','operator':'eq','value':True}], 'sort_by':'sodium_mg_per_serving','direction':'asc','limit':1})
        rows,total=apply_view(self.rows,view)
        self.assertEqual([r['id'] for r in rows],['d']);self.assertEqual(total,2)
    def test_null_nutrition_is_not_zero(self):
        rows,total=apply_view(self.rows,validate_view({}, {'filters':[{'field':'sodium_mg_per_serving','operator':'lt','value':150}]}))
        self.assertEqual({r['id'] for r in rows},{'a','d'})
    def test_sort_missing_last_both_directions(self):
        for direction in ['asc','desc']:
            rows,_=apply_view(self.rows,validate_view({}, {'sort_by':'sodium_mg_per_serving','direction':direction}))
            self.assertEqual(rows[-1]['id'],'c')
    def test_patch_preserves_previous_filter_and_can_clear(self):
        view=validate_view({}, {'filters':[{'field':'match_percent','operator':'gt','value':20}]})
        updated=validate_view(view,{'limit':2});self.assertEqual(updated['filters'],view['filters'])
        cleared=validate_view(updated,{'filters':[],'limit':None});self.assertEqual(apply_view(self.rows,cleared)[1],4)
    def test_reject_unknown_fields_and_invalid_values(self):
        for patch in [{'sort_by':'invented'},{'limit':True},{'filters':[{'field':'match_percent','operator':'gt','value':float('nan')}]},{'filters':[{'field':'vegetarian','operator':'gt','value':1}]}]:
            with self.assertRaises(ValueError):validate_view({},patch)

    def test_filters_recipes_by_title_or_ingredient_name(self):
        view=validate_view({}, {'include_ingredients':['chicken']})
        title_only={**self.rows[0],'id':'title','title':'Chicken pantry bowl'}
        rows,total=apply_view(self.rows+[title_only],view)
        self.assertEqual(total,3)
        self.assertEqual({row['id'] for row in rows},{'b','d','title'})

    def test_excludes_recipes_by_title_or_ingredient_name(self):
        rows=[{**self.rows[0],'id':'title','title':'Baked Fish'},
              {**self.rows[2],'title':'Weeknight supper'},
              {**self.rows[1],'title':'Chicken bowl'}]
        view=validate_view({}, {'exclude_ingredients':['fish','salmon']})
        filtered,total=apply_view(rows,view)
        self.assertEqual([row['id'] for row in filtered],['b'])
        self.assertEqual(total,1)

    def test_excludes_ai_selected_recipe_ids_after_semantic_review(self):
        view=validate_view({}, {'exclude_recipe_ids':['a','c']})
        filtered,total=apply_view(self.rows,view)
        self.assertEqual([row['id'] for row in filtered],['b','d'])
        self.assertEqual(total,2)

    def test_ingredient_filter_does_not_match_partial_words(self):
        rows=[{'id':'eggplant','match_percent':50,'sodium_mg_per_serving':10,'vegetarian':True,'missing':[],
               'ingredients':[{'name':'eggplant'}]}]
        view=validate_view({}, {'include_ingredients':['egg']})
        visible,total=apply_view(rows,view)
        self.assertEqual((visible,total),([],0))

    def test_filters_recipe_titles_for_a_named_kind_of_recipe(self):
        view=validate_view({}, {'title_contains':'chicken'})
        rows,total=apply_view(self.rows,view)
        self.assertEqual((rows,total),([],0))
        titled=[{**self.rows[1],'title':'Chicken and rice'},{**self.rows[2],'title':'Baked fish'}]
        rows,total=apply_view(titled,view)
        self.assertEqual([row['title'] for row in rows],['Chicken and rice'])
