from uuid import uuid4
import pytest
from pao.modules.schedules.policy import SchedulePreview,preview


def spec(**kwargs):
    return SchedulePreview(kind='studio_workflow',mode='cron',timezone='America/New_York',
        cron=kwargs.pop('cron','30 2 * * *'),after=kwargs.pop('after','2026-03-08T05:00:00Z'),
        now=kwargs.pop('now','2026-03-08T09:00:00Z'),**kwargs)


def test_spring_gap_is_skipped():
    result=preview(spec())
    assert result['due_count']==0 and result['next_at']=='2026-03-09T06:30:00+00:00'
    assert result['execution_enabled'] is False and result['needs_review'] is False


@pytest.mark.parametrize('fold,expected',[('first','2026-11-01T05:30:00+00:00'),('second','2026-11-01T06:30:00+00:00')])
def test_fall_fold_has_one_occurrence(fold,expected):
    result=preview(spec(cron='30 1 * * *',after='2026-11-01T04:00:00Z',now='2026-11-01T08:00:00Z',fold=fold))
    assert result['due_count']==1 and result['occurrences'][0]['utc']==expected


def test_skip_and_coalesce_are_explicit():
    args={'cron':'*/15 * * * *','after':'2026-01-01T00:00:00Z','now':'2026-01-01T01:01:00Z'}
    result=preview(spec(**args));assert result['due_count']==4 and len(result['occurrences'])==1
    skipped=preview(spec(**args,misfire='skip',grace_seconds=30));assert skipped['occurrences']==[]


def test_dom_dow_or_and_sunday_alias():
    result=preview(spec(cron='0 0 15 * 7',after='2026-01-03T05:00:00Z',now='2026-01-04T06:00:00Z'))
    assert result['due_count']==1


@pytest.mark.parametrize('cron',['* * * *','60 * * * *','*/0 * * * *','0 0 0 * *','0 0 * 13 *','0 0 * * 8','@reboot','1-0 * * * *'])
def test_invalid_cron(cron):
    with pytest.raises(ValueError):preview(spec(cron=cron))


def test_once_offset_and_boundary():
    body=SchedulePreview(kind='automation_follow_up',mode='once',timezone='Asia/Ho_Chi_Minh',
        once_at='2026-10-09T09:00:00+07:00',after='2026-10-09T01:00:00Z',now='2026-10-09T02:00:00Z')
    result=preview(body);assert result['due_count']==1 and result['next_at'] is None
    assert result['owner']=='automation.PaoAutomationWorkflow'
    body.after=body.now;assert preview(body)['due_count']==0


@pytest.mark.parametrize('value',['2026-03-08T05:00:00','bad'])
def test_no_naive_or_invalid_clock(value):
    with pytest.raises(ValueError):preview(spec(after=value))


async def test_preview_scoped_and_no_schedule_execution(client,identity):
    url='/v1/schedules/preview?workspace_id='+identity['workspace']
    body=spec().model_dump()
    result=await client.post(url,headers=identity['owner'],json=body)
    assert result.status_code==200 and result.json()['schedule_enabled'] is False
    assert (await client.post(url,headers=identity['outsider'],json=body)).status_code==404
    assert (await client.post(url,json=body)).status_code==401
    body['timezone']='Nonexistent/Zone'
    assert (await client.post(url,headers=identity['owner'],json=body)).status_code==422
    assert (await client.get('/v1/schedules/owners?workspace_id='+str(uuid4()),headers=identity['owner'])).status_code==404
