import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.store import store
from app.routers import worker, equipment, material, project, schedule, stats

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _daily_sync_job():
    logger.info("执行每日凌晨3点数据同步任务")
    store.sync_from_external_systems()


scheduler = BackgroundScheduler()
scheduler.add_job(
    _daily_sync_job,
    trigger=CronTrigger(hour=3, minute=0),
    id="daily_sync",
    replace_existing=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动应用，加载初始数据")
    store.load_initial_data()
    logger.info("启动定时调度器")
    scheduler.start()
    yield
    logger.info("关闭定时调度器")
    scheduler.shutdown()


app = FastAPI(
    title="建筑公司项目资源调度服务",
    description="管理工人、机械设备、材料按工期分配到多个项目，基于贪心算法的资源平衡调度",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(worker.router)
app.include_router(equipment.router)
app.include_router(material.router)
app.include_router(project.router)
app.include_router(schedule.router)
app.include_router(stats.router)


@app.get("/")
def root():
    return {
        "name": "建筑公司项目资源调度服务",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "workers_count": len(store.workers),
        "equipments_count": len(store.equipments),
        "materials_count": len(store.materials),
        "projects_count": len(store.projects),
        "unresolved_conflicts": len(store.get_unresolved_conflicts()),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    logger.info(f"启动服务，端口: {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
