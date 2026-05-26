from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import (
    ReviewResponse, ReviewListResponse, ReplyResponse, ReplyUpdateRequest, UserInfo,
)
from app.api.auth import get_current_user
from app.models import Hotel, Review, Reply, ReplyStatus, ReviewStatus
from app.services.ai_service import generate_reply

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


@router.post("/{review_id}/submit", response_model=ReplyResponse)
def submit_reply(hotel_id: str, review_id: str,
                 current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    review = db.query(Review).filter(Review.id == review_id, Review.hotel_id == hotel_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="点评不存在")

    reply = db.query(Reply).filter(Reply.review_id == review_id).order_by(Reply.created_at.desc()).first()
    if not reply:
        raise HTTPException(status_code=404, detail="未生成回复")

    reply.final_text = reply.edited_text or reply.ai_text
    reply.status = ReplyStatus.submitted
    reply.submitted_at = __import__("datetime").datetime.utcnow()
    review.status = ReviewStatus.replied

    # 使用模板则增加计数
    db.commit()
    db.refresh(reply)
    return ReplyResponse(
        id=reply.id, review_id=reply.review_id, ai_model=reply.ai_model,
        ai_text=reply.ai_text, edited_text=reply.edited_text, final_text=reply.final_text,
        status=reply.status.value, submitted_at=reply.submitted_at, created_at=reply.created_at,
    )


@router.post("/batch-generate")
async def batch_generate(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = _get_hotel(hotel_id, current_user.id, db)
    pending_reviews = db.query(Review).filter(
        Review.hotel_id == hotel_id,
        Review.status == ReviewStatus.pending_reply,
    ).all()

    results = []
    for review in pending_reviews:
        knowledge_texts = [f"{e.key}: {e.value}" for e in sorted(hotel.knowledge_entries, key=lambda e: e.priority, reverse=True)]
        knowledge_text = "\n".join(knowledge_texts) if knowledge_texts else hotel.name
        template_texts = [f"[{t.category.value}] {t.name}: {t.text}" for t in hotel.reply_templates if t.is_active]
        template_text = "\n".join(template_texts) if template_texts else "暂无"

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
        except Exception:
            category = "positive" if (review.rating or 5) >= 4 else "negative" if (review.rating or 5) < 3 else "neutral"
            fallback = next((t for t in hotel.reply_templates if t.category.value == category and t.is_active), None)
            ai_text = fallback.text if fallback else f"尊敬的宾客，感谢您的点评。欢迎再次光临{hotel.name}！"

        reply = Reply(review_id=review.id, ai_model="deepseek-chat", ai_text=ai_text, status=ReplyStatus.approved)
        db.add(reply)
        results.append({"review_id": review.id, "status": "generated"})

    db.commit()
    return {"generated": len(results), "details": results}


@router.post("/batch-submit")
def batch_submit(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    approved_replies = db.query(Reply).join(Review).filter(
        Review.hotel_id == hotel_id,
        Reply.status == ReplyStatus.approved,
    ).all()

    count = 0
    now = __import__("datetime").datetime.utcnow()
    for reply in approved_replies:
        reply.final_text = reply.edited_text or reply.ai_text
        reply.status = ReplyStatus.submitted
        reply.submitted_at = now
        reply.review.status = ReviewStatus.replied
        count += 1

    db.commit()
    return {"submitted": count}
