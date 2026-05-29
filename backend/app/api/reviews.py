import asyncio
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import (
    ReviewResponse, ReviewListResponse, ReplyResponse, ReplyUpdateRequest, UserInfo,
)
from app.api.auth import get_current_user
from app.models import Hotel, Review, Reply, ReplyStatus, ReviewStatus, SubmitTask, TaskStatus
from app.services.ai_service import generate_reply

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hotels/{hotel_id}/reviews", tags=["点评管理"])


def _get_hotel(hotel_id: str, user_id: str, db: Session) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == user_id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    return hotel


@router.get("", response_model=ReviewListResponse)
def list_reviews(
    hotel_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = None,
    platform: str = None,
    rating_min: float = None,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_hotel(hotel_id, current_user.id, db)
    q = db.query(Review).filter(Review.hotel_id == hotel_id)
    if status:
        q = q.filter(Review.status == status)
    if platform:
        if platform == "demo":
            q = q.filter(Review.platform_review_id.like("demo_%"))
        else:
            q = q.filter(Review.platform == platform, Review.platform_review_id.notlike("demo_%"))
    if rating_min is not None:
        q = q.filter(Review.rating >= rating_min)

    total = q.count()
    items = q.order_by(Review.review_date.desc().nullslast(), Review.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 全量计数（不受分页、筛选影响）
    base_q = db.query(Review).filter(Review.hotel_id == hotel_id)
    pending_total = base_q.filter(Review.status == ReviewStatus.pending_reply).count()
    # 已审核待提交的reply计数
    approved_total = db.query(Reply).join(Review).filter(
        Review.hotel_id == hotel_id,
        Reply.status == ReplyStatus.approved
    ).count()

    result = []
    for r in items:
        latest_reply = None
        if r.replies:
            lr = r.replies[0]
            latest_reply = ReplyResponse(
                id=lr.id, review_id=lr.review_id, ai_model=lr.ai_model,
                ai_text=lr.ai_text, edited_text=lr.edited_text, final_text=lr.final_text,
                status=lr.status.value, submitted_at=lr.submitted_at, created_at=lr.created_at,
            )
        is_demo = bool(r.platform_review_id and r.platform_review_id.startswith("demo_"))
        result.append(ReviewResponse(
            id=r.id, hotel_id=r.hotel_id, platform=r.platform.value if r.platform else None,
            platform_review_id=r.platform_review_id, guest_name=r.guest_name,
            room_type=r.room_type, rating=r.rating, content=r.content,
            check_in_date=r.check_in_date, review_date=r.review_date,
            ai_analysis=r.ai_analysis, status=r.status.value,
            reply_count=len(r.replies), latest_reply=latest_reply, is_demo=is_demo,
            created_at=r.created_at,
        ))

    return ReviewListResponse(total=total, page=page, page_size=page_size, pending_total=pending_total, approved_total=approved_total, items=result)


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(hotel_id: str, review_id: str,
               current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    r = db.query(Review).filter(Review.id == review_id, Review.hotel_id == hotel_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="点评不存在")

    latest_reply = None
    if r.replies:
        lr = r.replies[0]
        latest_reply = ReplyResponse(
            id=lr.id, review_id=lr.review_id, ai_model=lr.ai_model,
            ai_text=lr.ai_text, edited_text=lr.edited_text, final_text=lr.final_text,
            status=lr.status.value, submitted_at=lr.submitted_at, created_at=lr.created_at,
        )
    return ReviewResponse(
        id=r.id, hotel_id=r.hotel_id, platform=r.platform.value if r.platform else None,
        platform_review_id=r.platform_review_id, guest_name=r.guest_name,
        room_type=r.room_type, rating=r.rating, content=r.content,
        check_in_date=r.check_in_date, review_date=r.review_date,
        ai_analysis=r.ai_analysis, status=r.status.value,
        reply_count=len(r.replies), latest_reply=latest_reply, created_at=r.created_at,
    )


@router.post("/{review_id}/generate", response_model=ReplyResponse)
async def generate_reply_for_review(
    hotel_id: str, review_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = _get_hotel(hotel_id, current_user.id, db)
    review = db.query(Review).filter(Review.id == review_id, Review.hotel_id == hotel_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="点评不存在")

    # 构建知识库文本
    knowledge_texts = []
    for entry in sorted(hotel.knowledge_entries, key=lambda e: e.priority, reverse=True):
        knowledge_texts.append(f"{entry.key}: {entry.value}")
    knowledge_text = "\n".join(knowledge_texts) if knowledge_texts else hotel.name

    # 构建模板文本
    template_texts = []
    for tpl in hotel.reply_templates:
        if tpl.is_active:
            template_texts.append(f"[{tpl.category.value}] {tpl.name}: {tpl.text}")
    template_text = "\n".join(template_texts) if template_texts else "暂无参考模板"

    try:
        ai_text = await generate_reply(
            review_content=review.content or "",
            rating=review.rating or 3.0,
            hotel_name=hotel.name,
            reply_tone=hotel.reply_tone or "亲切温暖专业",
            knowledge_text=knowledge_text,
            template_text=template_text,
            provider=hotel.ai_provider or "deepseek",
            model=hotel.ai_model or "",
        )
    except Exception as e:
        # AI失败时使用模板回退
        category = "positive" if (review.rating or 5) >= 4 else "negative" if (review.rating or 5) < 3 else "neutral"
        fallback = next((t for t in hotel.reply_templates if t.category.value == category and t.is_active), None)
        ai_text = fallback.text if fallback else f"尊敬的宾客，感谢您的点评。欢迎再次光临{hotel.name}！"

    reply = Reply(
        review_id=review.id,
        ai_model="deepseek-chat",
        ai_text=ai_text,
        status=ReplyStatus.approved,  # 自动审核，简化操作流程
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return ReplyResponse(
        id=reply.id, review_id=reply.review_id, ai_model=reply.ai_model,
        ai_text=reply.ai_text, edited_text=reply.edited_text, final_text=reply.final_text,
        status=reply.status.value, submitted_at=reply.submitted_at, created_at=reply.created_at,
    )


@router.put("/{review_id}/reply", response_model=ReplyResponse)
def update_reply(hotel_id: str, review_id: str, data: ReplyUpdateRequest,
                 current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    review = db.query(Review).filter(Review.id == review_id, Review.hotel_id == hotel_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="点评不存在")

    reply = db.query(Reply).filter(Reply.review_id == review_id).order_by(Reply.created_at.desc()).first()
    if not reply:
        raise HTTPException(status_code=404, detail="未生成回复，请先生成")

    reply.edited_text = data.edited_text
    reply.status = ReplyStatus.approved
    db.commit()
    db.refresh(reply)
    return ReplyResponse(
        id=reply.id, review_id=reply.review_id, ai_model=reply.ai_model,
        ai_text=reply.ai_text, edited_text=reply.edited_text, final_text=reply.final_text,
        status=reply.status.value, submitted_at=reply.submitted_at, created_at=reply.created_at,
    )


@router.post("/{review_id}/submit")
async def submit_reply(hotel_id: str, review_id: str,
                 current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    review = db.query(Review).filter(Review.id == review_id, Review.hotel_id == hotel_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="点评不存在")

    reply = db.query(Reply).filter(Reply.review_id == review_id).order_by(Reply.created_at.desc()).first()
    if not reply:
        raise HTTPException(status_code=404, detail="未生成回复")

    reply.final_text = reply.edited_text or reply.ai_text
    db.commit()

    # 演示数据直接标记为已提交
    if review.platform_review_id and review.platform_review_id.startswith("demo_"):
        reply.status = ReplyStatus.submitted
        reply.submitted_at = datetime.utcnow()
        review.status = ReviewStatus.replied
        db.commit()
        db.refresh(reply)
        return ReplyResponse(
            id=reply.id, review_id=reply.review_id, ai_model=reply.ai_model,
            ai_text=reply.ai_text, edited_text=reply.edited_text, final_text=reply.final_text,
            status=reply.status.value, submitted_at=reply.submitted_at, created_at=reply.created_at,
        )

    # 真实数据：创建提交任务
    from app.api.tasks import _running_submit_tasks, _run_submit

    task = SubmitTask(
        id=str(uuid.uuid4()),
        hotel_id=hotel_id,
        platform=review.platform.value if review.platform else "ctrip",
        status=TaskStatus.pending,
        total_count=1,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    pair = {
        "review_id": review.id,
        "reply_id": reply.id,
        "reply_text": reply.final_text,
        "guest_name": review.guest_name or "",
        "content": review.content or "",
    }
    _running_submit_tasks[task.id] = asyncio.create_task(_run_submit(task.id, hotel_id, [pair]))

    return {"task_id": task.id, "status": "pending", "message": "提交任务已启动"}


@router.post("/batch-generate")
async def batch_generate(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = _get_hotel(hotel_id, current_user.id, db)
    pending_reviews = db.query(Review).filter(
        Review.hotel_id == hotel_id,
        Review.status == ReviewStatus.pending_reply,
    ).all()

    if not pending_reviews:
        return {"generated": 0, "details": []}

    # 预计算共用数据（避免并发访问 ORM 关系）
    knowledge_texts = [f"{e.key}: {e.value}" for e in sorted(hotel.knowledge_entries, key=lambda e: e.priority, reverse=True)]
    knowledge_text = "\n".join(knowledge_texts) if knowledge_texts else hotel.name
    template_texts = [f"[{t.category.value}] {t.name}: {t.text}" for t in hotel.reply_templates if t.is_active]
    template_text = "\n".join(template_texts) if template_texts else "暂无"

    hotel_name = hotel.name
    reply_tone = hotel.reply_tone or "亲切温暖专业"
    ai_provider = hotel.ai_provider or "deepseek"
    ai_model = hotel.ai_model or ""

    # 预计算回退模板
    fallback_map = {}
    for cat_val, cat_name in [("positive", "positive"), ("negative", "negative"), ("neutral", "neutral")]:
        t = next((t for t in hotel.reply_templates if t.category.value == cat_val and t.is_active), None)
        fallback_map[cat_name] = t.text if t else None

    async def generate_one(review):
        try:
            ai_text = await generate_reply(
                review_content=review.content or "",
                rating=review.rating or 3.0,
                hotel_name=hotel_name,
                reply_tone=reply_tone,
                knowledge_text=knowledge_text,
                template_text=template_text,
                provider=ai_provider,
                model=ai_model,
            )
            return review, ai_text, None
        except Exception as e:
            logger.warning(f"AI生成失败 review={review.id}: {e}")
            category = "positive" if (review.rating or 5) >= 4 else "negative" if (review.rating or 5) < 3 else "neutral"
            fallback_text = fallback_map.get(category)
            ai_text = fallback_text or f"尊敬的宾客，感谢您的点评。欢迎再次光临{hotel_name}！"
            return review, ai_text, str(e)

    # 并发调用 AI（不涉及 DB，协程安全）
    gen_results = await asyncio.gather(*[generate_one(r) for r in pending_reviews])

    results = []
    for review, ai_text, error in gen_results:
        reply = Reply(review_id=review.id, ai_model="deepseek-chat", ai_text=ai_text, status=ReplyStatus.approved)
        db.add(reply)
        results.append({"review_id": review.id, "status": "generated", "error": error})

    db.commit()
    return {"generated": len(results), "details": results}


@router.post("/batch-submit")
async def batch_submit(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    approved_replies = db.query(Reply).join(Review).filter(
        Review.hotel_id == hotel_id,
        Reply.status == ReplyStatus.approved,
    ).all()

    if not approved_replies:
        raise HTTPException(status_code=400, detail="没有待提交的回复")

    # 构建提交对
    demo_pairs = []
    real_pairs = []
    for reply in approved_replies:
        reply.final_text = reply.edited_text or reply.ai_text
        review = reply.review
        pair = {
            "review_id": review.id,
            "reply_id": reply.id,
            "reply_text": reply.final_text,
            "guest_name": review.guest_name or "",
            "content": review.content or "",
        }
        if review.platform_review_id and review.platform_review_id.startswith("demo_"):
            demo_pairs.append(pair)
        else:
            real_pairs.append(pair)

    # 演示数据直接标记
    now = datetime.utcnow()
    for p in demo_pairs:
        rp = db.query(Reply).filter(Reply.id == p["reply_id"]).first()
        if rp:
            rp.status = ReplyStatus.submitted
            rp.submitted_at = now
            rp.review.status = ReviewStatus.replied
    db.commit()

    if not real_pairs:
        return {"submitted": len(demo_pairs), "mode": "demo_only"}

    # 检查运行中的任务
    from app.api.tasks import _running_submit_tasks, _run_submit
    running = db.query(SubmitTask).filter(
        SubmitTask.hotel_id == hotel_id,
        SubmitTask.status == TaskStatus.running,
    ).first()
    if running:
        raise HTTPException(status_code=400, detail="已有正在执行的提交任务")

    task = SubmitTask(
        id=str(uuid.uuid4()),
        hotel_id=hotel_id,
        platform="ctrip",
        status=TaskStatus.pending,
        total_count=len(real_pairs) + len(demo_pairs),
        success_count=len(demo_pairs),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    _running_submit_tasks[task.id] = asyncio.create_task(_run_submit(task.id, hotel_id, real_pairs))

    return {"task_id": task.id, "status": "pending", "total": len(real_pairs), "message": "提交任务已启动"}
