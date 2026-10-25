from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board.maintenance import compact_board,split_exchange
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['board','exchange','all']);p.add_argument('--data-dir',type=Path,default=ROOT/'data');a=p.parse_args();result={}
    if a.action in ['board','all']:result['board']=compact_board(a.data_dir)
    if a.action in ['exchange','all']:result['exchange']=split_exchange(a.data_dir)
    print(json.dumps(result,ensure_ascii=False))
