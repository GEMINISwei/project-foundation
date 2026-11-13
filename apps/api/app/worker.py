"""worker 的進入點: python -m app.worker"""

import asyncio
import signal

from app.registry import ENABLED_MODULES
from shared.db.session import start_engine, stop_engine
from shared.jobs.worker import Worker
from shared.logging import configure_logging
from shared.platform import all_jobs, all_schedules, event_bus
from shared.settings import settings


async def main() -> None:
    configure_logging(json_output=settings.is_production)
    start_engine()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    # 收到停止訊號後做完手上的任務再結束, 不接新的。
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    worker = Worker(
        all_jobs(ENABLED_MODULES), all_schedules(ENABLED_MODULES), event_bus(ENABLED_MODULES)
    )
    try:
        await asyncio.gather(worker.run(stop), worker.heartbeat(stop))
    finally:
        await stop_engine()


if __name__ == "__main__":
    asyncio.run(main())
