import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import ScrapeTaskResponse, SubmitTaskResponse, UserInfo, HotelResponse
from app.api.auth import get_current_user
from app.models import Hotel, OTAAccount, ScrapeTask, SubmitTask, TaskStatus, Review, ReviewStatus, Reply, ReplyStatus
from app.services.crypto_service import decrypt_password
import random
import json

router = APIRouter(prefix="/api/v1", tags=["抓取任务"])

# 存储正在运行的后台任务
_running_tasks: dict = {}
_running_submit_tasks: dict = {}

# 演示点评数据
DEMO_REVIEWS = [
    {"guest_name": "张先生", "rating": 5.0, "content": "酒店位置很好，就在嘉陵江边上，房间可以看到江景非常漂亮。前台服务热情周到，入住手续办理很快。房间干净整洁，床品舒适。早餐品种丰富，特别是明宇中餐厅的川菜很正宗。下次来阆中还会选择这里！"},
    {"guest_name": "李女士", "rating": 4.0, "content": "整体体验不错，酒店环境优雅，大堂气派。房间面积够大，设施较新。但隔音效果一般，能听到走廊声音。早餐到10点就结束了，希望能延长一些。游泳池水质很好，孩子们玩得很开心。"},
    {"guest_name": "王先生", "rating": 2.0, "content": "入住体验不太好，预订的江景房给安排了城景，前台说江景房满了。房间空调噪音大，联系工程部维修等了近一个小时。早餐选择少，水果不新鲜。作为五星级酒店，服务和设施都有待提高。"},
    {"guest_name": "赵女士", "rating": 5.0, "content": "非常满意的一次入住！酒店就在阆中古城旁边，步行十分钟就到。前厅小刘服务特别好，帮我们规划了古城游览路线。江景房视野开阔，傍晚看夕阳超美。中餐厅的河鲜是亮点，推荐石锅鱼。一定会再来的！"},
    {"guest_name": "陈先生", "rating": 3.0, "content": "中规中矩吧。酒店硬件不错，但软件服务有待加强。办理入住时前台明显人手不够，排队等了快二十分钟。房间卫生可以，但mini吧是空的。健身房器材比较旧，跑步机屏幕坏了。位置确实方便，就在江边。"},
    {"guest_name": "周女士", "rating": 5.0, "content": "带父母来阆中旅游住的，全家都很满意！酒店安排了高楼层江景房，父母特别喜欢。服务人员很有礼貌，见到客人都会主动问好。早餐的担担面和红油抄手很好吃。离古城近，出行方便。已经推荐给朋友了！"},
    {"guest_name": "吴先生", "rating": 1.0, "content": "非常失望。预定了两个房间，到店后说只有一个房间了，让等了一个多小时才解决。房间有异味，开窗通风了好久。浴室排水不畅，洗澡水漫到房间里。前台处理投诉的态度也很敷衍。不会再来了。"},
    {"guest_name": "刘女士", "rating": 4.0, "content": "公司出差住的，整体感觉不错。房间够大，有办公桌很方便。WiFi速度快，开会视频不卡。早餐种类还行，就是高峰期位置不太好找。酒店有免费停车场，自驾很方便。下次出差还会考虑。"},
]


async def _set_progress(task_id: str, message: str, status: TaskStatus = None):
    """更新任务进度"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
        if task:
            task.progress_message = message
            if status:
                task.status = status
            db.commit()
    finally:
        db.close()


async def _run_scrape(task_id: str, hotel_id: str, platform: str):
    """后台执行抓取"""
    from app.database import SessionLocal
    from app.browser import get_browser_pool
    from app.ota import ADAPTERS
    import json

    db = SessionLocal()
    try:
        task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
        if task:
            task.status = TaskStatus.running
            task.progress_message = "正在准备..."
            task.started_at = datetime.utcnow()
            db.commit()

        # 获取账号信息
        await _set_progress(task_id, "正在查找OTA账号...")
        account = db.query(OTAAccount).filter(
            OTAAccount.hotel_id == hotel_id,
            OTAAccount.platform == platform,
            OTAAccount.is_active == True,
        ).first()
        if not account:
            raise Exception("OTA账号不存在")

        password = decrypt_password(account.encrypted_password or "")
        cookies_json = account.cookies_json

        # 启动浏览器
        await _set_progress(task_id, "正在启动浏览器...")
        pool = await get_browser_pool()
        context = await pool.get_context(account.id, cookies_json)
        page = await context.new_page()

        adapter_cls = ADAPTERS.get(platform)
        if not adapter_cls:
            raise Exception(f"不支持的平台: {platform}")
        adapter = adapter_cls()

        try:
            await _set_progress(task_id, "正在登录OTA后台...")
            # 截图登录前页面
            import os
            os.makedirs("/tmp/ctrip_debug", exist_ok=True)
            try:
                await page.screenshot(path=f"/tmp/ctrip_debug/login_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png", full_page=True)
            except Exception:
                pass
            logged_in = await adapter.login(page, account.username, password)
            if not logged_in:
                # 截图登录后页面用于排查
                try:
                    await page.screenshot(path=f"/tmp/ctrip_debug/login_fail_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png", full_page=True)
                except Exception:
                    pass
                raise Exception("登录失败：账号密码错误或需要验证码，请检查OTA账号配置")

            # 保存cookie
            new_cookies = json.dumps(await context.cookies())
            account.cookies_json = new_cookies
            account.last_login_at = datetime.utcnow()

            # 抓取点评
            await _set_progress(task_id, "正在抓取点评列表...")
            # 先截图保存页面状态便于调试
            try:
                import os
                os.makedirs("/tmp/ctrip_debug", exist_ok=True)
                await page.screenshot(path=f"/tmp/ctrip_debug/screenshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png", full_page=True)
            except Exception:
                pass
            raw_reviews = await adapter.fetch_pending_reviews(page)
        finally:
            await page.close()

        # 保存点评
        await _set_progress(task_id, f"正在保存点评({len(raw_reviews)}条)...")
        new_count = 0
        for r in raw_reviews:
            existing = db.query(Review).filter(
                Review.hotel_id == hotel_id,
                Review.platform == platform,
                Review.platform_review_id == r.platform_review_id,
            ).first()
            ota_status = ReviewStatus.replied if r.has_reply else ReviewStatus.pending_reply
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
                    status=ota_status,
                )
                db.add(review)
                new_count += 1
            elif existing.status != ota_status:
                existing.status = ota_status

        task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
        if task:
            task.status = TaskStatus.completed
            task.reviews_found = len(raw_reviews)
            task.reviews_new = new_count
            task.progress_message = f"完成：找到{len(raw_reviews)}条，新增{new_count}条"
            task.completed_at = datetime.utcnow()
            account.last_scrape_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
        if task:
            task.status = TaskStatus.failed
            task.error_message = str(e)
            task.progress_message = f"失败: {str(e)[:100]}"
            task.completed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
        _running_tasks.pop(task_id, None)


@router.post("/hotels/{hotel_id}/scrape", response_model=ScrapeTaskResponse)
async def trigger_scrape(hotel_id: str, platform: str = "ctrip",
                   current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == current_user.id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")

    account = db.query(OTAAccount).filter(
        OTAAccount.hotel_id == hotel_id,
        OTAAccount.platform == platform,
        OTAAccount.is_active == True,
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail=f"请先配置{platform}账号")

    # 检查是否已有运行中的任务
    running = db.query(ScrapeTask).filter(
        ScrapeTask.hotel_id == hotel_id,
        ScrapeTask.platform == platform,
        ScrapeTask.status == TaskStatus.running,
    ).first()
    if running:
        raise HTTPException(status_code=400, detail="已有正在执行的抓取任务")

    task = ScrapeTask(
        id=str(uuid.uuid4()),
        hotel_id=hotel_id,
        platform=platform,
        status=TaskStatus.pending,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 异步执行
    _running_tasks[task.id] = asyncio.create_task(_run_scrape(task.id, hotel_id, platform))

    return ScrapeTaskResponse.model_validate(task)


@router.get("/tasks/{task_id}", response_model=ScrapeTaskResponse)
def get_task_status(task_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    hotel = db.query(Hotel).filter(Hotel.id == task.hotel_id, Hotel.user_id == current_user.id).first()
    if not hotel:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    return ScrapeTaskResponse.model_validate(task)


@router.get("/tasks")
def list_tasks(hotel_id: str = None, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(ScrapeTask)
    if hotel_id:
        q = q.filter(ScrapeTask.hotel_id == hotel_id)
    else:
        hotel_ids = [h.id for h in db.query(Hotel).filter(Hotel.user_id == current_user.id).all()]
        q = q.filter(ScrapeTask.hotel_id.in_(hotel_ids))
    tasks = q.order_by(ScrapeTask.created_at.desc()).limit(20).all()
    return [ScrapeTaskResponse.model_validate(t) for t in tasks]


@router.post("/hotels/{hotel_id}/demo-reviews", response_model=ScrapeTaskResponse)
def generate_demo_reviews(hotel_id: str, count: int = 8,
                          current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    """生成演示点评数据，用于测试系统功能"""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == current_user.id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")

    task = ScrapeTask(
        id=str(uuid.uuid4()),
        hotel_id=hotel_id,
        platform="ctrip",
        status=TaskStatus.running,
    )
    db.add(task)
    db.commit()

    new_count = 0
    for i, demo in enumerate(DEMO_REVIEWS[:count]):
        platform_review_id = f"demo_{hotel_id[:8]}_{i}"
        existing = db.query(Review).filter(
            Review.hotel_id == hotel_id,
            Review.platform == "ctrip",
            Review.platform_review_id == platform_review_id,
        ).first()
        if not existing:
            from datetime import timedelta
            review = Review(
                hotel_id=hotel_id,
                platform="ctrip",
                platform_review_id=platform_review_id,
                guest_name=demo["guest_name"],
                rating=demo["rating"],
                content=demo["content"],
                check_in_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                review_date=datetime.utcnow() - timedelta(days=random.randint(0, 7)),
                status=ReviewStatus.pending_reply,
            )
            db.add(review)
            new_count += 1

    task.status = TaskStatus.completed
    task.reviews_found = count
    task.reviews_new = new_count
    task.progress_message = f"演示数据：生成{new_count}条点评"
    task.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return ScrapeTaskResponse.model_validate(task)


@router.post("/demo/setup", response_model=HotelResponse)
def demo_setup(current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    """一键体验：创建演示酒店并生成演示点评数据"""
    demo_hotel = Hotel(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name="阆中明宇豪雅度假酒店（演示）",
        brand="明宇商旅",
        address="四川省阆中市阆水中路33号",
        phone="0817-6288888",
        star_rating=5,
        highlights=["嘉陵江景", "阆中古城旁", "川菜美食", "亲子友好"],
        reply_tone="亲切温暖专业",
        ai_provider="deepseek",
    )
    db.add(demo_hotel)
    db.flush()

    # 生成演示点评
    from datetime import timedelta
    new_count = 0
    for i, demo in enumerate(DEMO_REVIEWS):
        existing = db.query(Review).filter(
            Review.hotel_id == demo_hotel.id,
            Review.platform == "ctrip",
            Review.platform_review_id == f"demo_{demo_hotel.id[:8]}_{i}",
        ).first()
        if not existing:
            review = Review(
                hotel_id=demo_hotel.id,
                platform="ctrip",
                platform_review_id=f"demo_{demo_hotel.id[:8]}_{i}",
                guest_name=demo["guest_name"],
                rating=demo["rating"],
                content=demo["content"],
                check_in_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                review_date=datetime.utcnow() - timedelta(days=random.randint(0, 7)),
                status=ReviewStatus.pending_reply,
            )
            db.add(review)
            new_count += 1

    db.commit()
    db.refresh(demo_hotel)
    return HotelResponse(
        id=demo_hotel.id,
        name=demo_hotel.name,
        brand=demo_hotel.brand,
        address=demo_hotel.address,
        phone=demo_hotel.phone,
        star_rating=demo_hotel.star_rating,
        room_count=demo_hotel.room_count,
        highlights=demo_hotel.highlights or [],
        reply_tone=demo_hotel.reply_tone,
        ai_provider=demo_hotel.ai_provider or "deepseek",
        ai_model=demo_hotel.ai_model or "",
        is_active=demo_hotel.is_active,
        schedule_config=demo_hotel.schedule_config,
        ota_count=0,
        pending_review_count=new_count,
        created_at=demo_hotel.created_at,
    )


# ===== OTA回复提交任务 =====

async def _set_submit_progress(task_id: str, message: str, status: TaskStatus = None):
    """更新提交任务进度"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        task = db.query(SubmitTask).filter(SubmitTask.id == task_id).first()
        if task:
            task.progress_message = message
            if status:
                task.status = status
            db.commit()
    finally:
        db.close()


async def _run_submit(task_id: str, hotel_id: str, review_pairs: list):
    """后台执行OTA回复提交"""
    from app.database import SessionLocal
    from app.browser import get_browser_pool
    from app.ota import ADAPTERS

    db = SessionLocal()
    try:
        task = db.query(SubmitTask).filter(SubmitTask.id == task_id).first()
        if task:
            task.status = TaskStatus.running
            task.progress_message = "正在准备..."
            task.started_at = datetime.utcnow()
            db.commit()

        # 获取OTA账号
        await _set_submit_progress(task_id, "正在查找OTA账号...")
        account = db.query(OTAAccount).filter(
            OTAAccount.hotel_id == hotel_id,
            OTAAccount.platform == "ctrip",
            OTAAccount.is_active == True,
        ).first()
        if not account:
            raise Exception("OTA账号不存在")

        password = decrypt_password(account.encrypted_password or "")
        cookies_json = account.cookies_json

        # 启动浏览器
        await _set_submit_progress(task_id, "正在启动浏览器...")
        pool = await get_browser_pool()
        context = await pool.get_context(account.id, cookies_json)
        page = await context.new_page()

        adapter_cls = ADAPTERS.get("ctrip")
        if not adapter_cls:
            raise Exception("不支持的平台: ctrip")
        adapter = adapter_cls()

        try:
            await _set_submit_progress(task_id, "正在登录携程后台...")
            logged_in = await adapter.login(page, account.username, password)
            if not logged_in:
                raise Exception("登录失败：请检查OTA账号")

            # 保存cookie
            new_cookies = json.dumps(await context.cookies())
            account.cookies_json = new_cookies
            account.last_login_at = datetime.utcnow()
            db.commit()

            # 执行提交
            await _set_submit_progress(task_id, f"正在提交回复({len(review_pairs)}条)...")
            results = await adapter.submit_replies_batch(page, review_pairs)

            # 统计结果并更新DB
            success_count = 0
            failed_count = 0
            now = datetime.utcnow()

            for r in results:
                idx = r["index"]
                pair = review_pairs[idx]
                reply_id = pair.get("reply_id")
                review_id = pair.get("review_id")

                if r.get("success"):
                    # 更新reply状态
                    reply = db.query(Reply).filter(Reply.id == reply_id).first()
                    if reply:
                        reply.status = ReplyStatus.submitted
                        reply.submitted_at = now
                    # 更新review状态
                    review = db.query(Review).filter(Review.id == review_id).first()
                    if review:
                        review.status = ReviewStatus.replied
                    success_count += 1
                else:
                    reply = db.query(Reply).filter(Reply.id == reply_id).first()
                    if reply:
                        reply.status = ReplyStatus.failed
                    failed_count += 1

            db.commit()

            task = db.query(SubmitTask).filter(SubmitTask.id == task_id).first()
            if task:
                task.status = TaskStatus.completed
                task.success_count = success_count
                task.failed_count = failed_count
                task.results_json = json.dumps(results, ensure_ascii=False)
                task.progress_message = f"完成：成功{success_count}条，失败{failed_count}条"
                task.completed_at = datetime.utcnow()

            db.commit()

        finally:
            await page.close()

    except Exception as e:
        task = db.query(SubmitTask).filter(SubmitTask.id == task_id).first()
        if task:
            task.status = TaskStatus.failed
            task.error_message = str(e)
            task.progress_message = f"失败: {str(e)[:100]}"
            task.completed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
        _running_submit_tasks.pop(task_id, None)


@router.get("/submit-tasks/{task_id}", response_model=SubmitTaskResponse)
def get_submit_task_status(task_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(SubmitTask).filter(SubmitTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    hotel = db.query(Hotel).filter(Hotel.id == task.hotel_id, Hotel.user_id == current_user.id).first()
    if not hotel:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    return SubmitTaskResponse.model_validate(task)


@router.get("/hotels/{hotel_id}/submit-tasks")
def list_submit_tasks(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == current_user.id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    tasks = db.query(SubmitTask).filter(
        SubmitTask.hotel_id == hotel_id
    ).order_by(SubmitTask.created_at.desc()).limit(10).all()
    return [SubmitTaskResponse.model_validate(t) for t in tasks]
