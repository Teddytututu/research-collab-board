"""Install into a project-local environment and start one detached local board."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]

def parse_args(argv=None):
    p=argparse.ArgumentParser();p.add_argument('project',nargs='?');p.add_argument('--question',default='');p.add_argument('--deliverable',default='');p.add_argument('--user-name',default='大肥鱼');p.add_argument('--port',type=int,default=os.environ.get('RESEARCH_BOARD_PORT','8780'));p.add_argument('--agent',choices=['GPT','Claude'],default=os.environ.get('RESEARCH_BOARD_AGENT','GPT'))
    emotes=p.add_mutually_exclusive_group()
    emotes.add_argument('--download-emotes',dest='emotes',action='store_const',const='download',help='Record explicit permission and download optional local Bilibili emotes')
    emotes.add_argument('--unicode-emotes',dest='emotes',action='store_const',const='unicode',help='Record the Unicode-only choice')
    a=p.parse_args(argv)
    if not 1024<=a.port<=65535:p.error('Choose a port between 1024 and 65535')
    return a

def register_night_watch(python,root,*,runner=None,dry_run=False):
    """Attempt the project installer once; failed registration leaves a runnable command."""
    relative=Path(root).resolve().relative_to(ROOT.resolve()).as_posix()
    command=[str(python),'-B',str(ROOT/'scripts/install_night_watch.py'),'--project-root',str(ROOT),'--data-dir',relative,'--python',str(python),'--install']
    manual='& '+' '.join("'"+str(value).replace("'","''")+"'" for value in command) if os.name=='nt' else __import__('shlex').join(command)
    if dry_run:command+=['--dry-run']
    try:
        result=(runner or subprocess.run)(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)
        if result.returncode:raise ValueError((result.stderr or result.stdout or 'Scheduler registration failed').strip())
        report=json.loads(result.stdout or '{}')
        if not isinstance(report,dict):raise ValueError('Scheduler installer returned an invalid report')
        status='registered' if report.get('status')=='installed' or report.get('registered') is True else 'preview' if dry_run else 'manual'
        return dict(status=status,report=report,manual_command=report.get('manual_command') or manual)
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        return dict(status='manual',error=str(error),manual_command=manual)


def setup_message(message, fallback=None):
    """Keep first-run choices readable on both Unicode and legacy output streams."""
    try:
        print(message,flush=True)
    except UnicodeEncodeError:
        text=fallback if fallback is not None else message
        print(text.encode('ascii','backslashreplace').decode('ascii'),flush=True)


def first_run_options(python,root,choice=None):
    sys.path.insert(0,str(ROOT))
    from board import onboarding,storage
    def install_emotes(data):
        result=subprocess.run([str(python),'-B',str(ROOT/'scripts/install_emotes.py'),'--data',str(data)],cwd=ROOT,check=True,capture_output=True,text=True,encoding='utf-8',timeout=60)
        return json.loads(result.stdout)
    preferences=onboarding.configure_emotes(root,choice,installer=install_emotes)
    if preferences['show_prompt']:
        setup_message(onboarding.EMOTE_PROMPT+'？由部署助手询问；同意后传 --download-emotes，选择 Unicode 传 --unicode-emotes。当前使用 Unicode。',
                      'Optional: download about 225 public emotes to this local project? The deployment assistant asks for your choice. After agreement use --download-emotes; choose --unicode-emotes to keep Unicode. Unicode is active now.')
    if preferences.get('status')=='fallback':
        setup_message('表情下载已回退到 Unicode；选择与本机图片保存在项目内。',
                      'The emote download fell back to Unicode. Your choice and existing local images are retained.')
    path=storage.relative_file(root,onboarding.PREFERENCES)
    settings=storage.read(path,{})
    watch=settings.get('night_watch',{})
    if not watch:
        watch=register_night_watch(python,root)
        storage.update_json(root,onboarding.PREFERENCES,lambda settings:settings.update(night_watch=watch))
    if watch.get('status')=='manual':
        command=watch['manual_command']
        fallback='Night watch manual setup: '+command if command.isascii() else 'Night watch needs manual setup. The exact command is saved in the project data: attachments/onboarding.json -> night_watch.manual_command. Installer: scripts/install_night_watch.py --install.'
        setup_message('守夜人手动接入：'+command,fallback)
        if watch.get('error'):setup_message(watch['error'])
        report=watch.get('report',{})
        for key in ['prepare_command','detail']:
            if report.get(key):setup_message(report[key])
    return dict(emotes=preferences,night_watch=watch)


def main():
    a=parse_args()
    env=ROOT/'.venv';python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():subprocess.run([sys.executable,'-m','venv','--without-pip',str(env)],check=True)
    ready=subprocess.run([str(python),'-B','-c','import PIL'],capture_output=True)
    if ready.returncode:subprocess.run([str(python),'-B',str(ROOT/'scripts/install_deps.py')],cwd=ROOT,check=True)
    command=[str(python),'-B','-m','board','start']+([a.project] if a.project else [])+['--port',str(a.port)]
    if a.question:command+=['--question',a.question]
    if a.deliverable:command+=['--deliverable',a.deliverable]
    if a.user_name:command+=['--user-name',a.user_name]
    subprocess.run(command+['--init-only'],cwd=ROOT,check=True)
    first_run_options(python,ROOT/'data',getattr(a,'emotes',None))
    subprocess.run([str(python),'-B',str(ROOT/'scripts/patrol.py'),a.agent,'--auto'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    def next_steps():
        subprocess.run([str(python),'-B',str(ROOT/'scripts/onboarding.py'),'status',a.agent],cwd=ROOT,check=True)
    root=ROOT/'data';local=json.loads((root/'project.json').read_text(encoding='utf-8'));url=f'http://127.0.0.1:{a.port}'
    try:
        with urllib.request.urlopen(url+'/api/project',timeout=2) as response:running=json.load(response)
        if running.get('workspace_id')!=local.get('workspace_id'):raise SystemExit('Port belongs to another project; choose --port')
        with urllib.request.urlopen(url+'/api/me',timeout=2) as response:identity=json.load(response)
        if identity.get('listener')!='127.0.0.1':raise SystemExit('Restart this project with the current loopback-only entry')
        print(url);next_steps();return
    except OSError:pass
    with (root/'server.log').open('ab') as log:
        child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    sys.path.insert(0,str(ROOT));from board import storage
    storage.write(root/'service.json',dict(pid=child.pid,command=command,port=a.port,started=time.time()))
    for _ in range(80):
        if child.poll() is not None:raise SystemExit('Read data/server.log to resolve startup')
        try:
            with urllib.request.urlopen(url+'/api/project',timeout=1) as response:running=json.load(response)
            if running.get('workspace_id')==local.get('workspace_id'):print(url,flush=True);next_steps();return
        except OSError:time.sleep(.1)
    raise SystemExit('Startup is taking longer; inspect data/server.log')

if __name__=='__main__':main()
