import unittest,sqlite3
from contextlib import closing
from unittest.mock import patch
from tests.catalog_fixture import catalog_fixture
from dash_app.providers import retrieve_guidance
class PdfRetrievalTests(unittest.TestCase):
    def test_pinecone_metadata_is_verified_against_sqlite(self):
        with catalog_fixture() as db:
            with closing(sqlite3.connect(db)) as c,c:
                page=c.execute('SELECT id,page,text FROM pages LIMIT 1').fetchone()
                c.execute('INSERT INTO chunks VALUES (?,?,?)',('chunk-x',page[0],page[2]))
                c.executemany('INSERT INTO metadata VALUES (?,?)',[('corpus_version','version-x'),('pinecone_namespace','namespace-x'),('embedding_model','model-x')])
            meta={'text':page[2],'page_id':page[0],'document_id':'test-document','pdf_page':page[1],'sha256':'test'}
            with patch('dash_app.providers.load_env'),patch.dict('os.environ',{'NEBIUS_EMBEDDING_MODEL':'model-x'}),patch('dash_app.providers.embed',return_value=[[1.0]]),patch('dash_app.providers.pinecone',return_value={'matches':[{'id':'chunk-x','metadata':meta,'score':.9}]}):
                rows,_=retrieve_guidance('test query')
                self.assertEqual(rows[0]['text'],page[2])
                self.assertIn('/source/test-document.pdf',rows[0]['source_url'])
                meta['text']='Invented replacement text'
                with self.assertRaises(RuntimeError):retrieve_guidance('test query')
