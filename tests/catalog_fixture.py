"""Synthetic golden catalog for offline tests only. Never imported by the app."""
import json,sqlite3,tempfile
from pathlib import Path
from contextlib import contextmanager,closing
from unittest.mock import patch
from dash_app import core
from dash_app.ingestion import schema,store_recipe
@contextmanager
def catalog_fixture():
    (core.ROOT/'reports').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=core.ROOT/'reports') as tmp:
        db=Path(tmp)/'golden.sqlite'
        with closing(sqlite3.connect(db)) as c,c:
            schema(c)
            c.execute('INSERT INTO metadata VALUES (?,?)',('schema_version','pdf-v1'))
            c.execute('INSERT INTO documents VALUES (?,?,?,?)',('test-document','Synthetic golden fixture','not-a-production-pdf','test'))
            rows=json.loads((Path(__file__).parent/'fixtures/golden_recipes.json').read_text())
            for r in rows:
                r['document_id']='test-document';r['source_url']='/source/test-document.pdf#page='+str(r['pdf_page'])
                for i in r['ingredients']:i['evidence']=str(i['quantity'])+' '+i['unit']+' '+i['name']
                text=' '.join([r['title']]+[i['evidence'] for i in r['ingredients']]+r['steps'])
                old=c.execute('SELECT text FROM pages WHERE id=?',(r['source_id'],)).fetchone()
                if old:text=old[0]+' '+text
                c.execute('INSERT OR REPLACE INTO pages VALUES (?,?,?,?)',(r['source_id'],'test-document',r['pdf_page'],text))
                store_recipe(c,r)
        with patch.object(core,'DB',db):yield db
