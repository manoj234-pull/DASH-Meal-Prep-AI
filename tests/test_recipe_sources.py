import unittest
from pathlib import Path
from dash_app.ingestion import extract_page_text, quantity, normalized, source_steps

class SourceReadingTests(unittest.TestCase):
    @unittest.skip('Offline PDF extraction is not part of the application test suite')
    def test_superscript_mixed_fraction_is_not_improper_fraction(self):
        import pdfplumber
        path=next((Path(__file__).resolve().parents[1]/"source_pdfs").glob("Your*.pdf"))
        with pdfplumber.open(path) as pdf:
            text=extract_page_text(pdf.pages[55])
        self.assertIn("6 1/2 Tbsp",text)
        self.assertIn("Tuna Salad",text)
        self.assertNotIn("61/2 Tbsp",text)
        self.assertEqual(quantity("6 1/2"),6.5)

    def test_temperature_glyph_equivalence_without_number_changes(self):
        self.assertEqual(normalized('350 \u02daF'),normalized('350 \u00b0F'))
        self.assertNotEqual(normalized('350 \u02daF'),normalized('375 \u00b0F'))

    def test_source_steps_keep_wrapped_lines_and_stop_at_nutrition(self):
        text='Dish\n1 cup grain\n1. Cook at 350 F.\nLet rest.\n2. Serve.\nMakes 2 servings\nCalories 100'
        self.assertEqual(source_steps(text),['Cook at 350 F. Let rest.','Serve.'])

    @unittest.skip('Offline PDF extraction is not part of the application test suite')
    def test_lasagna_fractions_preserve_whole_part(self):
        import pdfplumber
        path=next((Path(__file__).resolve().parents[1]/"source_pdfs").glob("Your*.pdf"))
        with pdfplumber.open(path) as pdf:
            text=extract_page_text(pdf.pages[59])
        self.assertIn("1 1/2 cups",text)
        self.assertIn("2 1/2 cups",text)

if __name__=="__main__":unittest.main()
