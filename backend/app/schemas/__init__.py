from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ===== Auth =====
class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    company_name: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class UserInfo(BaseModel):
    id: str
    username: str
    email: Optional[str]
    company_name: Optional[str]
    subscription_expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Hotel =====
class HotelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    brand: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    star_rating: Optional[int] = None
    room_count: Optional[int] = None
    highlights: List[str] = []
    reply_tone: str = "亲切温暖专业"
    ai_provider: str = "deepseek"
    ai_model: str = ""


class HotelUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    star_rating: Optional[int] = None
    room_count: Optional[int] = None
    highlights: Optional[List[str]] = None
    reply_tone: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None


class ScheduleConfig(BaseModel):
    auto_scrape: dict = {"enabled": False, "times": ["09:00", "18:00"]}
    auto_reply: dict = {"enabled": False, "times": ["10:00"]}


class HotelResponse(BaseModel):
    id: str
    name: str
    brand: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    star_rating: Optional[int]
    room_count: Optional[int]
    highlights: List[str]
    reply_tone: str
    ai_provider: str = "deepseek"
    ai_model: str = ""
    is_active: bool
    schedule_config: Optional[dict] = None
    ota_count: int = 0
    pending_review_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# ===== OTA Account =====
class OTAAccountCreate(BaseModel):
    platform: str = Field(..., pattern="^(ctrip|meituan|fliggy)$")
    username: str
    password: str


class OTAAccountUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class OTAAccountResponse(BaseModel):
    id: str
    hotel_id: str
    platform: str
    username: str
    is_active: bool
    last_login_at: Optional[datetime]
    last_scrape_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Knowledge Entry =====
class KnowledgeEntryCreate(BaseModel):
    category: str
    key: str
    value: str
    priority: int = 0


class KnowledgeEntryUpdate(BaseModel):
    category: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    priority: Optional[int] = None


class KnowledgeEntryResponse(BaseModel):
    id: str
    hotel_id: str
    category: str
    key: str
    value: str
    priority: int

    class Config:
        from_attributes = True


# ===== Reply Template =====
class ReplyTemplateCreate(BaseModel):
    name: str
    category: str = Field(..., pattern="^(positive|negative|neutral)$")
    text: str


class ReplyTemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    text: Optional[str] = None
    is_active: Optional[bool] = None


class ReplyTemplateResponse(BaseModel):
    id: str
    hotel_id: str
    name: str
    category: str
    text: str
    is_active: bool
    usage_count: int

    class Config:
        from_attributes = True


# ===== Review =====
class ReviewResponse(BaseModel):
    id: str
    hotel_id: str
    platform: str
    platform_review_id: Optional[str]
    guest_name: Optional[str]
    room_type: Optional[str]
    rating: Optional[float]
    content: Optional[str]
    check_in_date: Optional[datetime]
    review_date: Optional[datetime]
    ai_analysis: Optional[dict]
    status: str
    reply_count: int = 0
    latest_reply: Optional["ReplyResponse"] = None
    is_demo: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pending_total: int = 0  # 全量待回复数
    approved_total: int = 0  # 全量已审核待提交数
    items: List[ReviewResponse]


# ===== Reply =====
class ReplyResponse(BaseModel):
    id: str
    review_id: str
    ai_model: Optional[str]
    ai_text: Optional[str]
    edited_text: Optional[str]
    final_text: Optional[str]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ReplyUpdateRequest(BaseModel):
    edited_text: str


# ===== Scrape Task =====
class ScrapeTaskResponse(BaseModel):
    id: str
    hotel_id: str
    platform: str
    status: str
    reviews_found: int
    reviews_new: int
    error_message: Optional[str]
    progress_message: Optional[str] = None
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Report =====
class HotelReport(BaseModel):
    hotel_name: str
    total_reviews: int
    pending_reviews: int
    replied_reviews: int
    reply_rate: float
    avg_rating: float
    rating_distribution: dict  # {"5": count, "4": count, ...}
    platform_distribution: dict  # {"ctrip": count, ...}
    monthly_trends: list  # [{month: "2026-05", count: 10, replied: 8}, ...]
    recent_reviews: list  # 最近5条点评摘要
    review_summary: Optional[dict] = None  # 点评汇总：好评/差评主题排行


# ===== Dashboard =====
class DashboardSummary(BaseModel):
    total_hotels: int
    total_reviews: int
    pending_reviews: int
    replied_today: int
    reply_rate: float  # 0-100


# ===== SubmitTask =====
class SubmitTaskResponse(BaseModel):
    id: str
    hotel_id: str
    platform: str
    status: str
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    results_json: Optional[str] = None
    error_message: Optional[str] = None
    progress_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
