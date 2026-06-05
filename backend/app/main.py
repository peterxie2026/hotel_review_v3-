from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.models import *  # 确保所有模型被加载
from app.api.auth import router as auth_router
from app.api.hotels import router as hotels_router
from app.api.accounts import router as accounts_router
from app.api.knowledge import router as knowledge_router
from app.api.templates import router as templates_router
from app.api.reviews import router as reviews_router
from app.api.tasks import router as tasks_router
from app.api.report import router as report_router
from app.api.dashboard import router as dashboard_router
from app.api.subscription import router as subscription_router
from app.browser import get_browser_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建表
    Base.metadata.create_all(bind=engine)
    # 预热浏览器池
    try:
        await get_browser_pool()
    except Exception:
        pass
    # 启动定时调度器
    from app.services.scheduler_service import get_scheduler
    try:
        await get_scheduler()
    except Exception:
        pass
    yield
    # 关闭调度器
    from app.services.scheduler_service import _scheduler
    if _scheduler:
        await _scheduler.stop()
    # 关闭浏览器池
    from app.browser.pool import _browser_pool
    if _browser_pool:
        await _browser_pool.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(hotels_router)
app.include_router(accounts_router)
app.include_router(knowledge_router)
app.include_router(templates_router)
app.include_router(reviews_router)
app.include_router(tasks_router)
app.include_router(report_router)
app.include_router(dashboard_router)
app.include_router(subscription_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": settings.VERSION}
