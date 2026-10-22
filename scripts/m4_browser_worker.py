"""Only fixed internal event receipts on unique test queue; no tools/models/providers."""
import os
from arq import cron
from arq.connections import RedisSettings
from arq.worker import run_worker
from pao.config import settings
from pao.modules.events.delivery import deliver_business_event, dispatch_business_events

config=settings()
assert config.database_url.endswith('/pao_test')
assert RedisSettings.from_dsn(config.redis_url).database==15
queue=os.environ['PAO_M4_BROWSER_QUEUE']
assert queue.startswith('pao-test:m4-browser:')


class Worker:
    functions=[deliver_business_event]
    redis_settings=RedisSettings.from_dsn(config.redis_url)
    queue_name=queue
    handle_signals=False
    max_jobs=1
    job_timeout=20
    keep_result=0
    poll_delay=.1
    health_check_key=queue+':health'
    on_startup=dispatch_business_events
    cron_jobs=[cron(dispatch_business_events,second=set(range(0,60,2)),run_at_startup=True)]


if __name__=='__main__':run_worker(Worker)
