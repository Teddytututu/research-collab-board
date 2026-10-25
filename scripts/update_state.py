"""Update a local experiment counter, preserving prior bytes."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board import storage
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--done',required=True,type=int);p.add_argument('--total',required=True,type=int);p.add_argument('--root',type=Path,default=ROOT/'data');a=p.parse_args()
if not 0<=a.done<=a.total:p.error('Require 0 <= done <= total')
with storage.locked(a.root):
 path=a.root/'attachments/state.json';state=storage.read(path,dict(tasks={},runs={}));state.setdefault('runs',{})[a.run]=dict(done=a.done,total=a.total);storage.write(path,state)
print('Progress updated')
