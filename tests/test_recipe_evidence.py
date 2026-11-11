import unittest
from unittest.mock import patch
from dash_app.core import recipe_evidence
class MultiPageEvidenceTests(unittest.TestCase):
 def test_both_source_pages_are_used(self):
  with patch('dash_app.core.read_pdf_page',side_effect=lambda pid:{'text':{'a':'Ingredients','b':'Cooking steps'}[pid]}):
   self.assertEqual(recipe_evidence({'source_id':'a','source_page_ids':['a','b']}),'Ingredients\nCooking steps')
 def test_single_page_still_supported(self):
  with patch('dash_app.core.read_pdf_page',return_value={'text':'Original'}):self.assertEqual(recipe_evidence({'source_id':'a'}),'Original')
