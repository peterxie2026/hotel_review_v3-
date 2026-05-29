from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum


def gen_uuid():
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class ReplyCategory(str, enum.Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class ReviewStatus(str, enum.Enum):
    pending_reply = "pending_reply"
    replied = "replied"
    ignored = "ignored"


class ReplyStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    submitted = "submitted"
    failed = "failed"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class OTAPlatform(str, enum.Enum):
    ctrip = "ctrip"
    meituan = "meituan"
    fliggy = "fliggy"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    role = Column(SAEnum(UserRole), default=UserRole.user)
    subscription_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hotels = relationship("Hotel", back_populates="owner", cascade="all, delete-orphan")


class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(32), nullable=True)
    star_rating = Column(Integer, nullable=True)
    room_count = Column(Integer, nullable=True)
    highlights = Column(JSON, default=list)
    reply_tone = Column(String(64), default="亲切温暖专业")
    schedule_config = Column(JSON, default=dict)  # {"auto_scrape":{"enabled":false,"times":["09:00","18:00"]},"auto_reply":{"enabled":false,"time":"10:00"}}
    ai_provider = Column(String(32), default="deepseek")  # deepseek/qwen/minimax/zhipu
    ai_model = Column(String(64), default="")  # 空则用provider默认模型
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="hotels")
    ota_accounts = relationship("OTAAccount", back_populates="hotel", cascade="all, delete-orphan")
    knowledge_entries = relationship("KnowledgeEntry", back_populates="hotel", cascade="all, delete-orphan")
    reply_templates = relationship("ReplyTemplate", back_populates="hotel", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="hotel", cascade="all, delete-orphan")


class OTAAccount(Base):
    __tablename__ = "ota_accounts"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id"), nullable=False)
    platform = Column(SAEnum(OTAPlatform), nullable=False)
    username = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=True)
    cookies_json = Column(Text, nullable=True)
    cookies_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    last_scrape_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hotel = relationship("Hotel", back_populates="ota_accounts")


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id"), nullable=False)
    category = Column(String(64), nullable=False)  # hotel_info, service_feature, nearby, policy
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hotel = relationship("Hotel", back_populates="knowledge_entries")


class ReplyTemplate(Base):
    __tablename__ = "reply_templates"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id"), nullable=False)
    name = Column(String(128), nullable=False)
    category = Column(SAEnum(ReplyCategory), nullable=False)
    text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hotel = relationship("Hotel", back_populates="reply_templates")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id"), nullable=False)
    platform = Column(SAEnum(OTAPlatform), nullable=False)
    platform_review_id = Column(String(128), nullable=True)
    guest_name = Column(String(128), nullable=True)
    room_type = Column(String(128), nullable=True)
    rating = Column(Float, nullable=True)
    content = Column(Text, nullable=True)
    check_in_date = Column(DateTime, nullable=True)
    review_date = Column(DateTime, nullable=True)
    ai_analysis = Column(JSON, nullable=True)
    status = Column(SAEnum(ReviewStatus), default=ReviewStatus.pending_reply)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hotel = relationship("Hotel", back_populates="reviews")
    replies = relationship("Reply", back_populates="review", cascade="all, delete-orphan", order_by="Reply.created_at.desc()")


class Reply(Base):
    __tablename__ = "replies"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    review_id = Column(String(36), ForeignKey("reviews.id"), nullable=False)
    ai_model = Column(String(64), nullable=True)
    ai_text = Column(Text, nullable=True)
    edited_text = Column(Text, nullable=True)
    final_text = Column(Text, nullable=True)
    status = Column(SAEnum(ReplyStatus), default=ReplyStatus.draft)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    review = relationship("Review", back_populates="replies")


class ScrapeTask(Base):
    __tablename__ = "scrape_tasks"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id"), nullable=False)
    platform = Column(SAEnum(OTAPlatform), nullable=False)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.pending)
    reviews_found = Column(Integer, default=0)
    reviews_new = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    progress_message = Column(String(255), nullable=True)  # 实时进度描述
    celery_task_id = Column(String(128), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SubmitTask(Base):
    __tablename__ = "submit_tasks"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id"), nullable=False)
    platform = Column(SAEnum(OTAPlatform), nullable=False)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.pending)
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    results_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    progress_message = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
