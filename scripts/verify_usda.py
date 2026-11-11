"""Compare every imported value against the original USDA download."""
import json,sqlite3,zipfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
    c=sqlite3.connect(ROOT/'data/pdf_catalog.sqlite');checked=0;nutrients=0;failures=[]
    try:
        for path in (ROOT/'data/source_downloads').glob('usda-*.zip'):
            with zipfile.ZipFile(path) as z:rows=next(iter(json.loads(z.read(next(n for n in z.namelist() if n.endswith('.json')))).values()))
            for food in rows:
                expected={n['nutrient']['id']:(n['nutrient']['name'],n['nutrient']['unitName'],n.get('amount')) for n in food['foodNutrients']}
                actual={r[0]:tuple(r[1:]) for r in c.execute('SELECT nutrient_id,name,unit,amount FROM food_nutrients WHERE fdc_id=?',(food['fdcId'],))}
                if expected!=actual:failures.append(food['fdcId'])
                checked+=1;nutrients+=len(expected)
        report={'food_records_compared':checked,'nutrient_values_compared':nutrients,'mismatched_food_ids':failures,'categories':c.execute('SELECT count(distinct category) FROM foods').fetchone()[0],'negative_source_values_preserved_and_flagged':c.execute('SELECT count(*) FROM food_nutrients WHERE amount<0').fetchone()[0],'scope':'Import fidelity to USDA downloads; does not verify recipe-food matching or clinical suitability.'}
        (ROOT/'reports/usda-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return not failures and checked>0
    finally:c.close()
if __name__=='__main__':sys.exit(0 if verify() else 1)
