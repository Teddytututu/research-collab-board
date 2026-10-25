"""Quota-aware advice. Provider schedules are applied by the responsible assistant."""
import hashlib,json,math
from datetime import datetime,timezone
from . import storage
AGENTS=('Claude','GPT')
TIERS={'plenty':.7,'normal':.4,'tight':.15,'low':.03,'充足':.7,'一般':.4,'紧张':.15,'见底':.03}
ALPHA=.3

def quota_provenance(report):
    """Presentation facts are separate from the algorithm's planning defaults."""
    source=report.get('source');precision=report.get('precision','band');reported=report.get('updated_at')
    status='reported-estimate' if reported else 'unreported'
    if reported:
        if source=='configured-band-estimate':status='configured-estimate'
        elif source in ['manual-band-estimate','operator-report']:status='manual-estimate'
        elif source and report.get('observed_at') is not None:
            status={'provider_percent':'native','restriction':'restriction','stale-conservative-bound':'conservative-bound'}.get(precision,status)
    return dict(status=status,source=source,precision=precision,tier=report.get('tier'),
                observed_at=report.get('observed_at'),reported_at=reported)

def number(v,low=0,high=1e6):
    if isinstance(v,bool):raise ValueError('A finite number is required')
    x=float(v)
    if not math.isfinite(x) or not low<=x<=high:raise ValueError('Value is outside the accepted range')
    return x

def compute_schedule(agents,work,previous=None,now=None):
    import time
    now=time.time() if now is None else now;previous=previous or {};rows={};capacities={}
    for name in AGENTS:
        report=agents.get(name,{});jobs=work.get(name,{});prev=previous.get('agents',{}).get(name,{})
        raw=number(report.get('remaining',TIERS.get(report.get('tier','plenty'),.7)),0,1)
        hours=number(report.get('reset_hours',24));cost=.01
        history=report.get('history',[])[-20:]
        if 'before' in report and 'after' in report:history=history+[report]
        sampled=set()
        for h in history:
            before=number(h['before'],0,1);after=number(h['after'],0,1)
            if h.get('precision',report.get('precision'))=='provider_percent':
                sample=h.get('cost_sample_id')
                if not sample or before<=after or sample in sampled:continue
                sampled.add(sample)
            if after<=before:cost=(1-ALPHA)*cost+ALPHA*(before-after)
        reset=bool(report.get('reset')) or ('before' in report and report.get('after',0)>report['before'])
        digest=hashlib.sha256(json.dumps(dict(report=report,work=jobs),sort_keys=True,allow_nan=False).encode()).hexdigest()
        same=digest==prev.get('input_digest')
        smooth=lambda x,key:x if reset or key not in prev else (1-ALPHA)*prev[key]+ALPHA*x
        remaining=prev.get('smoothed_remaining',raw) if same else smooth(raw,'smoothed_remaining')
        reset_hours=prev.get('smoothed_reset_hours',hours) if same else smooth(hours,'smoothed_reset_hours')
        budget=remaining/max(reset_hours,.5)
        active=number(jobs.get('active',0));review=number(jobs.get('review',0));mentioned=bool(jobs.get('mentioned'))
        deadline=jobs.get('deadline_unix');urgent=deadline is not None and 0<=number(deadline)-now<=7200
        paused=raw<.1 and not mentioned and review==0
        interval=min(240,max(20,60*cost/(.3*max(budget,1e-12))))
        reason='按每小时额度分配巡检'
        if active==0 and review==0 and not mentioned:interval=min(240,interval*1.5);reason='空闲时延长巡检间隔'
        if mentioned or urgent:interval=20;reason='回应用户提及或临近截止'
        old=prev.get('interval_minutes')
        if old and abs(interval-old)/old<.2 and not mentioned and not urgent:interval=old;reason='变化低于20%，沿用间隔'
        if paused:interval=None;reason='额度见底，提及或交付验收时唤醒'
        wake=None if paused else now+interval*60
        # Identical GET refreshes preserve the promised wake; a new report advances it.
        if same and prev.get('paused')==paused and (not urgent or old==20) and (paused or (prev.get('next_wake') or 0)>now):wake=prev.get('next_wake',wake)
        rows[name]=dict(remaining=raw,smoothed_remaining=remaining,reset_hours=hours,smoothed_reset_hours=reset_hours,
            budget_per_hour=budget,cost=cost,interval_minutes=interval,next_wake=wake,paused=paused,reason=reason,
            input_digest=digest,reported_at=report.get('updated_at'),active=active,review=review,mentioned=mentioned,
            quota=quota_provenance(report))
        capacities[name]=budget/(1+number(jobs.get('unfinished',active+review)))
    total=sum(capacities.values());share=.5 if total==0 else capacities['Claude']/total
    share=max(.2,min(.8,share));shares={'Claude':share,'GPT':1-share}
    eligible=[n for n in AGENTS if not rows[n]['paused']]
    handoff=max(eligible,key=lambda n:capacities[n]) if eligible else None
    return dict(schema='quota-schedule-v1',updated_at=now,agents=rows,shares=shares,handoff_to=handoff,
                next_wake_iso={n:datetime.fromtimestamp(r['next_wake'],timezone.utc).isoformat() if r['next_wake'] else None for n,r in rows.items()})

def work_state(root):
    project=storage.read(root/'project.json',{});state=storage.read(root/'attachments/state.json',{});work={n:{} for n in AGENTS}
    tasks={}
    board=root/'board.md'
    if board.exists():
        import re
        for line in board.read_text(encoding='utf-8').splitlines():
            cells=[x.strip() for x in line.strip('|').split('|')]
            if len(cells)>=4 and re.fullmatch('T[0-9]+',cells[0]):tasks[cells[0]]=dict(status=cells[2],owner=cells[3])
    for key,value in state.get('tasks',{}).items():tasks[key]=dict(tasks.get(key,{}),**value)
    for t in tasks.values():
        name=t.get('owner')
        if name not in work:continue
        status=t.get('status','')
        if not status.startswith(('done','completed','通过','完成','已完成','取消','已取消','收回')):work[name]['unfinished']=work[name].get('unfinished',0)+1
        if status in ['review','待验收']:work[name]['review']=work[name].get('review',0)+1
        elif status.startswith(('doing','进行中','在跑')):work[name]['active']=work[name].get('active',0)+1
        if t.get('deadline_unix'):work[name]['deadline_unix']=min(work[name].get('deadline_unix',float('inf')),t['deadline_unix'])
    from .project import all_posts,session_message
    posts=sorted(all_posts(root),key=lambda p:p['created_at'])
    for name in AGENTS:
        latest=next((p for p in reversed(posts) if p['author']==name and session_message(p)),None)
        work[name]['mentioned']=any(p['author']=='owner' and '@'+name.lower() in p['body'].lower() and (latest is None or p['created_at']>latest['created_at']) for p in posts)
    return work

def refresh(root):
    root=__import__('pathlib').Path(root)
    with storage.locked(root):
        agents=storage.read(root/'attachments/agents.json',{});old=storage.read(root/'attachments/schedule.json',{})
        value=compute_schedule(agents,work_state(root),old);storage.write(root/'attachments/schedule.json',value);return value

def report(root,name,**value):
    from datetime import datetime
    if name not in AGENTS:raise ValueError('Choose Claude or GPT')
    with storage.locked(root):
        path=root/'attachments/agents.json';agents=storage.read(path,{})
        old=agents.get(name,{});history=old.get('history',[])[-19:]
        if 'before' in old and 'after' in old:history=history+[{k:old[k] for k in ['before','after','precision','cost_sample_id','cost_precision'] if k in old}]
        if 'before' not in value:old={k:v for k,v in old.items() if k not in ['before','after','cost_sample_id']}
        if 'source' in value and value['source']!=old.get('source'):
            old={k:v for k,v in old.items() if k not in ['observed_at','observed_before','observed_after','cost_precision','resolution','reset_source']}
        agents[name]=dict(old,**value,history=history,updated_at=datetime.now().astimezone().isoformat())
        compute_schedule(agents,{})
        storage.write(path,agents)
    return refresh(root)
