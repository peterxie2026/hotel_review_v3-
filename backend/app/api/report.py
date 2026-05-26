from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import get_db
from app.schemas import HotelReport, UserInfo
from app.api.auth import get_current_user
from app.models import Hotel, Review, ReviewStatus

router = APIRouter(prefix="/api/v1/hotels/{hotel_id}/report", tags=["点评报告"])


@router.get("", response_model=HotelReport)
def get_report(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(
        Hotel.id == hotel_id, Hotel.user_id == current_user.id, Hotel.is_active == True
    ).first()
    if not hotel:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="酒店不存在")

    reviews = db.query(Review).filter(Review.hotel_id == hotel_id).all()

    total = len(reviews)
    pending = sum(1 for r in reviews if r.status == ReviewStatus.pending_reply)
    replied = sum(1 for r in reviews if r.status == ReviewStatus.replied)
    reply_rate = round(replied / total * 100, 1) if total > 0 else 100.0

    # 平均评分
    ratings = [r.rating for r in reviews if r.rating]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

    # 评分分布
    rating_dist = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for r in reviews:
        if r.rating:
            bucket = str(min(int(r.rating), 5))
            rating_dist[bucket] = rating_dist.get(bucket, 0) + 1

    # 平台分布
    platform_dist = {}
    for r in reviews:
        p = r.platform.value if r.platform else "unknown"
        platform_dist[p] = platform_dist.get(p, 0) + 1

    # 月度趋势（最近6个月）
    monthly = {}
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    for r in reviews:
        if r.review_date and r.review_date >= six_months_ago:
            month_key = r.review_date.strftime("%Y-%m")
            if month_key not in monthly:
                monthly[month_key] = {"month": month_key, "count": 0, "replied": 0}
            monthly[month_key]["count"] += 1
            if r.status == ReviewStatus.replied:
                monthly[month_key]["replied"] += 1
    monthly_trends = sorted(monthly.values(), key=lambda x: x["month"])

    # 最近5条
    recent = sorted(
        [r for r in reviews if r.review_date],
        key=lambda r: r.review_date,
        reverse=True,
    )[:5]
    recent_list = [
        {
            "id": r.id,
            "guest_name": r.guest_name or "匿名",
            "rating": r.rating or 0,
            "content": (r.content or "")[:80] + ("..." if r.content and len(r.content) > 80 else ""),
            "status": r.status.value if r.status else "unknown",
            "review_date": r.review_date.isoformat() if r.review_date else None,
        }
        for r in recent
    ]

    return HotelReport(
        hotel_name=hotel.name,
        total_reviews=total,
        pending_reviews=pending,
        replied_reviews=replied,
        reply_rate=reply_rate,
        avg_rating=avg_rating,
        rating_distribution=rating_dist,
        platform_distribution=platform_dist,
        monthly_trends=monthly_trends,
        recent_reviews=recent_list,
    )
