from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board.maintenance import reserve
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'data');p.add_argument('--owner',default='GPT');p.add_argument('--title',default='');a=p.parse_args()
    print(reserve(a.data_dir,a.owner,a.title))
