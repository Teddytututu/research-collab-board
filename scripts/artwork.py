"""Inspect native image jobs or deploy seven selected outputs for one persona."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board import storage,artwork
from board.onboarding import ImageDependencyError

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['list','deploy']);p.add_argument('role',nargs='?',choices=['GPT','Claude'])
    p.add_argument('--ids',nargs='+');p.add_argument('--data-dir',type=Path,default=ROOT/'data');a=p.parse_args()
    if a.action=='list':result=storage.read(a.data_dir/'attachments/provider-images.json',{})
    else:
        if not a.role or not a.ids:p.error('Provide a role and its seven native job IDs in avatar/calm/surprised/wink/smile/shy/teary order')
        try:result=artwork.deploy(a.data_dir,a.role,a.ids)
        except ImageDependencyError as error:p.error(str(error))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
