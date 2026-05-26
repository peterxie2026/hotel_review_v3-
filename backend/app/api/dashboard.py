from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import get_db
from app.schemas import DashboardSummary, UserInfo
from app.api.auth import get_current_user
from app.models import Hotel, Review, ReviewStatus

router = APIRouter(prefix="/api/v1/dashboard", tags=["仪表盘"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotels = db.query(Hotel).filter(Hotel.user_id == current_user.id, Hotel.is_active == True).all()
    hotel_ids = [h.id for h in hotels]

    total_reviews = db.query(func.count(Review.id)).filter(Review.hotel_id.in_(hotel_ids)).scalar() or 0
    pending = db.query(func.count(Review.id)).filter(
        Review.hotel_id.in_(hotel_ids),
        Review.status == ReviewStatus.pending_reply,
    ).scalar() or 0

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    replied_today = db.query(func.count(Review.id)).filter(
        Review.hotel_id.in_(hotel_ids),
        Review.status == ReviewStatus.replied,
        Review.updated_at >= today,
    ).scalar() or 0

    reply_rate = round(pending / total_reviews * 100, 1) if total_reviews > 0 else 100.0

    return DashboardSummary(
        total_hotels=len(hotels),
        total_reviews=total_reviews,
        pending_reviews=pending,
        replied_today=replied_today,
        reply_rate=reply_rate,
    )
