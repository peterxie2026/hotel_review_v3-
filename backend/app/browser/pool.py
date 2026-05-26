import asyncio
from typing import Dict
from playwright.async_api import async_playwright, Browser, BrowserContext
from app.config import settings


class BrowserPool:
    """Playwright浏览器池，每个OTA账号维持独立的持久化context"""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

    async def get_context(self, account_id: str, cookies_json: str = None) -> BrowserContext:
        """获取或创建持久化context，自动同步最新cookie"""
        async with self._lock:
            # 如果已有context但cookie更新了，关闭旧的重建
            if account_id in self._contexts and cookies_json:
                try:
                    import json
                    new_cookies = json.loads(cookies_json) if isinstance(cookies_json, str) else cookies_json
                    old_cookies = await self._contexts[account_id].cookies()
                    # 简单对比：cookie数量变化则重建
                    if len(new_cookies) != len(old_cookies):
                        await self._contexts[account_id].close()
                        del self._contexts[account_id]
                except Exception:
                    pass

            if account_id not in self._contexts:
                context = await self._browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                )
                if cookies_json:
                    try:
                        import json
                        cookies = json.loads(cookies_json) if isinstance(cookies_json, str) else cookies_json
                        await context.add_cookies(cookies)
                    except Exception:
                        pass
                self._contexts[account_id] = context
            return self._contexts[account_id]

    async def save_cookies(self, account_id: str) -> str:
        """保存cookie到JSON字符串"""
        if account_id in self._contexts:
            cookies = await self._contexts[account_id].cookies()
            import json
            return json.dumps(cookies)
        return ""

    async def close_context(self, account_id: str):
        if account_id in self._contexts:
            await self._contexts[account_id].close()
            del self._contexts[account_id]

    async def stop(self):
        for ctx in list(self._contexts.values()):
            await ctx.close()
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


_browser_pool: BrowserPool | None = None


async def get_browser_pool() -> BrowserPool:
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool()
        await _browser_pool.start()
    return _browser_pool
