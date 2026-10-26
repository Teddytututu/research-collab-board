"""Build a clean source archive from the explicit allowlist and project version."""
from pathlib import Path
import hashlib,json,re,zipfile,sys,uuid,shutil,getpass,socket,tomllib
ROOT=Path(__file__).resolve().parents[1]
VERSION=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']

def write_report(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    if path.exists():
        before=path.read_bytes()
        if before==raw:return
        history=path.parent/'history';history.mkdir(exist_ok=True)
        saved=history/(path.name+'.'+hashlib.sha256(before).hexdigest()+'.before')
        if not saved.exists():saved.write_bytes(before)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.partial')
    temp.write_bytes(raw);temp.replace(path)

def files():
    names=['.gitattributes','.gitignore','LICENSE','README.md','README.zh-CN.md','当前指令.md','AGENTS.md','CLAUDE.md','pyproject.toml','requirements.txt','发言.py']
    names+=['board/'+n for n in ['__init__.py','__main__.py','app.py','contacts.py','project.py','maintenance.py','scheduler.py','provider_bridge.py','onboarding.py','artwork.py','assets.py','environment.py','storage.py','workers.py','task_eta.py','eta-view.js','eta-view.css','fanart.css','index.html','identity.js','identity.css','discussion.js','discussion.css','room-extras.js','room-markdown.js','room-features.css','v02.js','v02.css','room-collection.js','mood.js','room-collection.css','help.html']]
    names+=['scripts/'+n for n in ['bootstrap.py','install_emotes.py','install_deps.py','verify.py','onboarding.py','provider_bridge.py','artwork.py','maintenance.py','task_number.py','workers.py','post_message.py','update_state.py','patrol.py','react.py','install-startup.ps1','watchdog.ps1','release.py','night_watch.py','run_queue.py','install_night_watch.py','install-night-watch.ps1']]
    names+=['docs/'+n for n in ['assets.md','agent-schedules.md','provider-bridge.md','patrol.md','quota.md','quota-scenarios.md','customization.md','private-repository.md','validation.md','third-party-notices.md','night-watch.md']]
    names+=['demo/overview.json','demo/board.md']
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_v02*.py')]
    names += ['board/message_controls.py','tests/discussion-actions.test.cjs','tests/mobile-layers.browser.cjs']
    names += ['board/lifecycle.py','board/watch_rules.py','board/writing.py','board/lifecycle-view.js','board/lifecycle-view.css']
    names += ['scripts/task_flow.py','scripts/flow_check.py','scripts/patrol_log.py']
    names += ['tests/lifecycle-view.test.cjs','tests/mobile-layers-optional-runtime.test.cjs']
    names += ['tests/room-collection.test.cjs','tests/eta-view.test.cjs','tests/identity-refresh.test.cjs','tests/quota-truth.test.cjs']
    for folder in ['personas','protocol','templates']:
        names += [p.relative_to(ROOT).as_posix() for p in (ROOT/folder).glob('*') if p.suffix in ['.md','.json']]
    names += ['skills/research-report-writing/'+name for name in [
        'SKILL.md','README.md','references/writing.zh-CN.md','templates/report_helpers.py']]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'board/art').glob('*.svg') if p.name.startswith(('avatar-user','avatar-claude','avatar-gpt','claude-','gpt-','user-'))]
    names += ['assets/README.md','assets/public-emotes.json','board/art/fanart.json']
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'board/art').glob('*.png') if p.name in {'avatar-claude-full.png','avatar-claude.png','avatar-gpt.png','avatar-user.png','cell-01.png','cell-02.png','cell-03.png','cell-04.png','cell-05.png','cell-06.png','cell-07.png','cell-08.png','cell-09.png','cell-10.png','cell-11.png','cell-12.png','claude-calm.png','claude-cheer.png','claude-confused.png','claude-happy.png','claude-heart.png','claude-panic.png','claude-pout.png','claude-proud.png','claude-reading.png','claude-shy.png','claude-sleepy.png','claude-surprised.png','claude-teary.png','claude-thinking.png','claude-wink.png','emotion-atlas.png','trio-atlas.png'}]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'board/reactions').glob('*.svg')]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'docs').glob('v02-*.png')]
    return sorted(set(names))

def scan(blob,name=''):
    if blob.startswith(b'\x89PNG'):return []
    text=blob.decode('utf-8',errors='replace');rules={
        'private_absolute_path':r'(?i)[A-Z]:[/\\](?:Users|科研工作)[/\\]|/(?:home|localdata|var/tmp)/[a-z0-9_-]+',
        'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'literal_credential':r'''(?i)(?:api[_-]?key|password|secret)\s*[:=]\s*["'][A-Za-z0-9+/=]{24,}["']''',
        'email':r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}',
        'private_media_reference':r'/chat-img/[a-f0-9]{32}\.',
    }
    problems=[k for k,p in rules.items() if re.search(p,text)]
    # The local user's machine identity is computed at release time, never embedded in source.
    for value in [getpass.getuser(),socket.gethostname()]:
        if len(value)>3 and re.search(r'(?<![A-Za-z0-9_])'+re.escape(value)+r'(?![A-Za-z0-9_])',text,re.I):problems.append('local_machine_identity')
    return problems

def main():
    out=ROOT/'work/releases';out.mkdir(parents=True,exist_ok=True);manifest=[];problems=[];scanned=[]
    for name in files():
        path=ROOT/name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):raise ValueError('Source boundary')
        raw=path.read_bytes();manifest.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        problems.extend(dict(path=name,rule=r) for r in scan(raw,name))
        scanned.append((name,raw))
    report=dict(version=VERSION,files=len(manifest),findings=problems,manifest=manifest)
    write_report(out/'privacy-scan.json',report)
    if problems:raise SystemExit('Review work/releases/privacy-scan.json')
    archive=out/('research-collab-board-'+VERSION+'.zip');temp=out/(archive.name+'.'+uuid.uuid4().hex+'.partial')
    with zipfile.ZipFile(temp,'x',zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for name,raw in scanned:z.writestr('research-collab-board/'+name,raw)
    if archive.exists():
        history=out/'history';history.mkdir(exist_ok=True);digest=hashlib.sha256(archive.read_bytes()).hexdigest();saved=history/(digest+'.zip')
        if not saved.exists():shutil.copy2(archive,saved)
    temp.replace(archive)
    value=dict(archive=archive.name,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),bytes=archive.stat().st_size,source_files=len(manifest),privacy_findings=0)
    write_report(out/'release.json',value);print(json.dumps(value))

if __name__=='__main__':main()
