"""Inspect setup evidence or record an actual provider-native tool result."""
from pathlib import Path
import argparse,json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board import onboarding,storage,provider_bridge

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['status','native-result','emotes']);p.add_argument('agent',choices=['GPT','Claude'],nargs='?',default='GPT')
    p.add_argument('--id');p.add_argument('--kind',choices=['goal','scheduled-task'],default='goal')
    emotes=p.add_mutually_exclusive_group()
    emotes.add_argument('--download-emotes',dest='emotes',action='store_const',const='download')
    emotes.add_argument('--unicode-emotes',dest='emotes',action='store_const',const='unicode')
    p.add_argument('--data-dir',type=Path,default=ROOT/'data');a=p.parse_args()
    if a.action=='emotes':
        if a.emotes is None:p.error('Record the user answer with --download-emotes or --unicode-emotes')
        print(json.dumps(onboarding.configure_emotes(a.data_dir,a.emotes),ensure_ascii=False,indent=2));return
    if a.emotes is not None:p.error('Use the emotes action to record the user answer')
    if a.action=='native-result':
        if not a.id:p.error('Provide the actual returned provider-native ID')
        provider_bridge.record_native(a.data_dir,a.agent,a.kind,a.id)
    result=onboarding.status(a.data_dir,a.agent)
    storage.update_json(a.data_dir,'attachments/state.json',lambda s:s.setdefault('assistant_setup',{}).update({a.agent:result}))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
