"""Start a named research project on IPv4 loopback."""
from pathlib import Path
import argparse,json,sys,importlib.util,os
from .environment import use_project_environment
if __name__=='__main__':use_project_environment(module='board')
from . import project,storage,scheduler
from .app import create_server
ROOT=Path(__file__).resolve().parents[1]

def build_parser():
    p=argparse.ArgumentParser(description='Start a local research collaboration project')
    p.add_argument('action',nargs='?',choices=['start','schedule','message'],default='start');p.add_argument('project',nargs='?')
    p.add_argument('--delete',metavar='MESSAGE_ID')
    p.add_argument('--data-dir',type=Path,default=ROOT/'data');p.add_argument('--port',type=int,default=os.environ.get('RESEARCH_BOARD_PORT','8780'))
    p.add_argument('--demo',action='store_true');p.add_argument('--init-only',action='store_true')
    p.add_argument('--question',default='');p.add_argument('--deliverable',default='');p.add_argument('--user-name',default='大肥鱼')
    return p

def parse_args(argv=None,*,parser=None):
    p=parser or build_parser();a=p.parse_args(argv)
    if not 1024<=a.port<=65535:p.error('Choose a port between 1024 and 65535')
    return a

def main():
    p=build_parser();a=parse_args(parser=p);root=a.data_dir.resolve()
    if a.action=='message':
        if a.project not in {'Claude','GPT'} or not a.delete:p.error('Use message Claude|GPT --delete MESSAGE_ID')
        try:result=project.delete_message(root,a.delete,a.project,assistant=True)
        except (ValueError,PermissionError) as error:p.error(str(error))
        print(json.dumps(result,ensure_ascii=True));return
    if a.action=='schedule':print(json.dumps(scheduler.refresh(root),ensure_ascii=False));return
    for module in ['PIL']:
        if importlib.util.find_spec(module) is None:p.error('Install dependencies: python -m pip install -r requirements.txt')
    existing=storage.read(root/'project.json')
    if existing:
        if a.project and existing['name']!=a.project:p.error('Choose another --data-dir for a separate project')
    else:
        name=a.project or ('示例研究' if a.demo else '新研究项目')
        if sys.stdin.isatty() and not (a.question and a.deliverable):
            a.question=input('一句研究问题 / Research question: ').strip();a.deliverable=input('想要的成果 / Desired deliverable: ').strip()
        project.initialize(root,name,a.question,a.deliverable,a.user_name,a.demo)
    if a.question and a.deliverable:project.configure(root,a.question,a.deliverable)
    scheduler.refresh(root)
    if a.init_only:print(json.dumps(dict(initialized=True,project=storage.read(root/'project.json')['name']),ensure_ascii=False));return
    try:server=create_server(root,a.port)
    except OSError:p.error('Port is occupied; choose another --port')
    print(f'http://127.0.0.1:{a.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
