from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas import HotelCreate, HotelUpdate, HotelResponse, ScheduleConfig, UserInfo
from app.api.auth import get_current_user
from app.models import Hotel

router = APIRouter(prefix="/api/v1/hotels", tags=["酒店管理"])


@router.get("", response_model=List[HotelResponse])
def list_hotels(current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotels = db.query(Hotel).filter(Hotel.user_id == current_user.id, Hotel.is_active == True).all()
    result = []
    for h in hotels:
        pending = sum(1 for r in h.reviews if r.status.value == "pending_reply")
        result.append(HotelResponse(
            id=h.id, name=h.name, brand=h.brand, address=h.address,
            phone=h.phone, star_rating=h.star_rating, room_count=h.room_count,
            highlights=h.highlights or [], reply_tone=h.reply_tone,
            ai_provider=h.ai_provider or "deepseek", ai_model=h.ai_model or "",
            is_active=h.is_active, schedule_config=h.schedule_config or {},
            ota_count=len(h.ota_accounts), pending_review_count=pending,
            created_at=h.created_at,
        ))
    return result


@router.post("", response_model=HotelResponse)
def create_hotel(data: HotelCreate, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = Hotel(user_id=current_user.id, **data.model_dump())
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return HotelResponse(
        id=hotel.id, name=hotel.name, brand=hotel.brand, address=hotel.address,
        phone=hotel.phone, star_rating=hotel.star_rating, room_count=hotel.room_count,
        highlights=hotel.highlights or [], reply_tone=hotel.reply_tone,
        ai_provider=hotel.ai_provider or "deepseek", ai_model=hotel.ai_model or "",
        is_active=hotel.is_active, schedule_config=hotel.schedule_config or {},
        ota_count=0, pending_review_count=0, created_at=hotel.created_at,
    )


@router.get("/{hotel_id}", response_model=HotelResponse)
def get_hotel(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == current_user.id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    pending = sum(1 for r in hotel.reviews if r.status.value == "pending_reply")
    return HotelResponse(
        id=hotel.id, name=hotel.name, brand=hotel.brand, address=hotel.address,
        phone=hotel.phone, star_rating=hotel.star_rating, room_count=hotel.room_count,
        highlights=hotel.highlights or [], reply_tone=hotel.reply_tone,
        ai_provider=hotel.ai_provider or "deepseek", ai_model=hotel.ai_model or "",
        is_active=hotel.is_active, schedule_config=hotel.schedule_config or {},
        ota_count=len(hotel.ota_accounts), pending_review_count=pending,
        created_at=hotel.created_at,
    )


@router.put("/{hotel_id}", response_model=HotelResponse)
def update_hotel(hotel_id: str, data: HotelUpdate, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == current_user.id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(hotel, k, v)
    db.commit()
    db.refresh(hotel)
    pending = sum(1 for r in hotel.reviews if r.status.value == "pending_reply")
    return HotelResponse(
        id=hotel.id, name=hotel.name, brand=hotel.brand, address=hotel.address,
        phone=hotel.phone, star_rating=hotel.star_rating, room_count=hotel.room_count,
        highlights=hotel.highlights or [], reply_tone=hotel.reply_tone,
        ai_provider=hotel.ai_provider or "deepseek", ai_model=hotel.ai_model or "",
        is_active=hotel.is_active, schedule_config=hotel.schedule_config or {},
        ota_count=len(hotel.ota_accounts), pending_review_count=pending,
        created_at=hotel.created_at,
    )


@router.put("/{hotel_id}/schedule", response_model=HotelResponse)
def update_schedule(hotel_id: str, data: ScheduleConfig, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == current_user.id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    hotel.schedule_config = data.model_dump()
    db.commit()
    db.refresh(hotel)
    pending = sum(1 for r in hotel.reviews if r.status.value == "pending_reply")
    return HotelResponse(
        id=hotel.id, name=hotel.name, brand=hotel.brand, address=hotel.address,
        phone=hotel.phone, star_rating=hotel.star_rating, room_count=hotel.room_count,
        highlights=hotel.highlights or [], reply_tone=hotel.reply_tone,
        ai_provider=hotel.ai_provider or "deepseek", ai_model=hotel.ai_model or "",
        is_active=hotel.is_active, schedule_config=hotel.schedule_config or {},
        ota_count=len(hotel.ota_accounts), pending_review_count=pending,
        created_at=hotel.created_at,
    )


@router.delete("/{hotel_id}")
def delete_hotel(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == current_user.id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    hotel.is_active = False
    db.commit()
    return {"message": "酒店已删除"}
