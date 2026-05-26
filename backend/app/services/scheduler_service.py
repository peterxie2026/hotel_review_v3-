import asyncio
import json
from datetime import datetime, date
from app.database import SessionLocal
from app.models import Hotel, OTAAccount, ScrapeTask, TaskStatus, Review, ReviewStatus, Reply, ReplyStatus
from app.services.ai_service import generate_reply


class SchedulerService:
    """后台定时调度：自动抓取 + 自动回复"""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_scrape_dates: dict = {}  # key: hotel_id_platform, value: date
        self._last_reply_dates: dict = {}   # key: hotel_id, value: date

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _should_run_now(self, times: list, date_key: str, track: dict) -> bool:
        """检查当前时间是否匹配配置的时间列表（每分钟检查一次，同一天同一时间只执行一次）"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today = now.date()

        if current_time not in times:
            return False

        last_date = track.get(date_key)
        if last_date == today:
            return False

        return True

    async def _loop(self):
        """主循环，每分钟检查一次"""
        while self._running:
            try:
                await self._check_and_run()
            except Exception:
                pass
            await asyncio.sleep(60)

    async def _check_and_run(self):
        db = SessionLocal()
        try:
            hotels = db.query(Hotel).filter(Hotel.is_active == True).all()
            now = datetime.now()
            today = now.date()

            for hotel in hotels:
                config = hotel.schedule_config or {}
                if not isinstance(config, dict):
                    config = {}

                # === 自动抓取 ===
                scrape_cfg = config.get("auto_scrape", {})
                if scrape_cfg.get("enabled") and scrape_cfg.get("times"):
                    for platform in ["ctrip", "meituan", "fliggy"]:
                        key = f"{hotel.id}_{platform}"
                        if self._should_run_now(scrape_cfg["times"], key, self._last_scrape_dates):
                            self._last_scrape_dates[key] = today
                            account = db.query(OTAAccount).filter(
                                OTAAccount.hotel_id == hotel.id,
                                OTAAccount.platform == platform,
                                OTAAccount.is_active == True,
                            ).first()
                            if account:
                                import uuid
                                task = ScrapeTask(
                                    id=str(uuid.uuid4()),
                                    hotel_id=hotel.id,
                                    platform=platform,
                                    status=TaskStatus.pending,
                                )
                                db.add(task)
                                db.commit()
                                # 异步执行抓取
                                from app.api.tasks import _run_scrape
                                asyncio.create_task(_run_scrape(task.id, hotel.id, platform))

                # === 自动回复 ===
                reply_cfg = config.get("auto_reply", {})
                if reply_cfg.get("enabled") and reply_cfg.get("times"):
                    key = hotel.id
                    if self._should_run_now(reply_cfg["times"], key, self._last_reply_dates):
                        self._last_reply_dates[key] = today
                        await self._auto_reply(hotel.id, db)
        finally:
            db.close()

    async def _auto_reply(self, hotel_id: str, db):
        """自动为待回复点评生成AI回复并提交"""
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if not hotel:
            return

        # 构建知识库文本
        knowledge_texts = [f"{e.key}: {e.value}" for e in sorted(hotel.knowledge_entries, key=lambda e: e.priority, reverse=True)]
        knowledge_text = "\n".join(knowledge_texts) if knowledge_texts else hotel.name

        # 构建模板文本
        template_texts = [f"[{t.category.value}] {t.name}: {t.text}" for t in hotel.reply_templates if t.is_active]
        template_text = "\n".join(template_texts) if template_texts else "暂无"

        reviews = db.query(Review).filter(
            Review.hotel_id == hotel_id,
            Review.status == ReviewStatus.pending_reply,
        ).all()

        for review in reviews:
            try:
                reply_text = await generate_reply(
                    review_content=review.content or "",
                    rating=review.rating or 3.0,
                    hotel_name=hotel.name,
                    reply_tone=hotel.reply_tone or "亲切温暖专业",
                    knowledge_text=knowledge_text,
                    template_text=template_text,
                )
                if reply_text:
                    reply = Reply(
                        review_id=review.id,
                        ai_model="auto",
                        ai_text=reply_text,
                        final_text=reply_text,
                        status=ReplyStatus.submitted,
                        submitted_at=datetime.utcnow(),
                    )
                    db.add(reply)
                    review.status = ReviewStatus.replied
            except Exception:
                continue

        db.commit()


_scheduler: SchedulerService | None = None


async def get_scheduler() -> SchedulerService:
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
        await _scheduler.start()
    return _scheduler
