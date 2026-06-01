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
    """手动登录指引：返回各平台登录地址，用户在本地浏览器登录后导入Cookie"""
    _get_hotel(hotel_id, current_user.id, db)
    account = db.query(OTAAccount).filter(OTAAccount.id == account_id, OTAAccount.hotel_id == hotel_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    platform_name = account.platform.value if hasattr(account.platform, 'value') else str(account.platform)

    login_urls = {
        "ctrip": "https://ebooking.ctrip.com/",
        "meituan": "https://e.meituan.com/",
        "fliggy": "https://hotel.fliggy.com/",
    }
    login_url = login_urls.get(platform_name, "https://ebooking.ctrip.com/")

    return {
        "platform": platform_name,
        "login_url": login_url,
        "instructions": [
            f"1. 在您当前电脑的浏览器中打开: {login_url}",
            "2. 使用账号密码登录（完成验证码等操作）",
            "3. 登录成功后按 F12 打开开发者工具",
            "4. 切换到 Application（应用程序）→ Cookies",
            f"5. 找到 {login_url} 域名下的所有Cookie",
            "6. 全选复制Cookie内容，点击下方「导入Cookie」按钮",
        ],
        "status": "instructions",
    }


@router.post("/{account_id}/import-cookies")
def import_cookies(hotel_id: str, account_id: str, data: dict,
                   current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动导入Cookie JSON（从浏览器开发者工具复制）"""
    _get_hotel(hotel_id, current_user.id, db)
    account = db.query(OTAAccount).filter(OTAAccount.id == account_id, OTAAccount.hotel_id == hotel_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    cookies_text = data.get("cookies", "")
    if not cookies_text:
        raise HTTPException(status_code=400, detail="请粘贴Cookie内容")

    # 支持多种格式：JSON数组、JSON对象、或者直接复制
    try:
        cookies_list = json.loads(cookies_text)
    except json.JSONDecodeError:
        # 尝试解析常见的Cookie导出格式
        cookies_list = []
        for line in cookies_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies_list.append({
                    "name": parts[5],
                    "value": parts[6],
                    "domain": parts[0].lstrip("."),
                    "path": parts[2],
                    "expires": float(parts[4]) if parts[4] != "0" else -1,
                })

    if not isinstance(cookies_list, list) or len(cookies_list) == 0:
        raise HTTPException(status_code=400, detail="Cookie格式错误，请复制JSON数组格式的Cookie")

    account.cookies_json = json.dumps(cookies_list)
    account.last_login_at = __import__("datetime").datetime.utcnow()
    db.commit()

    return {"message": f"Cookie导入成功，共 {len(cookies_list)} 条", "status": "completed", "cookie_count": len(cookies_list)}


@router.post("/{account_id}/complete-login")
async def complete_manual_login(hotel_id: str, account_id: str,
                                current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动登录完成后，保存cookie并关闭浏览器（已废弃，保留兼容）"""
    _get_hotel(hotel_id, current_user.id, db)
    return {"message": "请使用「导入Cookie」功能代替", "status": "deprecated", "cookie_count": 0}


@router.delete("/{account_id}")
def delete_account(hotel_id: str, account_id: str, current_user: UserInfo = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_hotel(hotel_id, current_user.id, db)
    account = db.query(OTAAccount).filter(OTAAccount.id == account_id, OTAAccount.hotel_id == hotel_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    db.delete(account)
    db.commit()
    return {"message": "账号已删除"}
