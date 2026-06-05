from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List
import uuid

from app.database import get_db
from app.api.auth import get_current_user
from app.schemas import UserInfo
from app.models import (
    SubscriptionPlan, UserSubscription, PaymentOrder,
    SubscriptionStatus, PaymentStatus,
)
from app.schemas import (
    SubscriptionPlanResponse, UserSubscriptionResponse,
    PaymentOrderResponse, SubscribeRequest,
)

router = APIRouter(prefix="/api/v1/subscription", tags=["订阅"])


def _get_free_plan(db: Session) -> SubscriptionPlan:
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == "free_trial", SubscriptionPlan.is_active == True
    ).first()
    if not plan:
        raise HTTPException(status_code=500, detail="系统未配置免费套餐")
    return plan


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
def list_plans(db: Session = Depends(get_db)):
    return db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.sort_order).all()


@router.get("/my", response_model=UserSubscriptionResponse)
def my_subscription(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id
    ).first()
    if not sub:
        # 自动创建免费试用
        plan = _get_free_plan(db)
        sub = UserSubscription(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            plan_id=plan.id,
            status=SubscriptionStatus.trialing,
            trial_end_at=datetime.utcnow() + timedelta(days=14),
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=14),
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

    # 自动检查试用是否到期
    if sub.status == SubscriptionStatus.trialing and sub.trial_end_at:
        if datetime.utcnow() > sub.trial_end_at:
            sub.status = SubscriptionStatus.expired
            db.commit()

    return UserSubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        plan=SubscriptionPlanResponse.model_validate(sub.plan),
        status=sub.status.value if hasattr(sub.status, 'value') else sub.status,
        trial_end_at=sub.trial_end_at,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        auto_renew=sub.auto_renew,
        created_at=sub.created_at,
    )


@router.post("/subscribe", response_model=PaymentOrderResponse)
def subscribe(
    data: SubscribeRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """订阅或升级套餐 - 创建支付订单"""
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == data.plan_id, SubscriptionPlan.is_active == True
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")

    if plan.code == "free_trial":
        # 免费套餐直接激活
        sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id
        ).first()
        if sub:
            sub.plan_id = plan.id
            sub.status = SubscriptionStatus.trialing
            sub.trial_end_at = datetime.utcnow() + timedelta(days=14)
            sub.current_period_start = datetime.utcnow()
            sub.current_period_end = datetime.utcnow() + timedelta(days=14)
        else:
            sub = UserSubscription(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                plan_id=plan.id,
                status=SubscriptionStatus.trialing,
                trial_end_at=datetime.utcnow() + timedelta(days=14),
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=14),
            )
            db.add(sub)
        db.commit()
        # 返回一个虚拟的免费订单
        return PaymentOrderResponse(
            id="free_" + sub.id,
            user_id=current_user.id,
            plan=SubscriptionPlanResponse.model_validate(plan),
            amount=0,
            payment_method="manual",
            status="paid",
            paid_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

    # 付费套餐 - 创建支付订单
    amount = plan.price_yearly if data.billing_period == "yearly" else plan.price_monthly
    order = PaymentOrder(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        plan_id=plan.id,
        amount=amount,
        payment_method="manual",
        status=PaymentStatus.pending,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return PaymentOrderResponse(
        id=order.id,
        user_id=order.user_id,
        plan=SubscriptionPlanResponse.model_validate(plan),
        amount=order.amount,
        payment_method=order.payment_method,
        status=order.status.value if hasattr(order.status, 'value') else order.status,
        transaction_id=order.transaction_id,
        admin_note=order.admin_note,
        paid_at=order.paid_at,
        created_at=order.created_at,
    )


@router.post("/cancel")
def cancel_subscription(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="未找到订阅记录")
    sub.auto_renew = False
    db.commit()
    return {"message": "已取消自动续费"}


@router.get("/orders", response_model=List[PaymentOrderResponse])
def list_orders(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = db.query(PaymentOrder).filter(
        PaymentOrder.user_id == current_user.id
    ).order_by(PaymentOrder.created_at.desc()).all()

    result = []
    for o in orders:
        result.append(PaymentOrderResponse(
            id=o.id,
            user_id=o.user_id,
            plan=SubscriptionPlanResponse.model_validate(o.plan),
            amount=o.amount,
            payment_method=o.payment_method,
            status=o.status.value if hasattr(o.status, 'value') else o.status,
            transaction_id=o.transaction_id,
            admin_note=o.admin_note,
            paid_at=o.paid_at,
            created_at=o.created_at,
        ))
    return result


@router.get("/orders/{order_id}", response_model=PaymentOrderResponse)
def get_order(
    order_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(PaymentOrder).filter(
        PaymentOrder.id == order_id,
        PaymentOrder.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return PaymentOrderResponse(
        id=order.id,
        user_id=order.user_id,
        plan=SubscriptionPlanResponse.model_validate(order.plan),
        amount=order.amount,
        payment_method=order.payment_method,
        status=order.status.value if hasattr(order.status, 'value') else order.status,
        transaction_id=order.transaction_id,
        admin_note=order.admin_note,
        paid_at=order.paid_at,
        created_at=order.created_at,
    )


@router.post("/orders/{order_id}/check")
def check_order_payment(
    order_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """检查订单支付状态，如果已支付则激活订阅"""
    order = db.query(PaymentOrder).filter(
        PaymentOrder.id == order_id,
        PaymentOrder.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == PaymentStatus.paid:
        # 激活订阅
        sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id
        ).first()
        period_days = 365 if order.amount == order.plan.price_yearly else 30
        now = datetime.utcnow()
        if sub:
            sub.plan_id = order.plan_id
            sub.status = SubscriptionStatus.active
            sub.current_period_start = now
            sub.current_period_end = now + timedelta(days=period_days)
            sub.auto_renew = True
        else:
            sub = UserSubscription(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                plan_id=order.plan_id,
                status=SubscriptionStatus.active,
                current_period_start=now,
                current_period_end=now + timedelta(days=period_days),
                auto_renew=True,
            )
            db.add(sub)
        db.commit()
        return {"status": "paid", "message": "支付成功，订阅已激活"}

    return {"status": order.status.value if hasattr(order.status, 'value') else order.status}
