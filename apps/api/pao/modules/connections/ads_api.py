"""Explicit scoped typed read reports, no credentials or provider requests."""
from datetime import date
from uuid import UUID
from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal
from ...db import database
from ...models import AdMetric, AdEntity, MetaSnapshot, MetaSyncJob, GoogleAdsSyncJob, TenantConnectionGrant, TenantConnectionReference
from . import grants, ads_authority


def mount(router):
    @router.get('/ads-accounts')
    async def accounts(workspace_id: UUID, connection_id: UUID, kind: str = Query(pattern='^(meta_ads|google_ads)$'),
                       limit: int = Query(50,ge=1,le=100), offset: int = Query(0,ge=0,le=10000),
                       response: Response = None, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        from .inventory import connection_metadata, account_known
        from .inventory import manager
        response.headers['Cache-Control']='no-store'
        wid,cid=str(workspace_id),str(connection_id)
        await manager(db,wid,who)
        metadata=await connection_metadata(db,wid,who,kind,cid)
        meta=kind=='meta_ads';model=MetaSyncJob if meta else GoogleAdsSyncJob
        column=AdEntity.connection_id if meta else AdEntity.google_connection_id
        provenance=AdEntity.source_job_id if meta else AdEntity.google_source_job_id
        query=select(AdEntity.account_id).join(model,model.id==provenance).where(
            column==cid,AdEntity.connection_version==metadata['config_version'],AdEntity.kind=='account',
            AdEntity.platform==('meta' if meta else 'google'),AdEntity.remote_id==AdEntity.account_id,
            model.connection_id==cid,model.connection_version==metadata['config_version'],model.status=='completed')
        if meta:
            query=query.union(select(MetaSnapshot.remote_key).join(MetaSyncJob).where(
                MetaSyncJob.connection_id==cid,MetaSyncJob.connection_version==metadata['config_version'],
                MetaSyncJob.status=='completed',MetaSyncJob.kind=='accounts',MetaSnapshot.kind=='accounts'))
        q=query.subquery()
        ids=list(await db.scalars(select(q.c[0]).distinct().order_by(q.c[0]).offset(offset).limit(limit+1)))
        items=[]
        for account in ids[:limit]:
            await account_known(db,wid,kind,cid,metadata['config_version'],account)
            items.append({'account_id':account})
        return {'items':items,'has_more':len(ids)>limit,'config_version':metadata['config_version'],
                'source':'local_completed_discovery','provider_health_verified':False}

    @router.get('/ads-grants')
    async def catalog(workspace_id: UUID, response: Response, brand_id: UUID | None = None,
                       limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                       who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        wid = str(workspace_id)
        await grants.active_member(db, wid, who.id)
        brand = str(brand_id) if brand_id else None
        rows = (await db.execute(select(TenantConnectionGrant, TenantConnectionReference.kind)
            .join(TenantConnectionReference, TenantConnectionReference.id == TenantConnectionGrant.reference_id)
            .where(TenantConnectionGrant.workspace_id == wid, TenantConnectionGrant.grantee_id == who.id,
                   TenantConnectionGrant.brand_id == brand, TenantConnectionReference.workspace_id == wid,
                   TenantConnectionReference.kind.in_(('meta_ads', 'google_ads')))
            .order_by(TenantConnectionGrant.created_at, TenantConnectionGrant.id).offset(offset).limit(limit+1))).all()
        items = []
        for grant, kind in rows[:limit]:
            try:
                _, pin = await ads_authority.selected(db, wid, who.id, brand, grant.account_id, grant.id, kind)
            except HTTPException:
                continue
            items.append({'grant_id':grant.id, 'kind':kind, 'brand_id':brand,
                          'account_id':grant.account_id, 'expires_at':pin['expires_at'], 'capability':'ads_read'})
        return {'items':items, 'has_more':len(rows)>limit, 'provider_health_verified':False}

    @router.get('/grants/{grant_id}/ads-report')
    async def report(workspace_id: UUID, grant_id: UUID, response: Response, since: date, until: date,
                     brand_id: UUID | None = None, level: str = Query('campaign',pattern='^(campaign|adset|ad)$'),
                     granularity: str = Query('daily',pattern='^(daily|hourly)$'),
                     offset: int = Query(0,ge=0,le=100000),
                     who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        from ...warehouse_api import MetricOut
        response.headers['Cache-Control'] = 'no-store'
        if not 0 <= (until-since).days < 366:
            raise HTTPException(422, 'ads_report_range_invalid')
        wid = str(workspace_id)
        grant = await db.scalar(select(TenantConnectionGrant).where(
            TenantConnectionGrant.id == str(grant_id), TenantConnectionGrant.workspace_id == wid,
            TenantConnectionGrant.grantee_id == who.id))
        ref = await db.get(TenantConnectionReference, grant.reference_id) if grant else None
        if not ref or ref.kind not in ads_authority.MODELS:
            raise HTTPException(403, ads_authority.DENIED)
        conn, _ = await ads_authority.selected(db,wid,who.id,str(brand_id) if brand_id else None,
                                              grant.account_id,grant.id,ref.kind)
        meta = ref.kind == 'meta_ads'
        job = MetaSyncJob if meta else GoogleAdsSyncJob
        column = AdMetric.connection_id if meta else AdMetric.google_connection_id
        provenance = AdMetric.source_job_id if meta else AdMetric.google_source_job_id
        rows = list(await db.scalars(select(AdMetric).join(job,job.id==provenance).where(
            column==conn.id,AdMetric.connection_version==conn.version,AdMetric.platform==('meta' if meta else 'google'),
            AdMetric.account_id==grant.account_id,AdMetric.level==level,AdMetric.granularity==granularity,
            AdMetric.day>=since,AdMetric.day<=until,job.connection_id==conn.id,
            job.connection_version==conn.version,job.status=='completed',job.kind=='historical',
            job.account_id==grant.account_id).order_by(AdMetric.day.desc(),AdMetric.hour,AdMetric.entity_id)
            .offset(offset).limit(51)))
        return {'rows':[MetricOut.model_validate(row).model_dump(mode='json') for row in rows[:50]],
                'has_more':len(rows)>50,'account_id':grant.account_id,'provider_health_verified':False,
                'scope':'exact_source_version_account','missing_usage_is_zero':False}
