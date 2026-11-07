import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dash_app.ingestion import ingest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,default=ROOT/'source_pdfs');p.add_argument('--database',type=Path,default=ROOT/'data/pdf_catalog.sqlite');a=p.parse_args()
 a.database.parent.mkdir(parents=True,exist_ok=True)
 (ROOT/'reports').mkdir(exist_ok=True)
 report=ingest(a.folder,a.database)
 (ROOT/'reports/ingestion.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2))
