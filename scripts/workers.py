"""Claim, heartbeat and release one task; quota limit is provided by the dispatcher."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board import workers

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['claim','heartbeat','release']);p.add_argument('task')
    p.add_argument('--data-dir',type=Path,default=Path('data'));p.add_argument('--worker',default='W1')
    p.add_argument('--scope',action='append',default=[]);p.add_argument('--allowed-workers',type=int,default=1);p.add_argument('--token')
    p.add_argument('--eta');p.add_argument('--status',default='待验收')
    a=p.parse_args()
    if a.action=='claim': row=workers.claim(a.data_dir,a.task,a.worker,a.scope,a.allowed_workers,eta=a.eta)
    else: row=workers.update(a.data_dir,a.task,a.token,release=a.action=='release',status=a.status)
    print(json.dumps(row,ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (ValueError, TimeoutError) as error:
        print(str(error),file=sys.stderr);sys.exit(2)
