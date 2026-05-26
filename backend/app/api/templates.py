from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas import ReplyTemplateCreate, ReplyTemplateUpdate, ReplyTemplateResponse, UserInfo
from app.api.auth import get_current_user
from app.models import Hotel, ReplyTemplate

router = APIRouter(prefix="/api/v1/hotels/{hotel_id}/templates", tags=["回复模板"])


def _get_hotel(hotel_id: str, user_id: str, db: Session) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == user_id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    return hotel


@router.get("", response_model=List[ReplyTemplateResponse])
def list_templates(hotel_id: str, category: str = None,
                   current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    q = db.query(ReplyTemplate).filter(ReplyTemplate.hotel_id == hotel_id, ReplyTemplate.is_active == True)
    if category:
        q = q.filter(ReplyTemplate.category == category)
    return [ReplyTemplateResponse.model_validate(t) for t in q.all()]


@router.post("", response_model=ReplyTemplateResponse)
def create_template(hotel_id: str, data: ReplyTemplateCreate,
                    current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    tpl = ReplyTemplate(hotel_id=hotel_id, **data.model_dump())
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return ReplyTemplateResponse.model_validate(tpl)


@router.put("/{tpl_id}", response_model=ReplyTemplateResponse)
def update_template(hotel_id: str, tpl_id: str, data: ReplyTemplateUpdate,
                    current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    tpl = db.query(ReplyTemplate).filter(ReplyTemplate.id == tpl_id, ReplyTemplate.hotel_id == hotel_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(tpl, k, v)
    db.commit()
    db.refresh(tpl)
    return ReplyTemplateResponse.model_validate(tpl)


@router.delete("/{tpl_id}")
def delete_template(hotel_id: str, tpl_id: str,
                    current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    tpl = db.query(ReplyTemplate).filter(ReplyTemplate.id == tpl_id, ReplyTemplate.hotel_id == hotel_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    tpl.is_active = False
    db.commit()
    return {"message": "已删除"}
