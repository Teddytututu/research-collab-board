"""Post or inspect one of the project's three local conversations."""
from pathlib import Path
import argparse,sys,base64,mimetypes,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board.project import post,channel_id,ledger,message_metadata,all_posts,delete_message
from board.app import image_upload,file_upload
from board import storage
from board.writing import validate_message
p=argparse.ArgumentParser();p.add_argument('author',choices=['Claude','GPT'],nargs='?');p.add_argument('text',nargs='?');p.add_argument('--reply');p.add_argument('--delete',metavar='MESSAGE_ID');p.add_argument('--image',action='append',type=Path,default=[]);p.add_argument('--file',action='append',type=Path,default=[]);p.add_argument('--root',type=Path,default=ROOT/'data');p.add_argument('--channel');p.add_argument('--recent',action='store_true');p.add_argument('--limit',type=int,default=12);a=p.parse_args()
channel=channel_id(a.channel or 'main')
if a.delete:
 if not a.author or a.text is not None or a.reply or a.image or a.file or a.recent:p.error('Withdrawal uses an assistant identity and --delete MESSAGE_ID')
 print(json.dumps(delete_message(a.root,a.delete,a.author,assistant=True,channel=channel if a.channel else None),ensure_ascii=False));raise SystemExit(0)
if a.recent:
 rows=[row for row in all_posts(a.root) if a.channel is None or row.get('channel','main')==channel]
 rows.sort(key=lambda row:row.get('created_at',''))
 print(json.dumps([dict(row,**message_metadata(row)) for row in rows[-max(1,min(a.limit,100)):]],ensure_ascii=False,indent=2));raise SystemExit(0)
if not a.author or a.text is None:p.error('Provide an assistant and message, or --recent')
problems=validate_message(a.text)
if problems:p.error('; '.join(problems))
if len(a.image)+len(a.file)>6:p.error('Up to six attachments')
images=[];files=[]
for file in a.image:
 mime=mimetypes.guess_type(file.name)[0] or 'application/octet-stream';images.append(image_upload(a.root,'data:'+mime+';base64,'+base64.b64encode(file.read_bytes()).decode()))
for file in a.file:
 mime=mimetypes.guess_type(file.name)[0] or 'application/octet-stream';files.append(file_upload(a.root,dict(name=file.name,data='data:'+mime+';base64,'+base64.b64encode(file.read_bytes()).decode())))
print(post(a.root,a.author,a.text,a.reply,images=images,channel=channel,files=files)['id'])
