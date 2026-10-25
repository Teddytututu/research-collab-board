"""Host observation input and assistant native-goal requests; credentials stay out."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board import provider_bridge as bridge

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['observe-codex','quota','goal','controls'])
    p.add_argument('agent',nargs='?',choices=['GPT','Claude'],default='GPT');p.add_argument('--objective');p.add_argument('--status',choices=['active','complete'],default='active')
    p.add_argument('--data-dir',type=Path,default=ROOT/'data');a=p.parse_args()
    if a.action=='observe-codex':value=bridge.observe_codex(a.data_dir,json.load(sys.stdin))
    elif a.action=='quota':value=bridge.quota(a.data_dir,a.agent)
    elif a.action=='controls':value=bridge.controls(a.data_dir)
    else:
        if not a.objective:p.error('Provide --objective')
        value=bridge.request_goal(a.data_dir,a.agent,a.objective,a.status)
    print(json.dumps(value,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
