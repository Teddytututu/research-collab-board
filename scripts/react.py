"""Assistant reactions are a local file operation, separate from browser authorship."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board import storage,project
from board.app import REACTIONS,REACTION_KEYS
p=argparse.ArgumentParser();p.add_argument('agent',choices=['Claude','GPT']);p.add_argument('message_id');p.add_argument('emoji',choices=REACTION_KEYS);p.add_argument('--remove',action='store_true');p.add_argument('--root',type=Path,default=ROOT/'data');a=p.parse_args()
if not any(x['id']==a.message_id for x in project.all_posts(a.root)):p.error('Choose an existing message')
with storage.locked(a.root):storage.append(a.root/'attachments/discussion/reactions.jsonl',dict(message_id=a.message_id,actor=a.agent,emoji=a.emoji,active=not a.remove))
print('Reaction saved')
