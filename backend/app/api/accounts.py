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

    platform_name = account.platform.value if hasattr(account.platform, 'value') else str(account.platform)
    default_domains = {
        "ctrip": ".ctrip.com",
        "meituan": ".meituan.com",
        "fliggy": ".fliggy.com",
    }
    default_domain = default_domains.get(platform_name, ".ctrip.com")

    cookies_list = []

    # 尝试1: 解析JSON
    try:
        parsed = json.loads(cookies_text)
        if isinstance(parsed, list):
            cookies_list = parsed
        elif isinstance(parsed, dict):
            cookies_list = [parsed]
    except json.JSONDecodeError:
        pass

    # 尝试2: 解析表格式复制（Chrome/Safari DevTools表格复制）
    if not cookies_list:
        for line in cookies_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies_list.append({
                    "name": parts[5].strip(),
                    "value": parts[6].strip(),
                    "domain": parts[0].strip().lstrip("."),
                    "path": parts[2].strip(),
                    "expires": float(parts[4]) if parts[4] != "0" else -1,
                })

    # 尝试3: 解析 name=value 格式（每行一个）
    if not cookies_list:
        for line in cookies_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if "=" in line and not line.startswith("{"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    cookies_list.append({"name": parts[0].strip(), "value": parts[1].strip()})

    if not cookies_list:
        raise HTTPException(status_code=400, detail=(
            "无法解析Cookie数据。请使用推荐方式：在浏览器控制台执行 "
            "copy(JSON.stringify(document.cookie.split('; ').reduce((a,c)=>{"
            "const[p,...v]=c.split('=');a.push({name:p,value:v.join('=')});return a},[])))"
        ))

    # 补全缺失的字段
    for c in cookies_list:
        if "name" not in c or not c["name"]:
            raise HTTPException(status_code=400, detail="Cookie缺少name字段，请检查数据格式")
        if "value" not in c:
            c["value"] = ""
        if "domain" not in c or not c.get("domain"):
            c["domain"] = default_domain
        if "path" not in c or not c.get("path"):
            c["path"] = "/"
        # Playwright要求 httpOnly 和 secure 字段
        if "httpOnly" not in c:
            c["httpOnly"] = False
        if "secure" not in c:
            c["secure"] = False
        if "sameSite" not in c:
            c["sameSite"] = "Lax"

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
