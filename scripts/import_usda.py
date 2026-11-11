"""Import downloaded official USDA archives; no API key required."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dash_app.nutrition import import_archive
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--url',required=True);p.add_argument('--release',required=True);a=p.parse_args()
    print(json.dumps(import_archive(a.archive,source_url=a.url,release=a.release),indent=2))
