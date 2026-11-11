"""Official USDA data in SQLite. No guessed food mappings or missing-as-zero values."""
import hashlib,json,math,re,sqlite3,zipfile
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
from .core import ROOT

DB=ROOT/'data/pdf_catalog.sqlite'

def schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS nutrition_sources(source_url TEXT PRIMARY KEY,release TEXT,sha256 TEXT,license TEXT,imported_utc TEXT);
    CREATE TABLE IF NOT EXISTS foods(fdc_id INTEGER PRIMARY KEY,description TEXT,data_type TEXT,category TEXT,publication_date TEXT,source_url TEXT,portions TEXT);
    CREATE TABLE IF NOT EXISTS food_nutrients(fdc_id INTEGER,nutrient_id INTEGER,name TEXT,unit TEXT,amount REAL,derivation TEXT,PRIMARY KEY(fdc_id,nutrient_id));
    CREATE INDEX IF NOT EXISTS food_description_idx ON foods(description);
    """)

def import_archive(archive,database=DB,*,source_url,release):
    archive=Path(archive);digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as z:
        names=[n for n in z.namelist() if n.endswith('.json')]
        if len(names)!=1:raise ValueError('Expected one USDA JSON file')
        data=json.loads(z.read(names[0]))
    keys=[k for k in ('FoundationFoods','SRLegacyFoods') if k in data]
    if len(keys)!=1:raise ValueError('Unsupported USDA dataset')
    rows=data[keys[0]]
    if not rows:raise ValueError('Empty USDA archive')
    Path(database).parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(database)) as c:
        schema(c)
        with c:
            old=[r[0] for r in c.execute('SELECT fdc_id FROM foods WHERE source_url=?',(source_url,))]
            for fid in old:c.execute('DELETE FROM food_nutrients WHERE fdc_id=?',(fid,))
            c.execute('DELETE FROM foods WHERE source_url=?',(source_url,))
            for food in rows:
                fid=int(food['fdcId'])
                c.execute('INSERT OR REPLACE INTO foods VALUES (?,?,?,?,?,?,?)',(fid,food['description'],food['dataType'],food.get('foodCategory',{}).get('description'),food.get('publicationDate'),source_url,json.dumps(food.get('foodPortions',[]))))
                c.execute('DELETE FROM food_nutrients WHERE fdc_id=?',(fid,))
                for entry in food.get('foodNutrients',[]):
                    n=entry['nutrient'];amount=entry.get('amount')
                    if amount is not None and (type(amount) not in (float,int) or not math.isfinite(amount)):raise ValueError('Invalid USDA nutrient amount')
                    c.execute('INSERT OR REPLACE INTO food_nutrients VALUES (?,?,?,?,?,?)',(fid,n['id'],n['name'],n['unitName'],amount,json.dumps(entry.get('foodNutrientDerivation',{}))))
            c.execute('INSERT OR REPLACE INTO nutrition_sources VALUES (?,?,?,?,?)',(source_url,release,digest,'CC0-1.0',datetime.now(timezone.utc).isoformat()))
        return {'foods_imported':len(rows),'data_type':rows[0]['dataType'],'release':release,'sha256':digest,'source_url':source_url}

def connect(database):
    if not Path(database).is_file():raise RuntimeError('Import the official USDA dataset first')
    c=sqlite3.connect('file:'+Path(database).resolve().as_posix()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    if not c.execute("SELECT name FROM sqlite_master WHERE name='foods'").fetchone():
        c.close();raise RuntimeError('USDA data has not been imported')
    return c

def search_foods(query,limit=10,database=DB):
    if not isinstance(query,str) or not 1<=len(query.strip())<=200:raise ValueError('Supply a food description of 1-200 characters')
    if type(limit) is not int or not 1<=limit<=20:raise ValueError('Limit must be 1-20')
    terms=re.findall(r'[\w]+',query.lower())
    if not terms:return []
    sql='SELECT f.fdc_id,f.description,f.data_type,f.category,s.release AS source_release FROM foods f JOIN nutrition_sources s USING(source_url) WHERE '+' AND '.join('lower(f.description) LIKE ?' for _ in terms)+' ORDER BY f.data_type,f.description LIMIT ?'
    with closing(connect(database)) as c:return [dict(r) for r in c.execute(sql,tuple('%'+t+'%' for t in terms)+(limit,))]

def get_food_nutrition(fdc_id,grams=100,database=DB):
    if type(fdc_id) is not int:raise ValueError('Use a retrieved integer FDC ID')
    if type(grams) not in (int,float) or not math.isfinite(grams) or not 0<grams<=100000:raise ValueError('Supply a positive weight in grams, at most 100000')
    with closing(connect(database)) as c:
        row=c.execute('SELECT f.*,s.release AS source_release,s.license,s.sha256 FROM foods f JOIN nutrition_sources s USING(source_url) WHERE fdc_id=?',(fdc_id,)).fetchone()
        if row is None:raise ValueError('Unknown FDC ID')
        result=dict(row);result['portions']=json.loads(result['portions']);result['basis_grams']=grams
        result['fdc_url']='https://fdc.nal.usda.gov/food-details/'+str(fdc_id)+'/nutrients'
        result['nutrients']=[{'nutrient_id':r['nutrient_id'],'name':r['name'],'unit':r['unit'],'amount':None if r['amount'] is None or r['amount']<0 else r['amount']*grams/100,'per_100g':r['amount'],'quality':'missing' if r['amount'] is None else ('negative_source_value' if r['amount']<0 else 'available')} for r in c.execute('SELECT * FROM food_nutrients WHERE fdc_id=? ORDER BY nutrient_id',(fdc_id,))]
        result['limits']='Missing nutrients are unknown, not zero. This is a food record, not a verified recipe match. Raw/cooked state and product type must match. Household units require this food recordâ€™s own gram weight.'
        return result
