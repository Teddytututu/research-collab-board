"""Credential-free provider observations and bounded native-control requests.

The desktop/stdio host publishes facts; the assistant reports them through the
normal scheduler. This module never reads provider auth or user configuration.
"""
from pathlib import Path
import math, time, uuid
from . import storage
from .scheduler import TIERS
MAX_AGE = 900

def observe_image(root,item):
    if item.get('type')!='imageGeneration':return
    clean={target:item[source] for source,target in [('id','id'),('status','status'),('savedPath','saved_path'),('revisedPrompt','revised_prompt')] if source in item}
    if not clean.get('id'):return
    with storage.locked(root):
        path=Path(root)/'attachments/provider-images.json';rows=storage.read(path,{})
        if rows.get(clean['id'],{}).get('status')=='completed' and clean.get('status')=='in_progress':return
        clean={k:v for k,v in clean.items() if v is not None}
        rows[clean['id']]=dict(rows.get(clean['id'],{}),**clean);storage.write(path,rows)

def finite(value, low, high):
    if isinstance(value, bool):raise ValueError('A finite provider number is required')
    result=float(value)
    if not math.isfinite(result) or not low<=result<=high:raise ValueError('Provider number outside range')
    return result

def observe_codex(root, payload, now=None, invocation_id=None):
    """Accept the account/rateLimits/read result or notification; copy a whitelist."""
    now=time.time() if now is None else now
    snapshot=payload.get('rateLimits') or {}
    windows=[]
    for name in ['primary','secondary']:
        item=snapshot.get(name)
        if not item:continue
        used=finite(item['usedPercent'],0,100)
        reset=finite(item.get('resetsAt'),0,1e12) if item.get('resetsAt') is not None else None
        minutes=finite(item.get('windowDurationMins'),0,1e8) if item.get('windowDurationMins') is not None else None
        if reset is None or reset<=now:continue
        windows.append(dict(name=name,remaining=round(1-used/100,6),resets_at=reset,window_minutes=minutes))
    restriction=payload.get('ordinaryUsageAllowed')
    if not windows and restriction is None:return None
    chosen=min(windows,key=lambda w:(w['remaining']>=.1,w['remaining']/max((w['resets_at']-now)/3600,.5))) if windows else dict(remaining=0,resets_at=None,name=None)
    value=dict(source='codex-app-server',precision='provider_percent',observed_at=now,expires_at=now+MAX_AGE,
               remaining=chosen['remaining'],resets_at=chosen['resets_at'],selected_window=chosen['name'],windows=windows,
               resolution='provider integer percentage; invocation cost below this resolution remains an estimate')
    root=Path(root)
    with storage.locked(root):
        path=root/'attachments/provider-observations.json';observations=storage.read(path,{})
        previous=observations.get('GPT')
        if restriction is False or restriction is None and previous and previous.get('ordinary_usage_allowed') is False:
            value.update(remaining=0,ordinary_usage_allowed=False)
        elif restriction is True:
            value['ordinary_usage_allowed']=True
        if previous and previous.get('source')==value['source'] and previous['observed_at']<now:
            if previous.get('selected_window')==value.get('selected_window') and previous.get('resets_at')==value.get('resets_at'):
                value['previous']=dict(remaining=previous['remaining'],observed_at=previous['observed_at'])
                if invocation_id and previous['remaining']>value['remaining']:
                    if not isinstance(invocation_id,str) or len(invocation_id)>128:raise ValueError('A bounded native invocation ID is required')
                    value['cost_sample_id']=invocation_id
        observations['GPT']=value;storage.write(path,observations)
    return value

def quota(root, agent, now=None, tier='plenty', reset_hours=24):
    if agent not in ['GPT','Claude']:raise ValueError('Choose GPT or Claude')
    now=time.time() if now is None else now
    record=storage.read(Path(root)/'attachments/provider-observations.json',{}).get(agent,{})
    if record.get('ordinary_usage_allowed') is False:
        return dict(remaining=0,reset_hours=max(0,((record.get('resets_at') or now)-now)/3600),
                    ordinary_usage_allowed=False,precision='restriction',source=record['source'],observed_at=record['observed_at'],
                    reset_source='provider restriction; fresh positive observation required',
                    resolution='Provider disabled ordinary work; the restriction survives observation expiry and reset')
    if record and record.get('expires_at',0)>=now and record.get('observed_at',now+1)<=now and (record.get('resets_at') or 0)>now:
        value=dict(remaining=record['remaining'],reset_hours=(record['resets_at']-now)/3600,
                   precision=record['precision'],source=record['source'],observed_at=record['observed_at'],
                   reset_source='provider reset timestamp',resolution=record.get('resolution','provider observation'))
        previous=record.get('previous')
        if previous and previous.get('observed_at',0)>=now-MAX_AGE:
            value.update(observed_before=previous['remaining'],observed_after=record['remaining'],
                         cost_precision='below-provider-resolution' if previous['remaining']==record['remaining'] else 'unattributed-provider-change')
            if record.get('cost_sample_id'):
                value.update(before=previous['remaining'],after=record['remaining'],cost_sample_id=record['cost_sample_id'],cost_precision='quantized-single-invocation')
        return value
    if record and record.get('remaining',1)<.1 and (record.get('resets_at') or 0)>now:
        return dict(remaining=record['remaining'],reset_hours=(record['resets_at']-now)/3600,
                    precision='stale-conservative-bound',source=record['source'],observed_at=record['observed_at'],
                    reset_source='last provider reset timestamp',resolution='Expired low quota remains a conservative bound through its reset')
    return dict(tier=tier,remaining=TIERS[tier],reset_hours=finite(reset_hours,0,1e6),precision='band',
                source='configured-band-estimate',reset_source='configured horizon estimate',
                resolution='labelled quota band; provider measurement unavailable or expired')

def request_goal(root,agent,objective,status='active'):
    if agent not in ['GPT','Claude'] or status not in ['active','complete']:raise ValueError('Bounded goal action required')
    if not isinstance(objective,str) or not 1<=len(objective.strip())<=12000:raise ValueError('Concrete setup objective required')
    row=dict(id=uuid.uuid4().hex,agent=agent,action='goal',status=status,objective=objective,created_at=time.time())
    with storage.locked(root):storage.append(Path(root)/'attachments/provider-requests.jsonl',row)
    return row

def control_row(row):
    """Read earlier flat records while retaining independent goal and patrol IDs."""
    row=dict(row)
    if row.get('kind')=='scheduled-task':
        row.setdefault('patrol',dict(id=row.get('thread_id'),status=row.get('status'),provider=row.get('provider')))
    elif row.get('thread_id'):
        row.setdefault('goal',{k:row[k] for k in ['thread_id','status','provider','objective','request_id'] if k in row})
    if row.get('patrol_id'):
        row.setdefault('patrol',dict(id=row['patrol_id'],status=row.get('patrol_status'),next_wake_unix=row.get('next_wake_unix')))
    return row

def controls(root):return {agent:control_row(row) for agent,row in storage.read(Path(root)/'attachments/provider-controls.json',{}).items()}

def record_native(root,agent,kind,identifier):
    if agent not in ['GPT','Claude'] or kind not in ['goal','scheduled-task'] or not identifier:raise ValueError('An actual native control ID is required')
    def update(rows):
        row=control_row(rows.get(agent,{}));native=dict(provider='assistant-native-tool',status='active',recorded_at=time.time())
        if kind=='goal':
            native['thread_id']=identifier;row['goal']=native;row.update(native,kind='goal')
        else:
            native['id']=identifier;row['patrol']=native
            row.update(patrol_id=identifier,patrol_status='active')
        rows[agent]=row
    storage.update_json(root,'attachments/provider-controls.json',update)

def pending(root):
    with storage.locked(root):
        done=storage.read(Path(root)/'attachments/provider-acks.json',{})
        return [r for r in storage.lines(Path(root)/'attachments/provider-requests.jsonl') if r['id'] not in done]

def acknowledge(root,request_id,result):
    with storage.locked(root):
        req=next(r for r in storage.lines(Path(root)/'attachments/provider-requests.jsonl') if r['id']==request_id)
        clean={k:result[k] for k in ['provider','thread_id','status','next_wake_unix','patrol_id','patrol_status','error'] if k in result}
        clean.update(request_id=request_id,acknowledged_at=time.time())
        acks=storage.read(Path(root)/'attachments/provider-acks.json',{});acks[request_id]=clean
        storage.write(Path(root)/'attachments/provider-acks.json',acks)
        if clean.get('status') in ['active','complete'] and clean.get('thread_id'):
            current=controls(root);row=current.get(req['agent'],{})
            goal=dict(clean,objective=req['objective']);row.update(goal);row['goal']=goal
            if clean.get('patrol_id'):row['patrol']=dict(id=clean['patrol_id'],status=clean.get('patrol_status'),next_wake_unix=clean.get('next_wake_unix'))
            current[req['agent']]=row
            storage.write(Path(root)/'attachments/provider-controls.json',current)
        return clean

class CodexSessionHost:
    """Small host adapter: official RPC goal plus a live-session patrol timer.

    Pass the existing official RPC callable; auth stays with that connection.
    Call apply() during normal event dispatch and dispatch_due() while idle.
    """
    def __init__(self,root,thread_id,rpc):
        self.root=Path(root);self.thread_id=thread_id;self.rpc=rpc;self.timer=None;self.last_dispatched=None;self.closed=False
    def sync_patrol(self):
        if self.closed:return
        with storage.locked(self.root):
            current=controls(self.root);row=current.get('GPT',{})
            if row.get('goal',{}).get('thread_id')!=self.thread_id:
                self.timer=None;return
            advised=storage.read(self.root/'attachments/schedule.json',{}).get('agents',{}).get('GPT',{})
            when=advised.get('next_wake')
            restricted=quota(self.root,'GPT').get('ordinary_usage_allowed') is False
            if restricted or advised.get('paused') or not when:
                self.timer=None;status='paused-quota' if restricted or advised.get('paused') else 'awaiting-schedule'
            elif self.last_dispatched is not None and when<=self.last_dispatched:
                self.timer=None;status='running-session'
            else:
                self.timer=dict(id='session-'+self.thread_id,when=when,prompt='Read docs/patrol.md. Perform one authorized patrol, report quota with scripts/patrol.py GPT --auto, read the schedule and apply the next wake. Keep unchanged healthy states quiet.')
                status='scheduled-session'
            patrol=dict(id='session-'+self.thread_id,status=status,next_wake_unix=self.timer['when'] if self.timer else None)
            updated=dict(row,patrol=patrol,patrol_id=patrol['id'],patrol_status=status,next_wake_unix=patrol['next_wake_unix'])
            if updated!=row:
                current['GPT']=updated;storage.write(self.root/'attachments/provider-controls.json',current)
    def apply(self):
        if self.closed:return []
        results=[]
        for request in pending(self.root):
            if request.get('agent')!='GPT' or request.get('action')!='goal':continue
            try:
                result=self.rpc('thread/goal/set',dict(threadId=self.thread_id,objective=request['objective'],status=request['status']))
                goal=result['goal']
                if goal['threadId']!=self.thread_id or goal['status']!=request['status']:raise ValueError('Native goal acknowledgement mismatch')
                record=dict(provider='codex-app-server',thread_id=goal['threadId'],status=goal['status'])
                acknowledge(self.root,request['id'],record);results.append(dict(request_id=request['id'],native=result))
            except (RuntimeError,KeyError,ValueError) as error:
                acknowledge(self.root,request['id'],dict(provider='codex-app-server',error=type(error).__name__+': native action needs review'))
        self.sync_patrol();return results
    def dispatch_due(self,start_turn,now=None):
        now=time.time() if now is None else now
        self.sync_patrol()
        if self.closed or self.timer is None or self.timer['when']>now:return False
        timer=self.timer;self.timer=None;self.last_dispatched=timer['when']
        self.sync_patrol()
        start_turn(timer['prompt'])
        self.sync_patrol()
        return True
    def close(self):
        self.timer=None;self.closed=True
        with storage.locked(self.root):
            current=controls(self.root);row=current.get('GPT',{})
            if row.get('thread_id')==self.thread_id:
                row.update(patrol_status='stopped-with-host',next_wake_unix=None,host_stopped_at=time.time())
                if row.get('patrol'):row['patrol']=dict(row['patrol'],status='stopped-with-host',next_wake_unix=None)
                storage.write(self.root/'attachments/provider-controls.json',current)
