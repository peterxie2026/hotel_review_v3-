import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas import OTAAccountCreate, OTAAccountUpdate, OTAAccountResponse, UserInfo
from app.api.auth import get_current_user
from app.models import Hotel, OTAAccount
from app.services.crypto_service import encrypt_password

router = APIRouter(prefix="/api/v1/hotels/{hotel_id}/accounts", tags=["OTA账号"])

# 手动登录session存储
_manual_login_sessions: dict = {}


def _get_hotel(hotel_id: str, user_id: str, db: Session) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.user_id == user_id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="酒店不存在")
    return hotel


@router.get("", response_model=List[OTAAccountResponse])
def list_accounts(hotel_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    accounts = db.query(OTAAccount).filter(OTAAccount.hotel_id == hotel_id).all()
    return [OTAAccountResponse.model_validate(a) for a in accounts]


@router.post("", response_model=OTAAccountResponse)
def create_account(hotel_id: str, data: OTAAccountCreate, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    existing = db.query(OTAAccount).filter(OTAAccount.hotel_id == hotel_id, OTAAccount.platform == data.platform).first()
    if existing:
        raise HTTPException(status_code=400, detail="该平台账号已存在")
    account = OTAAccount(
        hotel_id=hotel_id,
        platform=data.platform,
        username=data.username,
        encrypted_password=encrypt_password(data.password) if data.password else None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return OTAAccountResponse.model_validate(account)


@router.put("/{account_id}", response_model=OTAAccountResponse)
def update_account(hotel_id: str, account_id: str, data: OTAAccountUpdate,
                   current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    account = db.query(OTAAccount).filter(OTAAccount.id == account_id, OTAAccount.hotel_id == hotel_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if data.username is not None:
        account.username = data.username
    if data.password is not None:
        account.encrypted_password = encrypt_password(data.password)
    if data.is_active is not None:
        account.is_active = data.is_active
    db.commit()
    db.refresh(account)
    return OTAAccountResponse.model_validate(account)


@router.post("/{account_id}/manual-login")
async def manual_login(hotel_id: str, account_id: str,
                       current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    """打开可见浏览器窗口，让用户手动登录解决验证码"""
    _get_hotel(hotel_id, current_user.id, db)
    account = db.query(OTAAccount).filter(OTAAccount.id == account_id, OTAAccount.hotel_id == hotel_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 关闭之前的同名会话
    if account_id in _manual_login_sessions:
        old = _manual_login_sessions[account_id]
        try:
            await old["context"].close()
            await old["browser"].close()
        except Exception:
            pass

    from app.services.crypto_service import decrypt_password
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False, args=["--no-sandbox"])
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    )
    page = await context.new_page()

    login_urls = {
        "ctrip": "https://ebooking.ctrip.com/",
        "meituan": "https://e.meituan.com/",
        "fliggy": "https://hotel.fliggy.com/",
    }
    url = login_urls.get(account.platform.value if hasattr(account.platform, 'value') else str(account.platform),
                         "http://ebooking.ctrip.com/")
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)

    _manual_login_sessions[account_id] = {
        "browser": browser,
        "context": context,
        "page": page,
        "playwright": pw,
        "account_id": account_id,
        "started_at": __import__("datetime").datetime.utcnow(),
    }

    return {
        "message": f"浏览器已打开，请在浏览器窗口中手动登录{account.platform}账号。登录完成后点击'完成登录'按钮。",
        "status": "ready",
    }


@router.post("/{account_id}/complete-login")
async def complete_manual_login(hotel_id: str, account_id: str,
                                current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动登录完成后，保存cookie并关闭浏览器"""
    _get_hotel(hotel_id, current_user.id, db)
    account = db.query(OTAAccount).filter(OTAAccount.id == account_id, OTAAccount.hotel_id == hotel_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    session = _manual_login_sessions.pop(account_id, None)
    if not session:
        raise HTTPException(status_code=400, detail="没有进行中的手动登录会话")

    try:
        cookies = await session["context"].cookies()
        account.cookies_json = json.dumps(cookies)
        account.last_login_at = __import__("datetime").datetime.utcnow()
        db.commit()

        await session["context"].close()
        await session["browser"].close()
        await session["playwright"].stop()

        return {"message": "登录完成，Cookie已保存", "status": "completed", "cookie_count": len(cookies)}
    except Exception as e:
        try:
            await session["context"].close()
            await session["browser"].close()
            await session["playwright"].stop()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.delete("/{account_id}")
def delete_account(hotel_id: str, account_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    account = db.query(OTAAccount).filter(OTAAccount.id == account_id, OTAAccount.hotel_id == hotel_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    db.delete(account)
    db.commit()
    return {"message": "账号已删除"}
