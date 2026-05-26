from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from playwright.async_api import Page


@dataclass
class RawReview:
    platform_review_id: str
    guest_name: str = ""
    room_type: str = ""
    rating: float = 0.0
    content: str = ""
    check_in_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    has_reply: bool = False  # OTA后台是否已有酒店回复


class OTAAdapter(ABC):
    platform: str = ""

    @abstractmethod
    async def login(self, page: Page, username: str, password: str) -> bool:
        """登录到OTA后台，返回是否成功"""

    @abstractmethod
    async def check_login_status(self, page: Page) -> bool:
        """检查当前session是否有效"""

    @abstractmethod
    async def fetch_pending_reviews(self, page: Page) -> List[RawReview]:
        """获取待回复点评列表"""

    @abstractmethod
    async def submit_reply(self, page: Page, review_id: str, reply_text: str) -> bool:
        """提交回复到OTA"""
