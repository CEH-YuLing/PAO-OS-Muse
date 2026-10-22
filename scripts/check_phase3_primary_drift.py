"""Read-only drift inventory. No row contents, credentials, restore or repair."""
import asyncio,json
from datetime import datetime,timezone
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from check_p11_migration import snapshot

async def main():
    url=make_url(settings().database_url)
    assert url.host=='127.0.0.1' and url.port==15432 and url.database=='pao_acos_local'
    engine=create_async_engine(url)
    recent=[]
    try:
        async with engine.connect() as db:
            columns=list(await db.execute(text("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND data_type IN ('timestamp with time zone','timestamp without time zone') ORDER BY table_name,column_name")))
            for table,column in columns:
                quote=lambda name:'"'+name.replace('"','""')+'"'
                query='SELECT count(*),max('+quote(column)+') FROM '+quote(table)+' WHERE '+quote(column)+">=TIMESTAMP '2026-10-17 07:08:00'"
                count,latest=(await db.execute(text(query))).one()
                if count:recent.append({'table':table,'column':column,'count':count,'latest':str(latest)})
        current=await snapshot(url)
        result={'read_only':True,'observed_at':datetime.now(timezone.utc).isoformat(),'recent_timestamp_inventory':recent,
            'snapshot':current,'prior_ci_snapshot_retained':False,'cause_confirmed':False,
            'warning':'Timestamp inventory is not proof of which process caused a change. Do not rewrite data to match an old snapshot.'}
        (ROOT/'.runtime/phase3-primary-drift.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='snapshot'}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
