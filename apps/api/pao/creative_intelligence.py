"""Deterministic, read-only creative intelligence over the local Ads warehouse."""
import hashlib
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from .models import (AdEntity, AdMetric, CreativeAnalysisRun, CreativeAsset,
    CreativeFeature, CreativeLearning, CreativeMetadata, CreativePerformance, now)
from .warehouse import ATTRIBUTION

ZERO=Decimal('0')
Q=Decimal('.000001')

def ratio(a,b,multiplier=Decimal('1')):
    return (Decimal(a)*multiplier/Decimal(b)).quantize(Q,rounding=ROUND_HALF_UP) if b else None

def change(current,baseline):
    return ratio(Decimal(current)-Decimal(baseline),abs(Decimal(baseline)),Decimal('100')) if baseline not in (None,0,ZERO) and current is not None else None

def aggregate(rows,start,end):
    chosen=[x for x in rows if start<=x.day<=end]
    spend=sum((Decimal(x.spend or 0) for x in chosen),ZERO);impressions=sum((x.impressions or 0 for x in chosen),0)
    clicks=sum((x.clicks or 0 for x in chosen),0);purchases=sum((Decimal(x.purchase or 0) for x in chosen),ZERO)
    revenue=sum((Decimal(x.revenue or 0) for x in chosen),ZERO);ads={x.entity_id for x in chosen}
    # Reach overlaps when a creative is attached to several ads. Only one-ad frequency is mathematically sound.
    reach=sum((x.reach or 0 for x in chosen),0) if len(ads)==1 else 0
    return {'spend':spend,'impressions':impressions,'clicks':clicks,'purchases':purchases,'revenue':revenue,
        'ctr':ratio(clicks,impressions,Decimal('100')),'cpm':ratio(spend,impressions,Decimal('1000')),
        'cpa':ratio(spend,purchases),'roas':ratio(revenue,spend),'frequency':ratio(impressions,reach) if reach else None,
        'ad_count':len(ads),'coverage_days':len({x.day for x in chosen}),'rows':chosen}

def fingerprint(*parts):
    return hashlib.sha256('\x1f'.join(str(x) for x in parts).encode()).hexdigest()

def duration_bucket(seconds):
    if seconds is None:return None
    if seconds<=15:return '≤15s'
    if seconds<=30:return '16–30s'
    if seconds<=60:return '31–60s'
    return '>60s'

def fatigue(current,baseline,age,config):
    frequency_rise=Decimal(str(config['frequency_rise_pct']));ctr_decline=Decimal(str(config['ctr_decline_pct']))
    cpa_increase=Decimal(str(config['cpa_increase_pct']));cpm_stable=Decimal(str(config['cpm_stable_pct']))
    enough=(current['coverage_days']>=2 and baseline['coverage_days']>=2 and
        current['impressions']>=config['minimum_impressions'] and baseline['impressions']>=config['minimum_impressions'])
    values={'frequency_change_pct':change(current['frequency'],baseline['frequency']),
        'ctr_change_pct':change(current['ctr'],baseline['ctr']),'cpa_change_pct':change(current['cpa'],baseline['cpa']),
        'cpm_change_pct':change(current['cpm'],baseline['cpm']),'current_impressions':current['impressions']}
    flags={'frequency_up':values['frequency_change_pct'] is not None and values['frequency_change_pct']>=frequency_rise,
        'ctr_down':values['ctr_change_pct'] is not None and values['ctr_change_pct']<=-ctr_decline,
        'cpa_up':values['cpa_change_pct'] is not None and values['cpa_change_pct']>=cpa_increase,
        'cpm_stable':values['cpm_change_pct'] is not None and abs(values['cpm_change_pct'])<=cpm_stable,
        'age_reached':age>=config['minimum_age_days'],'saturated':current['impressions']>=config['saturation_impressions']}
    count=sum(flags.values());deterioration=flags['ctr_down'] or flags['cpa_up'];delivery=flags['frequency_up'] or flags['saturated']
    if not enough:status='insufficient';score=ZERO
    elif deterioration and delivery and count>=3:status='fatigued';score=min(Decimal('1'),Decimal(count)/Decimal('6'))
    elif count>=2 and deterioration:status='watch';score=min(Decimal('.75'),Decimal(count)/Decimal('6'))
    else:status='healthy';score=Decimal(count)/Decimal('6')
    confidence=min(Decimal('1'),Decimal(min(current['impressions'],baseline['impressions']))/Decimal(max(config['minimum_impressions']*3,1))) if enough else ZERO
    serial_values={key:str(value) if isinstance(value,Decimal) else value for key,value in values.items()}
    return status,score.quantize(Decimal('.0001')),confidence.quantize(Decimal('.0001')),{**serial_values,**flags,'independent_signal_count':count,'sample_sufficient':enough}

async def analyze(db,conn,user_id,account_id,as_of,request_key,config):
    current_start=as_of-timedelta(days=config['current_days']-1)
    baseline_end=current_start-timedelta(days=1);baseline_start=baseline_end-timedelta(days=config['baseline_days']-1)
    ads=list(await db.scalars(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==account_id,AdEntity.kind=='ad',AdEntity.creative_id.is_not(None))))
    if not ads:raise ValueError('creative_data_unavailable')
    ad_ids=[x.remote_id for x in ads]
    metrics=list(await db.scalars(select(AdMetric).where(AdMetric.connection_id==conn.id,AdMetric.connection_version==conn.version,
        AdMetric.account_id==account_id,AdMetric.level=='ad',AdMetric.granularity=='daily',AdMetric.attribution==ATTRIBUTION,
        AdMetric.entity_id.in_(ad_ids),AdMetric.day.between(baseline_start,as_of))))
    if not metrics:raise ValueError('creative_performance_unavailable')
    latest=max(x.updated_at for x in metrics);account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,
        AdEntity.connection_version==conn.version,AdEntity.account_id==account_id,AdEntity.kind=='account'))
    run=CreativeAnalysisRun(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,user_id=user_id,
        account_id=account_id,request_key=request_key,as_of=as_of,current_days=config['current_days'],baseline_days=config['baseline_days'],
        configuration=config,source_updated_at=latest)
    db.add(run);await db.flush()
    creative_entities={x.remote_id:x for x in await db.scalars(select(AdEntity).where(AdEntity.connection_id==conn.id,
        AdEntity.connection_version==conn.version,AdEntity.account_id==account_id,AdEntity.kind=='creative'))}
    by_creative=defaultdict(list);ad_by_id={x.remote_id:x for x in ads}
    for metric in metrics:
        ad=ad_by_id.get(metric.entity_id)
        if ad:by_creative[ad.creative_id].append(metric)
    features=[];performances=[];assets=[]
    for creative_id,rows in sorted(by_creative.items()):
        entity=creative_entities.get(creative_id);source_job_id=(entity.source_job_id if entity else ad_by_id[rows[0].entity_id].source_job_id)
        asset=await db.scalar(select(CreativeAsset).where(CreativeAsset.connection_id==conn.id,CreativeAsset.connection_version==conn.version,
            CreativeAsset.account_id==account_id,CreativeAsset.creative_id==creative_id))
        if not asset:
            previous=await db.scalar(select(CreativeAsset).where(CreativeAsset.connection_id==conn.id,CreativeAsset.account_id==account_id,
                CreativeAsset.creative_id==creative_id).order_by(CreativeAsset.connection_version.desc()).limit(1))
            asset=CreativeAsset(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,account_id=account_id,
                creative_id=creative_id,name=entity.name if entity else None,source_job_id=source_job_id,
                first_seen_at=previous.first_seen_at if previous else entity.created_at if entity else min(x.created_at for x in rows));db.add(asset);await db.flush()
            if previous:
                prior_meta=await db.scalar(select(CreativeMetadata).where(CreativeMetadata.asset_id==previous.id))
                if prior_meta:
                    fields=('brand_id','product','market','language','format','duration_seconds','hook','angle','offer','cta','creator','landing_page')
                    db.add(CreativeMetadata(asset_id=asset.id,workspace_id=conn.workspace_id,source='imported',updated_by=user_id,
                        **{key:getattr(prior_meta,key) for key in fields}))
        else:asset.name=entity.name if entity else asset.name;asset.source_job_id=source_job_id;asset.last_seen_at=now()
        assets.append(asset)
        current=aggregate(rows,current_start,as_of);baseline=aggregate(rows,baseline_start,baseline_end)
        for sample_window,start,end,data in [('current',current_start,as_of,current),('baseline',baseline_start,baseline_end,baseline)]:
            row=CreativePerformance(run_id=run.id,asset_id=asset.id,sample_window=sample_window,period_start=start,period_end=end,
                currency=account.currency,timezone=account.timezone,**{k:data[k] for k in ('spend','impressions','clicks','purchases','revenue','ctr','cpm','cpa','roas','frequency','ad_count','coverage_days')})
            db.add(row);performances.append(row)
        age=max(0,(as_of-asset.first_seen_at.date()).days)
        status,score,confidence,signals=fatigue(current,baseline,age,config)
        brief={} if status!='fatigued' else {'objective':'refresh_creative','requirements':{'hooks':5,'angles':3,'ctas':2},
            'hooks':['Lead with the customer problem','Open with a specific result','Use a proof-first demonstration','Create a before/after contrast','Ask a curiosity-driven question'],
            'angles':['Problem and consequence','Proof and mechanism','Outcome and objection handling'],
            'ctas':['See how it works','Compare the offer now'],'recommended_duration':'test_shorter_variant',
            'recommended_format':'preserve_winner_then_test_one_variable','requires_human_review':True}
        feature=CreativeFeature(run_id=run.id,asset_id=asset.id,fatigue_status=status,fatigue_score=score,confidence=confidence,
            age_days=age,signals=signals,strategy_brief=brief);db.add(feature);features.append(feature)
    await db.flush()
    metadata={x.asset_id:x for x in await db.scalars(select(CreativeMetadata).where(CreativeMetadata.asset_id.in_([x.id for x in assets])))}
    current_by_asset={x.asset_id:x for x in performances if x.sample_window=='current'}
    learning_ids=[]
    dimensions={'hook':lambda m:m.hook,'angle':lambda m:m.angle,'format':lambda m:m.format,
        'duration':lambda m:duration_bucket(m.duration_seconds),'market':lambda m:m.market}
    for dimension,getter in dimensions.items():
        groups=defaultdict(list)
        for asset in assets:
            meta=metadata.get(asset.id);perf=current_by_asset[asset.id];value=getter(meta) if meta else None
            if value and perf.impressions>=config['minimum_impressions']:groups[value].append(perf)
        if len(groups)<2:continue
        scored=[]
        for value,items in groups.items():
            impressions=sum(x.impressions for x in items);clicks=sum(x.clicks for x in items);spend=sum((x.spend for x in items),ZERO);purchases=sum((x.purchases for x in items),ZERO)
            scored.append((ratio(spend,purchases) if purchases else None,ratio(clicks,impressions,Decimal('100')),value,impressions,len(items)))
        conversions=[x for x in scored if x[0] is not None]
        ranked=sorted(conversions,key=lambda x:x[0]) if len(conversions)>=2 else sorted(scored,key=lambda x:x[1] or ZERO,reverse=True)
        best=ranked[0];metric='CPA' if len(conversions)>=2 else 'CTR';metric_value=best[0] if metric=='CPA' else best[1]
        confidence=min(Decimal('.95'),Decimal(best[3])/Decimal(max(config['minimum_impressions']*5,1))).quantize(Decimal('.0001'))
        key=fingerprint(conn.id,conn.version,account_id,dimension,best[2]);learning=await db.scalar(select(CreativeLearning).where(CreativeLearning.fingerprint==key))
        evidence={'metric':metric,'metric_value':str(metric_value),'impressions':best[3],'creative_count':best[4],'compared_values':len(groups),'as_of':as_of.isoformat()}
        statement=f'{dimension} “{best[2]}” đang dẫn đầu theo {metric} trong mẫu đủ điều kiện.'
        if not learning:
            learning=CreativeLearning(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,account_id=account_id,
                latest_run_id=run.id,dimension=dimension,value=best[2],statement=statement,confidence=confidence,evidence=evidence,fingerprint=key);db.add(learning)
        else:
            learning.latest_run_id=run.id;learning.statement=statement;learning.confidence=confidence;learning.evidence=evidence;learning.status='active';learning.last_seen_at=now()
        await db.flush();learning_ids.append(learning.id)
    run.summary={'creative_count':len(assets),'fatigued_count':sum(x.fatigue_status=='fatigued' for x in features),
        'watch_count':sum(x.fatigue_status=='watch' for x in features),'insufficient_count':sum(x.fatigue_status=='insufficient' for x in features),
        'learning_count':len(learning_ids),'asset_ids':[x.id for x in assets],'learning_ids':learning_ids,
        'periods':{'current':[current_start.isoformat(),as_of.isoformat()],'baseline':[baseline_start.isoformat(),baseline_end.isoformat()]},
        'attribution':ATTRIBUTION,'read_only':True}
    await db.flush();return run
