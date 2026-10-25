"""Idempotent project setup and a file-based assistant discussion interface."""
from pathlib import Path
from datetime import datetime
import hashlib,uuid,json,re
from . import storage
CHANNELS={'main':'研究','study':'学习','library':'文件收藏'}

def channel_id(value='main'):
    aliases={'研究':'main','学习':'study','文件收藏':'library','research':'main','files':'library'}
    value=aliases.get(value,value)
    if value not in CHANNELS:raise ValueError('Choose research, study or file collection')
    return value

def ledger(root,channel='main'):
    name={'main':'web-main.jsonl','study':'web-study.jsonl','library':'web-library.jsonl'}[channel_id(channel)]
    return Path(root)/'attachments/discussion'/name

def raw_posts(root):return [p for c in CHANNELS for p in storage.lines(ledger(root,c))]

def all_posts(root):
    from .message_controls import marker_path,project_rows
    return project_rows(raw_posts(root),storage.lines(marker_path(root)))

def project_message(root,row):
    return next((p for p in all_posts(root) if p['id']==row['id']),row)

def delete_message(root,message_id,actor,*,assistant=False,channel=None):
    from .message_controls import delete_message as delete
    return delete(root,message_id,actor,assistant=assistant,channel=channel)

def message_metadata(row):
    """Classify historical automatic content in memory; retain ledger bytes."""
    kind='assistant' if row.get('author') in ['Claude','GPT'] else 'user'
    if kind=='assistant':
        if row.get('client_id') in ['project-kickoff-v2','builder-kickoff-v2']:kind='initialization'
        elif row.get('client_id') in ['demo-project-kickoff-v2','demo-builder-kickoff-v2']:kind='demo'
    return dict(message_kind=kind,source_label={'initialization':'初始化说明','demo':'示例'}.get(kind))

def session_message(row):return message_metadata(row)['message_kind']=='assistant'

def post(root,author,body,parent_id=None,client_id=None,images=None,channel='main',files=None,request_digest=None):
    if author not in ['owner','Claude','GPT']:raise ValueError('Choose the user, Claude or GPT')
    if not isinstance(body,str) or len(body)>6000 or not body.strip() and not images and not files:raise ValueError('Provide text or an attachment')
    if client_id is not None and (not isinstance(client_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}',client_id)):raise ValueError('Message identifier format')
    with storage.locked(root):return _post(root,author,body,parent_id,client_id,images,channel,files,request_digest=request_digest)

def _post(root,author,body,parent_id=None,client_id=None,images=None,channel='main',files=None,reference=None,request_digest=None):
    channel=channel_id(channel);path=ledger(root,channel);rows=storage.lines(path)
    if parent_id and not any(p['id']==parent_id for p in (all_posts(root) if channel=='main' else rows)):raise ValueError('Reply target must exist')
    if client_id:
        previous=next((p for p in rows if p.get('client_id')==client_id and p['author']==author),None)
        if previous:
            if request_digest:
                if previous.get('request_digest')!=request_digest:raise ValueError('Retry content must match')
            elif previous['body']!=body.strip() or previous.get('parent_id')!=parent_id or previous.get('images',[])!=(images or []):raise ValueError('Retry content must match')
            return project_message(root,previous)
    p=dict(id=uuid.uuid4().hex,author=author,body=body.strip(),parent_id=parent_id,client_id=client_id,images=images or [],files=files or [],channel=channel,created_at=datetime.now().astimezone().isoformat())
    if reference:p['reference']=reference
    if request_digest:p['request_digest']=request_digest
    storage.append(path,p);return project_message(root,p)

def bookmark(root,channel,message_id):
    channel=channel_id(channel)
    with storage.locked(root):
        source=next((p for p in all_posts(root) if p['id']==message_id and p.get('channel','main')==channel),None)
        if source is None or source.get('deleted'):raise ValueError('Choose an active conversation message')
        if channel=='library':return source
        ref=dict(channel=channel,message_id=message_id)
        previous=next((p for p in storage.lines(ledger(root,'library')) if p.get('reference')==ref),None)
        if previous:return project_message(root,previous)
        label=storage.read(Path(root)/'project.json',{}).get('user_name','大肥鱼') if source['author']=='owner' else source['author']
        return _post(root,'owner',f'收藏自{CHANNELS[channel]} · {label}\n\n'+source['body'],images=source.get('images'),channel='library',files=source.get('files'),reference=ref)

def initialize(root,name,question='',deliverable='',user_name='大肥鱼',demo=False):
    root=Path(root);name=str(name).strip()
    if not name or len(name)>120:raise ValueError('Provide a project name within 120 characters')
    with storage.locked(root):
        p=root/'project.json'
        if p.exists():
            existing=storage.read(p)
            if existing['name']!=name:raise ValueError('Use a separate --data-dir for another project')
            return existing
        value=dict(schema='research-board-project-v2',workspace_id=uuid.uuid4().hex,name=name,question=question,deliverable=deliverable,user_name=user_name,theme='default',created_at=datetime.now().astimezone().isoformat(),onboarding_complete=bool(question and deliverable))
        overview=dict(todo=[dict(what='写下一句研究问题与希望得到的成果',when='开始时',how='在项目设置中填写')],schedule=[],progress_lines=[dict(line=name,text=question or '从研究问题与具体成果开始。')],runs=[],tree=[dict(title=name,status='todo',summary=deliverable or '确定成果后开始分工',children=[])],task_groups=[],links=[dict(title='使用说明',path='/help',cat='项目',archived=False)],important_dates=[])
        if demo:
            seed=storage.read(Path(__file__).resolve().parents[1]/'demo/overview.json',{})
            overview.update({k:v for k,v in seed.items() if k!='parent_summary'})
        storage.write(p,value);storage.write(root/'overview.json',overview)
        for n,text in {'board.md':'# '+name+'\n\n| ID | 工作 | 状态 | 负责人 |\n| --- | --- | --- | --- |\n','exchange.md':'# 研究协作\n'}.items():
            if demo and n=='board.md':text=(Path(__file__).resolve().parents[1]/'demo/board.md').read_text(encoding='utf-8')
            if not (root/n).exists():(root/n).write_text(text,encoding='utf-8')
        storage.write(root/'attachments/state.json',dict(tasks={},runs={}))
        storage.write(root/'attachments/agents.json',{n:dict(tier='plenty',remaining=.7,reset_hours=24,precision='band') for n in ['Claude','GPT']})
        path=ledger(root);path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.touch()
        if demo:
            _post(root,'Claude','示例：研究负责人说明研究问题、比较方式与验收标准。',client_id='demo-project-kickoff-v2')
            _post(root,'GPT','示例：执行助手回复约定方案，并交付可审查的实现与结果。',client_id='demo-builder-kickoff-v2')
        return value

def configure(root,question,deliverable,user_name=None):
    if not isinstance(question,str) or not isinstance(deliverable,str) or not question.strip() or not deliverable.strip() or len(question)>2000 or len(deliverable)>2000:raise ValueError('Provide one research question and a concrete deliverable')
    with storage.locked(root):
        p=storage.read(root/'project.json');p.update(question=question.strip(),deliverable=deliverable.strip(),onboarding_complete=True)
        if user_name is not None:
            if not isinstance(user_name,str) or not 1<=len(user_name.strip())<=40:raise ValueError('Display name within 40 characters')
            p['user_name']=user_name.strip()
        storage.write(root/'project.json',p);o=storage.read(root/'overview.json');o['todo']=[];o['progress_lines']=[dict(line=p['name'],text=p['question'])];o['tree'][0].update(summary=p['deliverable'],status='doing');storage.write(root/'overview.json',o)
    return p
