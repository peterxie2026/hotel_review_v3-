import json
from datetime import datetime
from app.tasks.celery_app import celery_app
from app.models import ScrapeTask, TaskStatus, Review, ReviewStatus, OTAPlatform
from app.ota import ADAPTERS
from app.browser import get_browser_pool
from app.config import settings


@celery_app.task(bind=True)
def scrape_reviews(self, task_id: str, hotel_id: str, platform: str, account_id: str,
                   username: str, encrypted_password: str, cookies_json: str = None):
    """后台抓取任务"""
    from app.database import SessionLocal
    from app.services.crypto_service import decrypt_password
    import asyncio

    db = SessionLocal()

    try:
        # 更新任务状态
        task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
        if task:
            task.status = TaskStatus.running
            task.started_at = datetime.utcnow()
            task.celery_task_id = self.request.id
            db.commit()

        # 解密密码
        password = decrypt_password(encrypted_password) if encrypted_password else ""

        # 执行抓取
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_do_scrape(hotel_id, platform, username, password, cookies_json, account_id))
        loop.close()

        # 保存结果
        new_count = 0
        for r in result:
            existing = db.query(Review).filter(
                Review.hotel_id == hotel_id,
                Review.platform == platform,
                Review.platform_review_id == r.platform_review_id,
            ).first()
            if not existing:
                review = Review(
                    hotel_id=hotel_id,
                    platform=platform,
                    platform_review_id=r.platform_review_id,
                    guest_name=r.guest_name,
                    room_type=r.room_type,
                    rating=r.rating,
                    content=r.content,
                    check_in_date=r.check_in_date,
                    review_date=r.review_date,
                    status=ReviewStatus.pending_reply,
                )
                db.add(review)
                new_count += 1

        if task:
            task.status = TaskStatus.completed
            task.reviews_found = len(result)
            task.reviews_new = new_count
            task.completed_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        if task:
            task.status = TaskStatus.failed
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        db.close()


async def _do_scrape(hotel_id: str, platform: str, username: str, password: str,
                     cookies_json: str, account_id: str):
    pool = await get_browser_pool()
    context = await pool.get_context(account_id, cookies_json)
    page = await context.new_page()

    adapter_cls = ADAPTERS.get(platform)
    if not adapter_cls:
        raise ValueError(f"不支持的平台: {platform}")

    adapter = adapter_cls()

    try:
        # 登录
        logged_in = await adapter.login(page, username, password)
        if not logged_in:
            raise Exception("登录失败，可能需要手动验证码")

        # 保存cookie（登录成功后的新cookie）
        new_cookies = await pool.save_cookies(account_id)
        from app.database import SessionLocal
        from app.services.crypto_service import encrypt_password
        _db = SessionLocal()
        try:
            from app.models import OTAAccount
            acc = _db.query(OTAAccount).filter(OTAAccount.id == account_id).first()
            if acc:
                acc.cookies_json = new_cookies
                acc.last_login_at = datetime.utcnow()
                _db.commit()
        finally:
            _db.close()

        # 抓取点评
        reviews = await adapter.fetch_pending_reviews(page)
        return reviews
    finally:
        await page.close()
