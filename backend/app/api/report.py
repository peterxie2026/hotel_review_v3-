from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional
import re
from app.database import get_db
from app.schemas import HotelReport, UserInfo
from app.api.auth import get_current_user
from app.models import Hotel, Review, ReviewStatus

router = APIRouter(prefix="/api/v1/hotels/{hotel_id}/report", tags=["点评报告"])

# 好评主题关键词映射
POSITIVE_THEMES = {
    "位置/景观": ["位置", "交通", "地铁", "江景", "夜景", "靠近", "步行", "周边", "古城", "方便到达", "停车方便", "停车场"],
    "服务/前台": ["前台", "服务好", "热情", "周到", "贴心", "礼貌", "帮助", "升级", "安排", "小刘", "服务员", "态度好"],
    "房间/设施": ["房间大", "干净", "整洁", "舒适", "床品", "床很", "设施", "齐全", "新", "装修", "江景房", "宽敞"],
    "餐饮/早餐": ["早餐", "好吃", "美食", "川菜", "正宗", "餐厅", "担担面", "抄手", "河鲜", "中餐厅"],
    "性价比": ["性价比", "值得", "划算", "价格", "不贵"],
    "亲子/家庭": ["孩子", "家人", "父母", "一家", "小孩", "亲子", "儿童"],
}

NEGATIVE_THEMES = {
    "服务态度差": ["服务差", "态度差", "态度很", "很差", "爱理不理", "蛮横", "敷衍", "不礼貌", "前台态度", "服务一般", "服务怠慢", "不想再去", "不推荐", "体验极差"],
    "卫生不达标": ["脏", "异味", "不干净", "卫生差", "头发", "毛发", "污渍", "虫子", "霉", "灰尘", "有味道"],
    "设施/隔音差": ["吵", "噪音", "隔音", "空调", "马桶", "哐当", "热水", "排水", "淋浴", "wifi", "蓝屏", "尾房", "电暖器", "维修", "坏了", "老旧", "破", "吹风机", "电视", "灯不"],
    "预订/入住问题": ["预订", "房型不", "等太久", "排队", "超售", "没有房间", "不给", "升级", "安排", "免打扰"],
    "停车/周边": ["停车", "堵车", "闹市", "酒吧", "夜店", "周边设施"],
    "早餐差": ["早餐少", "早餐差", "不新鲜", "水果不", "早餐品种少", "早餐很"],
}


def _analyze_themes(reviews: list) -> dict:
    """对点评列表进行主题分析，返回好评和差评的排行"""
    positive_counts = {k: 0 for k in POSITIVE_THEMES}
    negative_counts = {k: 0 for k in NEGATIVE_THEMES}

    for r in reviews:
        content = r.content or ""
        rating = r.rating or 3.0

        if rating >= 3.5:
            # 好评 → 匹配好评主题
            for theme, keywords in POSITIVE_THEMES.items():
                for kw in keywords:
                    if kw in content:
                        positive_counts[theme] += 1
                        break
        elif rating <= 2.5:
            # 差评 → 匹配差评主题
            for theme, keywords in NEGATIVE_THEMES.items():
                for kw in keywords:
                    if kw in content:
                        negative_counts[theme] += 1
                        break

    # 排序取 Top
    positive_top = sorted(
        [{"theme": k, "count": v} for k, v in positive_counts.items() if v > 0],
        key=lambda x: x["count"], reverse=True
    )[:5]

    negative_top = sorted(
        [{"theme": k, "count": v} for k, v in negative_counts.items() if v > 0],
        key=lambda x: x["count"], reverse=True
    )[:5]

    return {
        "positive_themes": positive_top,
        "negative_themes": negative_top,
    }


@router.get("", response_model=HotelReport)
def get_report(
    hotel_id: str,
    date_from: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = db.query(Hotel).filter(
        Hotel.id == hotel_id, Hotel.user_id == current_user.id, Hotel.is_active == True
    ).first()
    if not hotel:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="酒店不存在")

    q = db.query(Review).filter(Review.hotel_id == hotel_id)

    # 时间筛选
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            q = q.filter(Review.review_date >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q = q.filter(Review.review_date <= dt)
        except ValueError:
            pass

    reviews = q.all()

    # 如果没有筛选时间范围，默认最近30天
    if not date_from and not date_to:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        filtered_reviews = [r for r in reviews if r.review_date and r.review_date >= thirty_days_ago]
    else:
        filtered_reviews = reviews

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

    # 月度趋势
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

    # 主题分析（使用筛选后的点评）
    theme_analysis = _analyze_themes(filtered_reviews)

    # 好评率和差评率
    positive_count = sum(1 for r in filtered_reviews if r.rating and r.rating >= 3.5)
    negative_count = sum(1 for r in filtered_reviews if r.rating and r.rating <= 2.5)
    neutral_count = len(filtered_reviews) - positive_count - negative_count

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
        review_summary={
            "date_from": date_from or (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "date_to": date_to or datetime.utcnow().strftime("%Y-%m-%d"),
            "filtered_count": len(filtered_reviews),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "positive_rate": round(positive_count / len(filtered_reviews) * 100, 1) if filtered_reviews else 0,
            "negative_rate": round(negative_count / len(filtered_reviews) * 100, 1) if filtered_reviews else 0,
            "positive_themes": theme_analysis["positive_themes"],
            "negative_themes": theme_analysis["negative_themes"],
        },
    )
