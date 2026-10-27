"""Project-local ETA tracking from measured active time and explicit task forecasts."""
import copy,csv,hashlib,io,json,math,re,threading,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from . import storage
TZ=timezone(timedelta(hours=8))
REFRESH_LOCK=threading.RLock()
MAX_GAP=1800
def manual_kind(task_id):return 'manual:'+str(task_id)
def unix(value):
    if isinstance(value,(int,float)) and not isinstance(value,bool):return float(value)
    if not isinstance(value,str):return None
    match=re.search(r'(?:19|20)\d\d-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:[+-]\d\d:\d\d|Z)?',value)
    if not match:return None
    try:
        d=datetime.fromisoformat(match[0].replace('Z','+00:00'))
        return (d if d.tzinfo else d.replace(tzinfo=TZ)).timestamp()
    except ValueError:return None



def iso(value):return datetime.fromtimestamp(value,TZ).isoformat()



def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)



def duration(seconds):
    minutes=max(1,math.ceil(max(0,seconds)/60))
    return str(minutes)+'分钟' if minutes<60 else (str(round(minutes/60,1)).rstrip('0').rstrip('.')+'小时')



def valid_intervals(samples):
    rows=sorted({s['at']:s for s in samples if number(s.get('at')) and number(s.get('done'))}.values(),key=lambda s:s['at'])
    output=[]
    for a,b in zip(rows,rows[1:]):
        dt=b['at']-a['at'];dd=b['done']-a['done']
        if not (0<dt<=MAX_GAP and dd>=0 and a.get('active') and b.get('active') and a.get('phase')==b.get('phase') and a.get('total')==b.get('total')):continue
        if number(a.get('active_seconds')) and number(b.get('active_seconds')):
            dt=b['active_seconds']-a['active_seconds']
            if not 0<dt<=b['at']-a['at']:continue
        output.append(dict(start=a['at'],end=b['at'],seconds=dt,increment=dd))
    return output



def speed(samples,now):
    intervals=valid_intervals(samples)
    recent=[r for r in intervals if r['start']>=now-3600 and r['end']<=now]
    def rate(rows):
        elapsed=sum(r['seconds'] for r in rows);gain=sum(r['increment'] for r in rows)
        return (gain/elapsed,elapsed,gain) if elapsed>0 and gain>0 else (None,elapsed,gain)
    # A recent estimate needs a window covering at least thirty minutes.
    r,elapsed,gain=rate(recent)
    span=recent[-1]['end']-recent[0]['start'] if recent else 0
    if r and span>=1800 and elapsed>=1800:return dict(rate=r,source='recent',seconds=elapsed,increment=gain,confidence='中')
    r,elapsed,gain=rate(intervals)
    if r:return dict(rate=r,source='historical',seconds=elapsed,increment=gain,confidence='低' if elapsed<1800 else '中')
    return dict(rate=None,source='manual',seconds=0,increment=0,confidence='低')



def correction(rows,kind='experiment'):
    latest={}
    for row in rows:
        row_kind=manual_kind(row['task_id']) if row.get('kind')=='manual' and kind.startswith('manual:') else row.get('kind')
        if row_kind==kind and row.get('valid_for_calibration') and number(row.get('ratio')) and 0.1<=row['ratio']<=10:
            prior=latest.get(row['task_id'])
            if prior is None or row.get('issued_at',0)>prior.get('issued_at',0):latest[row['task_id']]=row
    values=[r['ratio'] for r in latest.values()]
    return (sum(values)/len(values) if len(values)>=3 else 1.0),len(values)



def estimate(run,samples,now,factor=1.0,calibration_n=0,manual=None):
    done,total=run.get('done',0),run.get('total',0)
    if total>0 and done>=total:return dict(mode='complete',at=None,confidence='高',basis='本阶段 '+str(done)+' / '+str(total)+' 已完成',overdue=False)
    measured=speed([s for s in samples if s.get('phase')==run.get('phase') and s.get('total')==total],now)
    remaining=(total-done)/measured['rate']*factor if measured['rate'] else (manual or {}).get('remaining_seconds')
    basis=('近30–60分钟' if measured['source']=='recent' else '历史有效运行')+'完成 '+str(measured['increment'])+' 项，用时 '+duration(measured['seconds']) if measured['rate'] else (manual or {}).get('basis','按任务范围人工估计')
    if measured['rate']:basis+='；剩余 '+str(max(0,total-done))+' 项'
    if factor!=1:basis+='；按 '+str(calibration_n)+' 个同类交付的平均偏差乘 '+str(round(factor,2))
    if not run.get('active',True):
        return dict(mode='conditional' if run.get('stale') else 'paused',at=None,remaining_seconds=remaining,confidence=measured['confidence'],basis=basis,condition='最新运行状态确认' if run.get('stale') else run.get('condition','恢复运行'),overdue=False,rate_source=measured['source'])
    if remaining is not None:
        # Anchor a prediction to its observation, rather than moving it on every GET.
        at=run.get('at',now)+max(0,remaining)
        return dict(mode='estimate',at=iso(at),remaining_seconds=max(0,remaining),confidence=measured['confidence'],basis=basis,overdue=at<now,rate_source=measured['source'])
    fallback=copy.deepcopy(manual or {})
    fallback.update(mode='conditional',confidence='低',basis=basis,overdue=False)
    fallback.setdefault('condition','取得阶段运行速度后更新')
    return fallback



TERMINAL={'review','handoff','complete','completed','accepted_complete','done','delivered'}

def round_start(task):
    return max([unix(task.get(k)) or 0 for k in ['claimed_at','round_started_at','started_at']])


def deliveries(task):
    rows=[dict(r) for r in task.get('completion_history',[]) if isinstance(r,dict) and unix(r.get('at')) is not None]
    times=[unix(task.get(k)) for k in ['actual_completion','actual_completed_at','completed_at']]
    times=[v for v in times if v is not None]
    if times:rows.append(dict(at=iso(max(times)),scope=task.get('completion_scope','上一轮交付')))
    actual=actual_time(task)
    if actual:rows.append(dict(at=actual,scope=task.get('completion_scope','已交付')))
    return list({iso(unix(r['at'])):dict(r,at=iso(unix(r['at']))) for r in rows}.values())


def current_eta(task):
    value=task.get('eta') if isinstance(task.get('eta'),dict) else {}
    at=unix(value.get('at'))
    if at is None or at<round_start(task):return {}
    return value


def actual_time(task):
    if task.get('state') and task['state'] not in TERMINAL:return None
    start=round_start(task)
    explicit=[unix(task.get(k)) for k in ['actual_completion','actual_completed_at','completed_at']]
    valid=[v for v in explicit if v is not None and v>=start]
    if valid:return iso(max(valid))
    released=unix(task.get('released_at'))
    return iso(released) if task.get('state') in TERMINAL and released is not None and released>=start else None



def confidence(task):
    match=re.search(r'(?:把握[：:]?\s*([高中低])|[（(]([高中低])(?:等)?(?:把握)?[）)])',str(task.get('estimated_completion','')))
    value=next((v for v in match.groups() if v),'低') if match else task.get('eta_confidence',task.get('confidence','低'))
    return {'high':'高','medium':'中','low':'低'}.get(value,value)



def task_basis(task,manual):
    text=str(task.get('estimated_completion',''))
    inline=text.split('·',1)[1].strip() if '·' in text else None
    return inline or task.get('eta_basis') or task.get('estimate_basis') or task.get('basis') or (manual or {}).get('basis') or '执行者按当前工作量估计'



def task_estimate(task,manual,now):
    actual=unix(actual_time(task))
    if actual:return dict(mode='complete',actual_at=iso(actual),confidence='高',basis='本轮已交付',overdue=False)
    if str(task.get('estimated_completion','')).startswith('持续'):
        return dict(mode='continuous',confidence='高',basis='持续任务按实验队列完成条件交付',overdue=False)
    declared=current_eta(task)
    expected=unix(task.get('estimated_completion'))
    if expected is not None and expected<round_start(task):expected=None
    at=unix(declared.get('at')) if declared else expected
    if at is not None:
        return dict(mode='estimate',at=iso(at),confidence=declared.get('confidence',confidence(task)),basis=declared.get('basis',task_basis(task,manual)),revision_reason=declared.get('revision_reason',''),overdue=at<now)
    condition=re.search(r'等(.+?)后约\s*([0-9.]+)\s*小时',str(task.get('estimated_completion','')))
    if condition:return dict(mode='conditional',condition=condition[1],short_condition=(manual or {}).get('short_condition',condition[1]),remaining_seconds=float(condition[2])*3600,confidence=confidence(task),basis=task_basis(task,manual),overdue=False)
    result=copy.deepcopy(manual or dict(mode='conditional',condition='本轮工作量确认',short_condition='本轮估时',confidence='低',basis='接手后30分钟内给出范围估计'))
    result.setdefault('mode','conditional');result.setdefault('confidence','低');result['overdue']=bool(unix(result.get('at')) and unix(result['at'])<now)
    return result



def calibration_row(task_id,prediction,actual):
    issued=unix(prediction.get('issued_at'));expected=unix(prediction.get('at'));actual=unix(actual)
    if expected is None or actual is None:return None
    valid=issued is not None and issued<expected and issued<actual
    interrupted=prediction.get('interruption_seconds',0)
    return dict(task_id=task_id,prediction_id=prediction.get('id',hashlib.sha256((task_id+str(issued)+str(expected)).encode()).hexdigest()[:16]),
        kind=prediction.get('kind','manual'),issued_at=issued,predicted_at=iso(expected),actual_at=iso(actual),
        expected_seconds=expected-issued if valid else None,actual_seconds=actual-issued if valid else None,delay_seconds=actual-expected,
        ratio=(actual-issued)/(expected-issued) if valid else None,interruption_seconds=interrupted,
        valid_for_calibration=valid and interrupted==0,basis=prediction.get('basis','执行者预计'))



def live_runs(state,at=None):
    """Read generic project stages, with freshness checked per observation."""
    at=time.time() if at is None else at
    raw=state.get('runs',{})
    candidates=[dict(value,id=key) for key,value in raw.items() if isinstance(value,dict)] if isinstance(raw,dict) else [dict(value) for value in raw if isinstance(value,dict)]
    for task_id,task in state.get('tasks',{}).items():
        if isinstance(task,dict):candidates.extend(dict(row,task_id=task_id) for row in task.get('eta_stages',[]) if isinstance(row,dict))
    result={}
    for row in candidates:
        if not row.get('id') or not number(row.get('done')) or not number(row.get('total')) or row['total']<=0:continue
        source=unix(row.get('source_at',row.get('observed_at',row.get('at',at))))
        fresh=source is not None and 0<=at-source<=1200
        row.update(phase=row.get('phase','work'),name=row.get('name',row['id']),source_at=source,
                   at=source if source is not None else at,done=max(0,min(row['done'],row['total'])),
                   active=bool(row.get('active',True) and fresh),stale=not fresh,
                   condition=row.get('condition','执行条件恢复'))
        result[row['id']]=row
    return list(result.values())

def snapshot(state,overview,now=None):
    now=time.time() if now is None else now
    tracker=state.get('eta_tracking',{});history=tracker.get('observations',{});manual=tracker.get('manual',{})
    factor,n=correction(tracker.get('calibration_rows',[]))
    out=copy.deepcopy(overview or {});existing=[dict(r) for r in out.get('runs',[]) if isinstance(r,dict)]
    for run in live_runs(state,now):
        saved=tracker.get('run_estimates',{}).get(run['id'],{})
        fingerprint={'version':3,**{k:run.get(k) for k in ('done','total','phase','active','stale')}}
        eta=copy.deepcopy(saved['eta']) if saved.get('fingerprint')==fingerprint else estimate(run,history.get(run['id'],[]),now,factor,n,manual.get(run['id']))
        if eta.get('at'):eta['overdue']=unix(eta['at'])<now
        row=next((r for r in existing if r.get('id',r.get('task_id'))==run['id']),None)
        if row is None:row={};existing.append(row)
        row.update(run,eta=eta,status='完成' if run['done']>=run['total'] else '进行中' if run['active'] else '状态更新中' if run.get('stale') else '已暂停')
    out['runs']=existing
    out['task_etas']={key:task_estimate(value,manual.get(key),now) for key,value in state.get('tasks',{}).items() if isinstance(value,dict)}
    for key,eta in out['task_etas'].items():
        label=state['tasks'][key].get('completion_label')
        if eta['mode']=='complete' and label:eta['completion_label']=label
    for run in existing:
        if run.get('id') in out['task_etas'] and run.get('eta'):out['task_etas'][run['id']]=copy.deepcopy(run['eta'])
    for key,eta in out['task_etas'].items():
        task=state.get('tasks',{}).get(key,{})
        events=tracker.get('task_milestones',{}).get(key,[])+deliveries(task)
        current=unix(eta.get('actual_at'));start=round_start(task)
        prior={r['at']:r for r in events if unix(r.get('at')) is not None and unix(r['at'])!=current and (not start or unix(r['at'])<start)}
        if prior:eta['previous_deliveries']=sorted(prior.values(),key=lambda r:unix(r['at']))
        scope=task.get('current_scope') or (task.get('completion_scope') if eta['mode']=='complete' else None)
        if scope:eta['current_scope']=scope
        if key in tracker.get('historical_delays',{}):eta['historical_revision']=tracker['historical_delays'][key]
    for key,value in manual.items():
        if key not in out['task_etas'] and not any(row.get('id')==key for row in existing):out['task_etas'][key]=task_estimate({},value,now)
    return out

def record(state,now=None):
    now=time.time() if now is None else now
    tracker=state.setdefault('eta_tracking',{});history=tracker.setdefault('observations',{})
    for run in live_runs(state,now):
        rows=history.setdefault(run['id'],[])
        sample={k:run[k] for k in ['at','phase','total','done','active','source_at']}
        if number(run.get('active_seconds')):sample['active_seconds']=run['active_seconds']
        if not rows or sample['done']!=rows[-1]['done'] or sample['active']!=rows[-1]['active'] or now-rows[-1]['at']>=300:rows.append(sample)
        history[run['id']]=rows[-3000:]
    predictions=tracker.setdefault('predictions',{})
    completed=tracker.setdefault('calibration_rows',[]);ids={r['prediction_id'] for r in completed}
    for task_id,task in state.get('tasks',{}).items():
        if not isinstance(task,dict):continue
        start=round_start(task);eta=current_eta(task);expected=eta.get('at') or task.get('estimated_completion');actual=actual_time(task)
        milestones=tracker.setdefault('task_milestones',{}).setdefault(task_id,[])
        known={r['at'] for r in milestones}
        for delivery in deliveries(task):
            if delivery['at'] not in known:milestones.append(delivery);known.add(delivery['at'])
        rounds=tracker.setdefault('task_rounds',{}).setdefault(task_id,[])
        if not rounds or rounds[-1]['started_at']!=start:rounds.append(dict(started_at=start,state=task.get('state'),observed_at=iso(now)))
        rounds[-1].update(state=task.get('state'),last_observed_at=iso(now))
        seq=predictions.setdefault(task_id,[])
        if unix(expected) is not None and unix(expected)>=start and (not actual or unix(expected)!=unix(actual)):
            issued=unix(eta.get('issued_at') or task.get('eta_issued_at'))
            if issued is None:issued=now if seq and any(p.get('round_started_at')==start for p in seq) else max(start,unix(task.get('updated_at') or task.get('claimed_at') or task.get('started_at')) or now)
            row=dict(at=iso(unix(expected)),issued_at=issued,round_started_at=start,kind=task.get('eta_kind',manual_kind(task_id)),basis=eta.get('basis',task_basis(task,{})),revision_reason=eta.get('revision_reason','按本轮工作量估计'))
            if not seq or seq[-1]['at']!=row['at'] or seq[-1].get('round_started_at',0)!=start:seq.append(row)
        if actual:
            for prediction in seq:
                same_round=prediction.get('round_started_at',unix(prediction.get('issued_at')) or 0)>=start
                if not same_round:continue
                row=calibration_row(task_id,prediction,actual)
                if row and row['prediction_id'] not in ids:completed.append(row);ids.add(row['prediction_id'])
    cache=tracker.setdefault('run_estimates',{})
    factor,n=correction(completed)
    for run in live_runs(state,now):
        fp={'version':3,**{k:run.get(k) for k in ('done','total','phase','active','stale')}}
        previous=cache.get(run['id'],{})
        if previous.get('fingerprint')==fp:continue
        if run['done']>=run['total'] and previous.get('eta',{}).get('at'):
            closed=calibration_row(run['id'],dict(at=previous['eta']['at'],issued_at=previous.get('issued_at'),kind='experiment',basis=previous['eta'].get('basis','')),now)
            if closed and closed['prediction_id'] not in ids:completed.append(closed);ids.add(closed['prediction_id'])
        eta=estimate(run,history.get(run['id'],[]),now,factor,n,tracker.get('manual',{}).get(run['id']))
        if previous:
            reason='按最新数量与运行条件修订'
            if unix(previous.get('eta',{}).get('at')) and unix(previous['eta']['at'])<now:reason='上次预计已超时，按最新进度修订'
            eta['revision_reason']=reason
            tracker.setdefault('estimate_history',{}).setdefault(run['id'],[]).append(dict(previous,ended_at=iso(now),reason=reason))
        cache[run['id']]=dict(fingerprint=fp,eta=eta,issued_at=iso(now))
    tracker['updated_at']=iso(now)
    tracker['calibration_factor'],tracker['calibration_sample_count']=correction(completed)
    return tracker


def export_csv(root,rows):
    fields=['task_id','prediction_id','kind','issued_at','predicted_at','actual_at','expected_seconds','actual_seconds','delay_seconds','ratio','interruption_seconds','valid_for_calibration','basis']
    with storage.locked(root):
        path=storage.relative_file(root,'attachments/eta/estimates.csv');raw=path.read_bytes() if path.exists() else b''
        existing=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))) if raw else []
        known={row['prediction_id'] for row in existing};new=[row for row in rows if row['prediction_id'] not in known]
        if not new:return
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
        if not raw:writer.writeheader()
        for row in new:writer.writerow(row)
        storage.write_bytes(path,raw+stream.getvalue().encode('utf-8'))

def project(root,overview,now=None):
    """Read persisted observations and project ETA without recording a poll."""
    state=storage.read(Path(root)/'attachments/state.json',{})
    return snapshot(state,overview,now) if state else overview or {}


def refresh(root,overview,now=None):
    """Timed patrol writer; retain observation throttling and calibration history."""
    root=Path(root);now=time.time() if now is None else now;path=root/'attachments/state.json'
    if not path.exists():return overview or {}
    with REFRESH_LOCK:
        state=storage.read(path,{})
        tracker=state.get('eta_tracking',{})
        signature=hashlib.sha256(json.dumps([[{k:v for k,v in run.items() if k!='at'} for run in live_runs(state,now)],{k:(v.get('eta'),v.get('estimated_completion'),actual_time(v),round_start(v),v.get('state'),v.get('completion_scope'),v.get('current_scope'),v.get('completion_history'),v.get('eta_confidence'),v.get('eta_basis')) for k,v in state.get('tasks',{}).items() if isinstance(v,dict)}],sort_keys=True,default=str).encode()).hexdigest()
        last=unix(tracker.get('updated_at')) or 0
        if signature!=tracker.get('signature') or now-last>=300:
            def change(current):record(current,now);current['eta_tracking']['signature']=signature
            state=storage.update_json(root,'attachments/state.json',change)
            export_csv(root,state['eta_tracking'].get('calibration_rows',[]))
        return snapshot(state,overview,now)
