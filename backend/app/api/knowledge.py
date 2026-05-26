from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas import KnowledgeEntryCreate, KnowledgeEntryUpdate, KnowledgeEntryResponse, UserInfo
from app.api.auth import get_current_user
from app.models import Hotel, KnowledgeEntry

router = APIRouter(prefix="/api/v1/hotels/{hotel_id}/knowledge", tags=["知识库"])


def _get_hotel(hotel_id: str, user_id: str, db: Session) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == user_id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    return hotel


@router.get("", response_model=List[KnowledgeEntryResponse])
def list_entries(hotel_id: str, category: str = None,
                 current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    q = db.query(KnowledgeEntry).filter(KnowledgeEntry.hotel_id == hotel_id)
    if category:
        q = q.filter(KnowledgeEntry.category == category)
    return [KnowledgeEntryResponse.model_validate(e) for e in q.order_by(KnowledgeEntry.priority.desc()).all()]


@router.post("", response_model=KnowledgeEntryResponse)
def create_entry(hotel_id: str, data: KnowledgeEntryCreate,
                 current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    entry = KnowledgeEntry(hotel_id=hotel_id, **data.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return KnowledgeEntryResponse.model_validate(entry)


@router.put("/{entry_id}", response_model=KnowledgeEntryResponse)
def update_entry(hotel_id: str, entry_id: str, data: KnowledgeEntryUpdate,
                 current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id, KnowledgeEntry.hotel_id == hotel_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return KnowledgeEntryResponse.model_validate(entry)


@router.delete("/{entry_id}")
def delete_entry(hotel_id: str, entry_id: str,
                 current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id, KnowledgeEntry.hotel_id == hotel_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    db.delete(entry)
    db.commit()
    return {"message": "已删除"}
