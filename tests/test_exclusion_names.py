import unittest
from dash_app.core import contains_exclusion

class ExclusionNamesTests(unittest.TestCase):
    def test_preparation_and_plural_variations(self):
        for name in ['mushrooms, sliced','fresh mushroom, chopped','garlic, minced']:
            self.assertTrue(contains_exclusion([name],['mushrooms','garlic']))
    def test_whole_words_not_substrings(self):
        self.assertFalse(contains_exclusion(['eggplant','nutmeg'],['egg','nut']))
    def test_multiword_restrictions_remain_specific(self):
        self.assertTrue(contains_exclusion(['red onions, diced'],['red onion']))
        self.assertFalse(contains_exclusion(['green onions, chopped'],['red onion']))
