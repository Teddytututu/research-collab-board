"""Single-user application bound to IPv4 loopback."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,unquote,parse_qs
import base64,hashlib,html,io,ipaddress,json,mimetypes,os,re,uuid
from . import project,storage,scheduler,contacts,task_eta,assets,onboarding
ASSETS=Path(__file__).resolve().parent
STATIC={n for n in ['index.html','discussion.js','discussion.css','identity.js','identity.css','room-extras.js','room-markdown.js','room-features.css','room-collection.js','mood.js','room-collection.css','v02.js','v02.css','eta-view.js','eta-view.css','fanart.css','help.html']}
STATIC.update({'lifecycle-view.js','lifecycle-view.css','index-tabs.js','index-tabs.css'})
REACTIONS={'👍':'done','❤️':'care','😂':'smile','🎉':'celebrate','👀':'review','💡':'idea'}
REACTION_KEYS=list(dict.fromkeys([*REACTIONS,*(x['key'] for x in assets.emote_manifest())]))
def contained(root,relative):
    root=Path(root).resolve();p=root/relative
    if Path(relative).is_absolute() or not p.resolve().is_relative_to(root):raise ValueError('Workspace-relative file required')
    current=p
    while current!=root:
        if current.is_symlink():raise ValueError('Workspace file required')
        current=current.parent
    return p

def accounts(root):
    p=storage.read(root/'project.json');rows=[]
    for name,label,asset in [('owner',p['user_name'],'user'),('Claude','Claude','claude'),('GPT','GPT','gpt')]:
        generated=generated_asset(root,name,'avatar')
        file=generated.relative_to(root/'attachments').as_posix() if generated else f'avatar-{asset}.svg'
        avatar=dict(file=file,full=file)
        bundled=assets.avatars().get(name,{})
        if not generated and bundled and (ASSETS/'art'/bundled['file']).is_file():avatar=bundled
        rows.append(dict(id=name,display_name=label,avatar=avatar))
    return rows

MOOD_ALIASES={'happy':'smile','sleepy':'calm','proud':'smile','reading':'calm','heart':'shy',
              'cheer':'smile','pout':'teary','confused':'surprised','thinking':'calm','panic':'surprised'}

def generated_asset(root,who,mood):
    """Use the newest runtime format; preserve both files and original placeholders."""
    for name in dict.fromkeys([mood,MOOD_ALIASES.get(mood,mood)]):
        candidates=[contained(Path(root)/'attachments',f'generated/{who}/{name}{ext}') for ext in ['.png','.svg']]
        found=[p for p in candidates if p.is_file()]
        if found:return max(found,key=lambda p:(p.stat().st_mtime_ns,p.suffix=='.png'))
    return None

def conversation(root,channel=None):
    unified=channel is None;channel=project.channel_id(channel or 'main');posts=[p for p in project.all_posts(root) if unified or p.get('channel','main')==channel]
    from .message_controls import reaction_state
    active=reaction_state(storage.lines(root/'attachments/discussion/reactions.jsonl'))
    people={p['id']:{k:p.get(k) for k in ('id','display_name','avatar')} for p in accounts(root)}
    from datetime import datetime,timezone
    def timestamp(p):
        d=datetime.fromisoformat(p['created_at'].replace('Z','+00:00'));return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    posts=sorted(posts,key=timestamp)
    items=[]
    for row in posts:
        value={k:row.get(k) for k in ['id','body','parent_id','author','created_at','channel','images','files','reference']};value['images']=value['images'] or [];value['files']=value['files'] or []
        value.update(project.message_metadata(row))
        value.update({k:row.get(k) for k in ('deleted','deleted_by','deleted_at','delete_action','parent_deleted','reference_text')})
        value['can_delete']=not row.get('deleted',False)
        if not row.get('deleted'):value['delete_action']='withdraw' if row.get('author')=='owner' else 'delete'
        if row.get('deleted'):value.pop('reference',None)
        value['reactions']=[] if row.get('deleted') else [dict(emoji=e,count=sum(mid==row['id'] and em==e for mid,a,em in active),mine=(row['id'],'owner',e) in active,
            actors=[people[a] for mid,a,em in sorted(active) if mid==row['id'] and em==e and a in people]) for e in REACTION_KEYS if any(mid==row['id'] and em==e for mid,a,em in active)]
        items.append(value)
    catalog=assets.reaction_catalog(root) if onboarding.emote_preferences(root)['mode']=='download' else []
    result=dict(items=items,channel=channel,unified=unified,max_text=6000,reaction_emoji=list(dict.fromkeys([*REACTIONS,*(x['key'] for x in catalog)])),reaction_catalog=catalog,sticker_catalog=[])
    result['revision']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest();return result

def snapshot(root,channel=None):
    overview=storage.read(root/'overview.json',{});state=storage.read(root/'attachments/state.json',{});tasks=[]
    if overview.get('patrols'):
        from .lifecycle import check
        overview['flow_issues']=check(root)
    for line in (root/'board.md').read_text(encoding='utf-8').splitlines():
        cells=[x.strip() for x in line.strip('|').split('|')]
        if len(cells)>=4 and re.fullmatch('T[0-9]+',cells[0]):tasks.append(dict(id=cells[0],title=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',cells[1]),status=cells[2],owner=cells[3]))
    for tid,row in state.get('tasks',{}).items():
        current=next((x for x in tasks if x['id']==tid),None)
        if current:current.update({k:row[k] for k in ['title','status','owner','current_stage'] if k in row})
        else:tasks.append(dict(id=tid,title=row.get('title',tid),status=row.get('status','待领'),owner=row.get('owner','GPT'),**({'current_stage':row['current_stage']} if 'current_stage' in row else {})))
    for run in overview.get('runs',[]):run.update(state.get('runs',{}).get(run.get('id'),{}))
    from datetime import datetime,timedelta
    today=datetime.now().astimezone().date()
    for day in overview.get('schedule',[]):
        if type(day.get('relative_day')) is int:day['date']=(today+timedelta(days=day['relative_day'])).strftime('%m-%d')
    overview=task_eta.project(root,overview)
    for task in tasks:task['eta']=overview.get('task_etas',{}).get(task['id'])
    result=dict(overview=overview,tasks=tasks,discussion=conversation(root,channel),project=storage.read(root/'project.json'),modified=datetime.now().astimezone().isoformat())
    result['revision']=hashlib.sha256(json.dumps({k:v for k,v in result.items() if k!='modified'},sort_keys=True).encode()).hexdigest();return result

def image_upload(root,value):
    from PIL import Image,ImageOps
    import warnings
    if not isinstance(value,str) or len(value)>12*1024**2:raise ValueError('Image size limit 8MiB')
    m=re.fullmatch(r'data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/=]+)',value)
    if not m:raise ValueError('Choose a supported image')
    blob=base64.b64decode(m[2],validate=True)
    if len(blob)>8*1024**2:raise ValueError('Image size limit 8MiB')
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(blob)) as im:
            if im.width*im.height>16_000_000 or im.format not in ['PNG','JPEG','WEBP','GIF']:raise ValueError('Image dimensions or type')
            image=ImageOps.exif_transpose(im).convert('RGB');image.load()
    name=uuid.uuid4().hex+'.png';p=root/'attachments/discussion/images'/name;p.parent.mkdir(parents=True,exist_ok=True);image.save(p,'PNG');return name

def file_upload(root,value):
    if not isinstance(value,dict) or set(value)!={'name','data'}:raise ValueError('File upload format')
    name=value['name'];data=value['data']
    if not isinstance(name,str) or not 1<=len(name)<=160 or re.search(r'[/\\<>:\x00-\x1f]',name):raise ValueError('Choose a file name')
    ext=Path(name).suffix.lower()
    if ext not in ['.pdf','.txt','.md','.csv','.json','.docx','.xlsx','.pptx','.zip','.html']:raise ValueError('Choose a document, archive or text file')
    match=re.fullmatch(r'data:[a-zA-Z0-9.+/-]*;base64,([A-Za-z0-9+/=]+)',data) if isinstance(data,str) and len(data)<=12*1024**2 else None
    if not match:raise ValueError('File encoding')
    blob=base64.b64decode(match[1],validate=True)
    if not 0<len(blob)<=8*1024**2:raise ValueError('File size limit 8MiB')
    identifier=uuid.uuid4().hex+ext;p=root/'attachments/discussion/files'/identifier;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(blob)
    return dict(id=identifier,name=name,bytes=len(blob),url='/chat-file/'+identifier)

def create_server(root,port=8780,open_file=None):
    root=Path(root).resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,value=b'',mime='application/json; charset=utf-8',headers=()):
            if isinstance(value,dict):value=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            if isinstance(value,str):value=value.encode()
            self.send_response(status)
            for key,val in [('Content-Type',mime),('Content-Length',str(len(value))),('Cache-Control','no-store, private'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"),*headers]:self.send_header(key,val)
            self.end_headers()
            if self.command!='HEAD':self.wfile.write(value)
        def body(self,limit=100_000):
            fields=self.headers.get_all('Content-Length',[])
            if len(fields)!=1 or not fields[0].isdigit() or self.headers.get('Transfer-Encoding'):raise ValueError('Fixed request length required')
            size=int(fields[0])
            if not 0<size<=limit:raise ValueError('Request size limit')
            if self.headers.get_content_type()!='application/json':raise ValueError('JSON request required')
            value=json.loads(self.rfile.read(size))
            if not isinstance(value,dict):raise ValueError('JSON object required')
            return value
        def dispatch(self):
            authority=self.headers.get('Host','');host=urlsplit('http://'+authority).hostname
            hosts={'127.0.0.1','localhost','::1'}
            if host not in hosts or self.headers.get('Forwarded') or any(k.lower().startswith('x-forwarded-') for k in self.headers):return self.respond(403,dict(error='Use the direct board address'))
            local=ipaddress.ip_address(self.client_address[0]).is_loopback
            if not local:return self.respond(403,dict(error='Use the local board address'))
            if self.command=='POST' and self.headers.get('X-Board-Identity') not in {None,'owner'}:return self.respond(403,dict(error='Browser identity is the project owner'))
            route=unquote(urlsplit(self.path).path)
            query=parse_qs(urlsplit(self.path).query)
            channel=project.channel_id((query.get('channel') or ['main'])[0])
            if self.command=='POST' and self.headers.get('Origin')!='http://'+authority:return self.respond(403,dict(error='Use the board page to send requests'))
            if self.command=='POST':
                p=self.body(68*1024**2 if route=='/api/discussion' else 100_000)
                if route=='/api/discussion/delete':
                    if set(p)-{'message_id','channel'} or 'message_id' not in p:raise ValueError('Deletion uses a message ID and optional channel')
                    return self.respond(200,project.delete_message(root,p['message_id'],'owner',channel=p.get('channel')))
                if route=='/api/discussion':
                    if p.get('author','owner')!='owner':return self.respond(403,dict(error='Browser messages use the project user'))
                    channel=project.channel_id(p.get('channel','main'));images=p.get('images',[]);files=p.get('files',[])
                    if not isinstance(images,list) or not isinstance(files,list) or len(images)+len(files)>6:raise ValueError('Up to six attachments')
                    digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
                    prior=next((x for x in storage.lines(project.ledger(root,channel)) if x.get('client_id')==p.get('client_id') and x['author']=='owner'),None) if p.get('client_id') else None
                    if prior:
                        if prior.get('request_digest')!=digest:raise ValueError('Retry content must match')
                        return self.respond(201,dict(post=project.project_message(root,prior)))
                    names=[image_upload(root,x) for x in images]
                    uploaded=[file_upload(root,x) for x in files]
                    return self.respond(201,dict(post=project.post(root,'owner',p.get('body',''),p.get('parent_id'),p.get('client_id'),names,channel,uploaded,digest)))
                if route in ['/api/bookmark','/api/favorite']:return self.respond(201,dict(post=contacts.favorite(root,p,'owner')))
                if route=='/api/reaction':
                    mid=p.get('message_id');emoji=p.get('emoji')
                    if set(p)!={'message_id','emoji','active'} or emoji not in REACTION_KEYS or type(p.get('active')) is not bool or not any(x['id']==mid and not x.get('deleted') for x in project.all_posts(root)):raise ValueError('Choose an active conversation message and reaction')
                    with storage.locked(root):storage.append(root/'attachments/discussion/reactions.jsonl',dict(message_id=mid,emoji=emoji,active=p['active'],actor='owner'))
                    return self.respond(200,dict(message_id=mid,reactions=next(x['reactions'] for c in project.CHANNELS for x in conversation(root,c)['items'] if x['id']==mid)))
                if route=='/api/project':return self.respond(200,project.configure(root,p.get('question'),p.get('deliverable'),p.get('user_name')))
                if route=='/api/quota':
                    name=p.get('agent');tier=p.get('tier')
                    if tier not in scheduler.TIERS:raise ValueError('Choose a quota band')
                    return self.respond(200,scheduler.report(root,name,tier=tier,remaining=scheduler.TIERS[tier],reset_hours=p.get('reset_hours',24),precision='band',source='manual-band-estimate',observed_at=None,reset_source='manual horizon estimate',resolution='manually selected quota band'))
                if route=='/api/open':
                    links=storage.read(root/'overview.json',{}).get('links',[]);index=p.get('i')
                    if type(index) is not int or not 0<=index<len(links):raise ValueError('Select a project file')
                    file=contained(root,links[index]['path'])
                    if file.is_relative_to(root/'attachments/discussion'):return self.respond(404,dict(error='Choose a public project file'))
                    if not file.exists():return self.respond(404,dict(error='Project file is being prepared'))
                    if open_file:open_file(file)
                    elif os.name=='nt':os.startfile(file)
                    else:raise ValueError('Open the project file using its report link')
                    return self.respond(200,dict(ok=True))
                return self.respond(404,dict(error='Choose a project action'))
            if route in ['/','/index.html']:
                text=(ASSETS/'index.html').read_text(encoding='utf-8');p=storage.read(root/'project.json')
                text=text.replace('__SITE_TITLE__',html.escape(p['name'])).replace('__GREETING_LITERAL__',json.dumps(p['user_name']+'，',ensure_ascii=False).replace('<','\\u003c'))
                return self.respond(200,text,'text/html; charset=utf-8')
            if route=='/favicon.ico':return self.respond(204,b'','image/x-icon')
            if route=='/api/me':return self.respond(200,dict(id='owner',local=local,listener=self.server.server_address[0],channel='main',channels=list(project.CHANNELS),conversations=True))
            if route=='/api/accounts':return self.respond(200,dict(accounts=accounts(root)))
            if route=='/api/board':return self.respond(200,snapshot(root,channel if 'channel' in query else None))
            if route=='/api/discussion':return self.respond(200,conversation(root,channel if 'channel' in query else None))
            if route=='/api/conversations':
                seen=json.loads((query.get('seen') or ['{}'])[0]);rows=[]
                for cid,label in project.CHANNELS.items():
                    posts=[p for p in project.all_posts(root) if p.get('channel','main')==cid];last=posts[-1] if posts else None;stamp=seen.get(cid,'') if isinstance(seen,dict) else ''
                    from datetime import datetime,timezone
                    def epoch(value):
                        try:
                            d=datetime.fromisoformat(value.replace('Z','+00:00'));return d.replace(tzinfo=timezone.utc).timestamp() if d.tzinfo is None else d.timestamp()
                        except (ValueError,TypeError,AttributeError):return 0
                    rows.append(dict(id=cid,label=label,latest=last['body'][:90] if last else '开始新会话',unread=sum(p['author']!='owner' and epoch(p['created_at'])>epoch(stamp) for p in posts),last_at=last['created_at'] if last else None))
                return self.respond(200,dict(channels=rows))
            if route=='/api/project':return self.respond(200,storage.read(root/'project.json'))
            if route=='/api/schedule':return self.respond(200,scheduler.refresh(root))
            name=route[1:]
            if route=='/help':name='help.html'
            if name in STATIC:return self.respond(200,(ASSETS/name).read_bytes(),mimetypes.guess_type(name)[0] or 'application/octet-stream')
            if re.fullmatch(r'/(?:art|reactions)/[a-z0-9_-]+\.(?:svg|png|json)',route):
                path=contained(ASSETS,route[1:])
                if path.is_file():return self.respond(200,path.read_bytes(),mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            if re.fullmatch(r'/room-reactions/[0-9]+\.png',route):
                name=route.rsplit('/',1)[1]
                if name in {row['file'] for row in assets.emote_manifest()}:
                    path=contained(root/'emotes',name)
                    if path.is_file():return self.respond(200,path.read_bytes(),'image/png')
            if re.fullmatch(r'/generated/(?:owner|Claude|GPT)/(?:avatar|calm|surprised|wink|smile|shy|teary|happy|sleepy|proud|reading|heart|cheer|pout|confused|thinking|panic)(?:\.(?:png|svg))?',route):
                who,mood=route.split('/')[-2:];mood=re.sub(r'\.(?:png|svg)$','',mood)
                path=generated_asset(root,who,mood)
                svg_headers=[('Content-Security-Policy',"sandbox; default-src 'none'; style-src 'unsafe-inline'")]
                if path:
                    svg=path.suffix=='.svg'
                    return self.respond(200,path.read_bytes(),'image/svg+xml' if svg else 'image/png',headers=svg_headers if svg else ())
                who='user' if who=='owner' else who.lower()
                bundled=ASSETS/'art'/(f'avatar-{who}.png' if mood=='avatar' else f'{who}-{mood}.png')
                if bundled.is_file():return self.respond(200,bundled.read_bytes(),'image/png')
                fallback=ASSETS/'art'/(f'avatar-{who}.svg' if mood=='avatar' else f'{who}-{mood}.svg')
                if not fallback.is_file():fallback=ASSETS/'art'/f'{who}-{MOOD_ALIASES.get(mood,"calm")}.svg'
                return self.respond(200,fallback.read_bytes(),'image/svg+xml',headers=svg_headers)
            if re.fullmatch(r'/chat-img/[a-f0-9]{32}\.png',route):
                if not any(route.rsplit('/',1)[1] in p.get('images',[]) for p in project.all_posts(root)):return self.respond(404,dict(error='Choose an active conversation image'))
                path=contained(root/'attachments/discussion/images',route.rsplit('/',1)[1])
                if path.is_file():return self.respond(200,path.read_bytes(),'image/png')
            if re.fullmatch(r'/chat-file/[a-f0-9]{32}\.[a-z0-9]+',route):
                identifier=route.rsplit('/',1)[1]
                try:meta,path=contacts.download(root,identifier)
                except ValueError:return self.respond(404,dict(error='Choose a conversation file'))
                from urllib.parse import quote
                return self.respond(200,path.read_bytes(),'application/octet-stream',headers=[('Content-Disposition',"attachment; filename*=UTF-8''"+quote(meta['name']))])
            if route.startswith('/files/'):
                path=contained(root,route[len('/files/'):]);allowed={x.get('path') for x in storage.read(root/'overview.json',{}).get('links',[]) if isinstance(x.get('path'),str)}
                if path.is_relative_to(root/'attachments/discussion'):return self.respond(404,dict(error='Choose a public project file'))
                if path.relative_to(root).as_posix() in allowed and path.is_file():
                    from urllib.parse import quote
                    return self.respond(200,path.read_bytes(),mimetypes.guess_type(path.name)[0] or 'application/octet-stream',headers=[('Content-Disposition',"attachment; filename*=UTF-8''"+quote(path.name))])
            return self.respond(404,dict(error='Choose a board page or project attachment'))
        def handle_request(self):
            self.connection.settimeout(20)
            try:self.dispatch()
            except (ValueError,TypeError,KeyError,UnicodeError):self.respond(400,dict(error='Check the project request'))
            except (OSError,TimeoutError):self.respond(503,dict(error='Local storage is busy; try again shortly'))
        do_GET=do_POST=do_HEAD=handle_request
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    return server
