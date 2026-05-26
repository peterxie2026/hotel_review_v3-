import asyncio
import re
from datetime import datetime
from typing import List
from playwright.async_api import Page
from app.ota.base import OTAAdapter, RawReview


class CtripAdapter(OTAAdapter):
    platform = "ctrip"

    async def login(self, page: Page, username: str, password: str) -> bool:
        """登录携程ebooking后台 - 优先使用cookie，失败时尝试自动登录"""
        # 直接尝试访问点评列表页，利用已有cookie
        if await self.check_login_status(page):
            return True

        # Cookie失效，尝试自动填表登录
        try:
            await page.goto("https://ebooking.ctrip.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 检查是否已经登录（可能是cookie部分有效）
            if await self._quick_login_check(page):
                return True

            # 找用户名输入框
            for user_sel in ["input[name='username']", "input[name='userName']", "input[name='account']",
                             "input#userName", "input#username", "input[type='text']"]:
                try:
                    await page.fill(user_sel, username, timeout=3000)
                    break
                except Exception:
                    continue

            for pwd_sel in ["input[name='password']", "input[name='passWord']", "input#password",
                            "input[type='password']"]:
                try:
                    await page.fill(pwd_sel, password, timeout=3000)
                    break
                except Exception:
                    continue

            # 点击登录按钮
            for btn_sel in ["button#btnLogin", "button:has-text('登录')", "input[value='登录']",
                            "button:has-text('登 录')", ".login-btn", "a:has-text('登录')"]:
                try:
                    await page.click(btn_sel, timeout=3000)
                    await asyncio.sleep(5)
                    break
                except Exception:
                    continue

            return await self.check_login_status(page)
        except Exception:
            return False

    async def _quick_login_check(self, page: Page) -> bool:
        """快速检查登录状态，不额外导航"""
        try:
            url = page.url.lower()
            title = await page.title()
            if "login" in url or "登录" in title:
                return False
            if "ebooking" in url:
                return True
            # 检查页面是否包含酒店名称（登录成功）
            page_text = await page.inner_text("body")
            if "酒店" in page_text and "首页" in page_text:
                return True
            return False
        except Exception:
            return False

    async def check_login_status(self, page: Page) -> bool:
        """检查是否已登录 - 访问点评列表页看是否被重定向到登录页"""
        try:
            # 直接访问需登录的点评列表页
            await page.goto("https://ebooking.ctrip.com/comment/commentList", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            url = page.url.lower()
            title = await page.title()
            # 被重定向到登录页
            if "login" in url or "登录" in title:
                return False
            # 成功访问ebooking页面
            if "ebooking" in url or "ebooking" in title.lower() or "comment" in url:
                return True
            # 进一步检查页面内容
            try:
                body = await page.inner_text("body")
                if "酒店" in body and ("点评" in body or "评论" in body or "首页" in body):
                    return True
            except Exception:
                pass
            return "login" not in url
        except Exception:
            return False

    async def fetch_pending_reviews(self, page: Page) -> List[RawReview]:
        """获取待回复点评（无待回复时自动抓差评）"""
        # 导航到点评列表
        current_url = page.url.lower()
        if "comment" not in current_url or "ebooking" not in current_url:
            for review_url in ["http://ebooking.ctrip.com/comment/commentList",
                              "https://ebooking.ctrip.com/comment/commentList"]:
                try:
                    await page.goto(review_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    break
                except Exception:
                    continue

        # 等待页面渲染完成，然后滚动加载更多点评
        await asyncio.sleep(2)

        # 滚动页面触发懒加载，获取更多点评
        try:
            for scroll_step in range(5):
                await page.evaluate(f"window.scrollTo(0, {scroll_step * 1500})")
                await asyncio.sleep(0.8)
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
        except Exception:
            pass

        # 保存页面HTML和截图用于调试
        try:
            import os
            os.makedirs("/tmp/ctrip_debug", exist_ok=True)
            html = await page.content()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            with open(f"/tmp/ctrip_debug/page_html_{ts}.html", "w") as f:
                f.write(html[:80000])
        except Exception:
            pass

        reviews = []

        # 按优先级尝试不同标签页
        tabs_to_try = [
            ("待回复", ["text=待回复", "a:has-text('待回复')", "span:has-text('待回复')", "div:has-text('待回复')"]),
            ("差评", ["text=差评", "a:has-text('差评')", "span:has-text('差评')", "div:has-text('差评')"]),
            ("全部点评", ["text=全部点评", "a:has-text('全部点评')", "span:has-text('全部点评')"]),
        ]

        for tab_name, tab_selectors in tabs_to_try:
            # 点击对应标签
            if tab_name != "全部点评":
                clicked = False
                for tab_sel in tab_selectors:
                    try:
                        element = await page.query_selector(tab_sel)
                        if element:
                            await element.click()
                            await asyncio.sleep(2)
                            clicked = True
                            break
                    except Exception:
                        continue

            # 方法1: inner_text全页面解析（保留换行，解析可靠）
            reviews = await self._fullpage_extract(page)
            if reviews:
                break

            # 方法2: JS DOM提取兜底
            reviews = await self._js_extract_reviews(page)
            if reviews:
                break

        return reviews

    async def _js_extract_reviews(self, page: Page) -> List[RawReview]:
        """通过JS从DOM中提取点评数据 - 寻找最小的包含单条点评的容器"""
        try:
            result = await page.evaluate("""
                (() => {
                    const reviews = [];
                    const allEls = document.querySelectorAll('div, li, section, tr');
                    const seen = new Set();

                    for (const el of allEls) {
                        const text = (el.textContent || '').trim();
                        // Each individual review must have exactly one "发表于:" and sub-ratings
                        const pubCount = (text.match(/发表于:/g) || []).length;
                        if (pubCount !== 1) continue;
                        if (!text.includes('设施') && !text.includes('卫生')) continue;
                        if (text.length < 80 || text.length > 3000) continue;

                        const key = text.substring(0, 80);
                        if (seen.has(key)) continue;
                        seen.add(key);

                        reviews.push({ fullText: text });
                        if (reviews.length >= 30) break;
                    }
                    return reviews;
                })()
            """)

            reviews = []
            for item in result:
                full_text = item.get('fullText', '')
                if full_text:
                    r = self._parse_review_text(full_text)
                    if r and r.content and len(r.content) >= 5:
                        if not any(existing.platform_review_id == r.platform_review_id for existing in reviews):
                            reviews.append(r)
            return reviews
        except Exception:
            return []

    def _parse_review_text(self, text: str) -> RawReview | None:
        """从单条点评的文本块中解析信息 - text必须只包含一条点评"""
        lines = text.split('\n')
        if len(lines) < 3:
            return None

        # 找到"发表于:"行 - 必须是倒数几行内，因为发表于后面只有回复内容
        pub_line_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if re.search(r'发表于:\s*\d{4}年', lines[i]):
                pub_line_idx = i
                break

        if pub_line_idx < 0:
            return None

        # 确保发表于后面没有另一条点评的元数据（说明这不是合理的块）
        after_lines = lines[pub_line_idx + 1:]
        after_text = '\n'.join(after_lines)
        if re.search(r'^(?:设施|卫生|环境|服务)\s+[\d.]+$', after_text, re.MULTILINE):
            return None  # 发表于后面的内容包含另一条点评的评分数据

        # 提取发表日期
        m = re.search(r'发表于:\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2}):(\d{2})', lines[pub_line_idx])
        if m:
            try:
                review_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                      int(m.group(4)), int(m.group(5)), int(m.group(6)))
            except Exception:
                review_date = datetime.now()
        else:
            review_date = datetime.now()

        # 从"发表于:"开始，向上按段落区块扫描
        # 区块结构（从下到上）：
        #   发表于: [time]
        #   [空行]
        #   [点评正文 - 可能多行连续无空行]
        #   [空行]
        #   [子评分: 服务 X, 卫生 X, 环境 X, 设施 X]
        #   [总评分: 数字]
        #   [可选: 反馈异常点评]
        #   [空行]
        #   [房型]
        #   [空行]
        #   [入住年月]
        #   [空行]
        #   [客人名]

        j = pub_line_idx - 1

        # 跳过发表于前面的空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 收集点评正文（非空的连续行）
        content_lines = []
        while j >= 0 and lines[j].strip():
            content_lines.insert(0, lines[j].strip())
            j -= 1
        content = '\n'.join(content_lines).strip()

        # 跳过正文前面的空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 接下来应该是评分块：服务/卫生/环境/设施 + 总评分
        rating = 3.0
        found_rating_block = False
        for _ in range(10):
            if j < 0:
                break
            line = lines[j].strip()
            if not line:
                break
            if re.match(r'^(设施|卫生|环境|服务)\s+([\d.]+)$', line):
                found_rating_block = True
                j -= 1
                continue
            m = re.match(r'^([\d.]+)$', line)
            if m and float(m.group(1)) <= 5:
                rating = float(m.group(1))
                found_rating_block = True
                j -= 1
                continue
            if line == '反馈异常点评' or 'AI点评保护' in line or '此点评不计入' in line:
                j -= 1
                continue
            # 非评分行，说明评分块结束
            break

        # 跳过评分块前空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 房型
        room_type = ""
        if j >= 0:
            line = lines[j].strip()
            if ('房' in line or '套' in line) and len(line) <= 30 and not re.search(r'(\d|分|点评|回复)', line):
                room_type = line
                j -= 1

        # 跳过空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 入住年月
        travel_date = None
        if j >= 0:
            line = lines[j].strip()
            m = re.match(r'^(\d{4})年(\d{1,2})月$', line)
            if m:
                try:
                    travel_date = datetime(int(m.group(1)), int(m.group(2)), 1)
                except Exception:
                    pass
                j -= 1

        # 跳过空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 客人名
        guest_name = ""
        if j >= 0:
            line = lines[j].strip()
            if re.match(r'^[\w*_]+$', line) and len(line) >= 5:
                guest_name = line
            elif re.search(r'[一-鿿]', line) and len(line) <= 20:
                if not any(k in line for k in ['点评', '回复', '酒店', '携程', '筛选', '下载', '发表于', '反馈', '不计入']):
                    guest_name = line
            elif re.match(r'^[\w*_-]+$', line):  # 其他用户名格式
                guest_name = line

        # 验证内容有效性
        if not content or len(content) < 3:
            return None
        # 排除明显的误识别（酒店回复被当成点评）
        if content.startswith('尊敬的') or '回复员工' in content:
            return None
        if len(content) > 2000:  # 太长的内容可能是多个块合并了
            return None

        # 检测携程后台是否已有酒店回复
        has_hotel_reply = False
        after_pub = text[text.find(lines[pub_line_idx]):] if pub_line_idx >= 0 else ''
        if '酒店回复内容' in after_pub:
            has_hotel_reply = True

        # 用guest_name+日期+内容生成稳定ID，避免重复抓取
        raw_id = str(hash(f"{guest_name}_{review_date.strftime('%Y%m%d')}_{content[:50]}"))

        return RawReview(
            platform_review_id=raw_id,
            guest_name=guest_name or "携程旅客",
            room_type=room_type,
            rating=rating,
            content=content,
            check_in_date=travel_date,
            review_date=review_date,
            has_reply=has_hotel_reply,
        )

    async def _fullpage_extract(self, page: Page) -> List[RawReview]:
        """全页面文本分析 - 通过发表于位置精确定位每条点评"""
        try:
            body_text = await page.inner_text("body")
        except Exception:
            return []

        # 保存调试文本
        try:
            import os
            os.makedirs("/tmp/ctrip_debug", exist_ok=True)
            with open(f"/tmp/ctrip_debug/page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w") as f:
                f.write(body_text[:30000])
        except Exception:
            pass

        lines = body_text.split('\n')

        # 找到所有"发表于:"行索引
        pub_indices = []
        for i, line in enumerate(lines):
            if re.search(r'发表于:\s*\d{4}年', line):
                pub_indices.append(i)

        if not pub_indices:
            return []

        reviews = []
        prev_boundary = -1  # 上一个窗口结束位置，避免跨点评重叠

        for pub_idx in pub_indices:
            # 确保窗口不包含前一条点评的"发表于:"
            start = max(prev_boundary + 1, pub_idx - 30)
            end = min(len(lines), pub_idx + 5)
            block = '\n'.join(lines[start:end])

            r = self._parse_review_text(block)
            if r and r.content and len(r.content) >= 3:
                if not any(existing.platform_review_id == r.platform_review_id for existing in reviews):
                    reviews.append(r)

            prev_boundary = pub_idx  # 下一条点评从这里之后开始

        return reviews

    async def submit_reply(self, page: Page, review_id: str, reply_text: str) -> bool:
        """提交回复"""
        try:
            await page.goto("https://ebooking.ctrip.com/comment/commentList", wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 找到对应点评的回复框
            for ta_sel in ["textarea#content", "textarea[name='content']", "textarea.reply-area",
                           "textarea", "[class*='reply'] textarea"]:
                try:
                    await page.fill(ta_sel, reply_text, timeout=3000)
                    break
                except Exception:
                    continue
            await asyncio.sleep(0.5)

            for btn_sel in ["button:has-text('提交')", "button:has-text('回复')", ".submit-btn",
                            "button.primary", "input[value='提交']"]:
                try:
                    await page.click(btn_sel, timeout=3000)
                    await asyncio.sleep(2)
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
