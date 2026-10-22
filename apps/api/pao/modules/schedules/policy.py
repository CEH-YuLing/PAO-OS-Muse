"""Bounded UTC evaluation of five-field numeric cron, no polling or execution.

DST gaps are skipped; folds use an explicit first/second occurrence policy.
DOM and DOW follow cron's OR rule when both fields are restricted.
"""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from typing import Literal
from pydantic import Field
from ..studio.contracts import Closed

OWNERS={'ads_report':'business.report_scheduler',
        'ads_sync':'business.warehouse_scheduler',
        'automation_follow_up':'automation.PaoAutomationWorkflow',
        'studio_workflow':'runtime.dispatch_studio_schedules.v1','bounded_goal':'runtime.dispatch_studio_schedules.v1',
        'business_plan_report':'runtime.dispatch_studio_schedules.v1'}


class SchedulePreview(Closed):
    kind:Literal['ads_report','ads_sync','automation_follow_up','studio_workflow','bounded_goal','business_plan_report']
    mode:Literal['once','cron']
    timezone:str=Field(min_length=1,max_length=80)
    cron:str|None=Field(default=None,max_length=120)
    once_at:str|None=Field(default=None,max_length=40)
    after:str=Field(max_length=40)
    now:str=Field(max_length=40)
    misfire:Literal['skip','coalesce']='coalesce'
    grace_seconds:int=Field(default=300,ge=0,le=86400)
    fold:Literal['first','second']='first'


def timestamp(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.utcoffset() is None:raise ValueError('schedule_timestamp_requires_offset')
    return result.astimezone(timezone.utc)


def field(value,low,high):
    result=set()
    for part in value.split(','):
        pieces=part.split('/')
        if len(pieces)>2:raise ValueError('schedule_cron_invalid')
        base=pieces[0];step=int(pieces[1]) if len(pieces)==2 else 1
        if step<1 or step>high-low+1:raise ValueError('schedule_cron_invalid')
        if base=='*':start,end=low,high
        elif '-' in base:start,end=map(int,base.split('-'))
        else:
            start=int(base);end=high if len(pieces)==2 else start
        if not low<=start<=end<=high:raise ValueError('schedule_cron_invalid')
        result.update(range(start,end+1,step))
    return result


def compile_cron(expression):
    parts=expression.split()
    if len(parts)!=5:raise ValueError('schedule_cron_five_fields_required')
    values=[field(part,*bounds) for part,bounds in zip(parts,[(0,59),(0,23),(1,31),(1,12),(0,7)])]
    values[4]={v%7 for v in values[4]}
    return parts,values


def matches(stamp,zone,compiled,fold):
    local=stamp.astimezone(zone);parts,values=compiled
    if local.minute not in values[0] or local.hour not in values[1] or local.month not in values[3]:return False
    dom=local.day in values[2];dow=(local.weekday()+1)%7 in values[4]
    day=(dom or dow) if parts[2]!='*' and parts[4]!='*' else (dom and dow)
    if not day:return False
    # Only filter folds when the wall time is genuinely ambiguous. UTC scanning
    # cannot manufacture a nonexistent spring-forward wall time.
    wall=local.replace(tzinfo=None)
    first=wall.replace(tzinfo=zone,fold=0);second=wall.replace(tzinfo=zone,fold=1)
    if first.utcoffset()!=second.utcoffset() and local.fold!=(0 if fold=='first' else 1):return False
    return True


def preview(body:SchedulePreview):
    zone=ZoneInfo(body.timezone);after=timestamp(body.after);current=timestamp(body.now)
    if current<after:raise ValueError('schedule_window_invalid')
    if current-after>timedelta(days=7):raise ValueError('schedule_misfire_window_exceeds_7_days')
    due=[];next_at=None
    if body.mode=='once':
        if not body.once_at or body.cron is not None:raise ValueError('schedule_once_contract_invalid')
        candidate=timestamp(body.once_at)
        if after<candidate<=current:due=[candidate]
        if candidate>current:next_at=candidate
    else:
        if not body.cron or body.once_at is not None:raise ValueError('schedule_cron_contract_invalid')
        compiled=compile_cron(body.cron)
        cursor=after.replace(second=0,microsecond=0)+timedelta(minutes=1)
        end=current+timedelta(days=366)
        while cursor<=end:
            if matches(cursor,zone,compiled,body.fold):
                if cursor<=current:due.append(cursor)
                else:next_at=cursor;break
            cursor+=timedelta(minutes=1)
    selected=due[-1:] if body.misfire=='coalesce' else [s for s in due if (current-s).total_seconds()<=body.grace_seconds]
    owner=OWNERS[body.kind]
    return {'owner':owner,'execution_enabled':False,'schedule_enabled':False,
        'preview_only':True,'timezone':body.timezone,'fold':body.fold,
        'due_count':len(due),'coalesced_count':len(due)-len(selected),
        'occurrences':[{'utc':s.isoformat(),'local':s.astimezone(zone).isoformat(),
            'dedupe_slot':body.timezone+':'+s.astimezone(zone).strftime('%Y-%m-%dT%H:%M')} for s in selected],
        'next_at':next_at.isoformat() if next_at else None,
        'next_search_horizon_days':366,'needs_review':owner=='unassigned' or (body.mode=='cron' and next_at is None)}
