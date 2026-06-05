from sqlalchemy.orm import Session
from datetime import datetime
from app.models import UserSubscription, SubscriptionStatus, Hotel


def check_hotel_limit(db: Session, user_id: str) -> bool:
    """检查用户是否可以创建更多酒店，返回 (ok, error_message)"""
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id
    ).first()
    if not sub:
        return True, None  # 没有订阅记录，允许（新用户）

    # 检查试用是否到期
    if sub.status == SubscriptionStatus.trialing:
        if sub.trial_end_at and datetime.utcnow() > sub.trial_end_at:
            sub.status = SubscriptionStatus.expired
            db.commit()
            return False, "免费试用已到期，请升级套餐后继续使用"

    if sub.status == SubscriptionStatus.expired:
        return False, "订阅已到期，请续费后继续使用"

    if sub.status == SubscriptionStatus.cancelled:
        return False, "订阅已取消，请重新订阅后继续使用"

    # 检查酒店数量限制
    plan = sub.plan
    if plan and plan.hotel_limit > 0:
        current_count = db.query(Hotel).filter(
            Hotel.user_id == user_id, Hotel.is_active == True
        ).count()
        if current_count >= plan.hotel_limit:
            return False, f"当前套餐（{plan.name}）最多可管理 {plan.hotel_limit} 家酒店，您已有 {current_count} 家。请升级套餐或删除不需要的酒店"

    return True, None


def check_review_limit(db: Session, user_id: str, new_count: int = 1) -> bool:
    """检查用户本月是否超出点评抓取限制"""
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id
    ).first()
    if not sub:
        return True, None

    if sub.status == SubscriptionStatus.trialing:
        if sub.trial_end_at and datetime.utcnow() > sub.trial_end_at:
            sub.status = SubscriptionStatus.expired
            db.commit()
            return False, "免费试用已到期，请升级套餐后继续使用"

    if sub.status in (SubscriptionStatus.expired, SubscriptionStatus.cancelled):
        return False, "订阅已到期或已取消，请续费后继续使用"

    plan = sub.plan
    if plan and plan.review_limit_monthly > 0:
        # 计算当月已抓取点评数
        from app.models import ScrapeTask, TaskStatus
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_tasks = db.query(ScrapeTask).filter(
            ScrapeTask.hotel.has(user_id=user_id),
            ScrapeTask.created_at >= month_start,
            ScrapeTask.status == TaskStatus.completed,
        ).all()
        month_reviews = sum(t.reviews_new for t in month_tasks)

        if month_reviews + new_count > plan.review_limit_monthly:
            return False, (
                f"本月点评抓取已达 {month_reviews} 条，当前套餐（{plan.name}）"
                f"每月限制 {plan.review_limit_monthly} 条。请升级套餐"
            )

    return True, None
