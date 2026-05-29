import asyncio
import hashlib
import re
from datetime import datetime
from typing import List
from playwright.async_api import Page
from app.ota.base import OTAAdapter, RawReview


class CtripAdapter(OTAAdapter):
    platform = "ctrip"

    async def login(self, page: Page, username: str, password: str) -> bool:
        """登录携程ebooking后台 - 优先检查已有cookie，失效时尝试自动登录"""
        # 如果cookie已经有效，直接返回成功
        if await self.check_login_status(page):
            return True

        # Cookie失效，尝试自动填表登录
        if not username or not password:
            return False

        try:
            await page.goto("https://ebooking.ctrip.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 填写用户名
            for user_sel in ["input[name='username']", "input[name='userName']", "input[name='account']",
                             "input#userName", "input#username", "input[type='text']"]:
                try:
                    await page.fill(user_sel, username, timeout=3000)
                    break
                except Exception:
                    continue

            # 填写密码
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
        """检查是否已登录 - 先访问首页看cookie是否有效，再尝试点评页"""
        try:
            # 先访问ebooking首页，检查cookie是否有效
            await page.goto("https://ebooking.ctrip.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            url = page.url.lower()
            title = await page.title()

            # 被重定向到登录页 = cookie失效
            if "login" in url or "登录" in title:
                return False

            # 仍在ebooking域名下 = cookie有效
            if "ebooking" in url:
                return True

            # 尝试直接访问需登录的点评列表页进一步验证
            await page.goto("https://ebooking.ctrip.com/comment/commentList", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            url = page.url.lower()
            if "login" in url:
                return False
            return "ebooking" in url or "comment" in url
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

        # 优先抓待回复点评，再尝试差评，最后兜底抓全部点评
        tabs_to_try = [
            ("待回复", ["text=待回复", "a:has-text('待回复')", "span:has-text('待回复')", "div:has-text('待回复')"]),
            ("差评", ["text=差评", "a:has-text('差评')", "span:has-text('差评')", "div:has-text('差评')"]),
            ("全部点评", ["text=全部点评", "a:has-text('全部点评')", "span:has-text('全部点评')"]),
        ]

        for tab_name, tab_selectors in tabs_to_try:
            # 点击对应标签（全部点评是默认视图，不需要点击）
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
                        // 跳过补充点评（会和主点评重复）
                        if (text.includes('补充点评:')) continue;

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
        """解析携程ebooking单条点评文本

        携程页面每条点评的文本格式（从上到下）：
            [客人名]
            [空行]
            [入住年月: YYYY年MM月]
            [空行]
            [房型]
            [空行]
            [可选: 反馈异常点评 / AI点评保护]
            [可选: 异常评分数字]
            [子评分: 设施 X, 卫生 X, 环境 X, 服务 X]  ← 可能缺个别项
            [空行]
            [点评正文 - 可能多行]
            [空行]
            发表于: YYYY年MM月DD日HH:MM:SS
            [空行]
            [可选: 酒店回复内容: + 回复正文 + 回复员工行]
        """
        lines = text.split('\n')
        if len(lines) < 4:
            return None

        # 1. 找到"发表于:"行
        pub_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if re.search(r'发表于:\s*\d{4}年', lines[i]):
                pub_idx = i
                break
        if pub_idx < 0:
            return None

        # 提取发表日期
        m = re.search(r'发表于:\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2}):(\d{2})', lines[pub_idx])
        if m:
            try:
                review_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                      int(m.group(4)), int(m.group(5)), int(m.group(6)))
            except Exception:
                review_date = datetime.now()
        else:
            review_date = datetime.now()

        # 2. 检测已有回复（在"发表于:"之后）
        after_text = '\n'.join(lines[pub_idx + 1:pub_idx + 20])
        has_hotel_reply = '酒店回复内容' in after_text

        # 3. 向上扫描：从"发表于:"往前，跳过空行 → 点评正文 → 空行 → 评分区 → 元数据区
        j = pub_idx - 1
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 收集点评正文
        content_lines = []
        while j >= 0 and lines[j].strip():
            content_lines.insert(0, lines[j].strip())
            j -= 1
        content = '\n'.join(content_lines).strip()

        # 验证正文有效性
        if not content or len(content) < 3:
            return None
        if content.startswith('尊敬的') and '回复员工' in content:
            return None
        if content.startswith('补充点评') or '\n补充点评' in content:
            return None
        if len(content) > 2000:
            return None

        # 跳过正文前空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 4. 解析评分区：子评分 + 可能的前置异常分
        rating = None
        sub_ratings = {}
        abnormal_score = None
        for _ in range(10):
            if j < 0:
                break
            line = lines[j].strip()
            if not line:
                break
            # 子评分: 设施 X, 卫生 X, 环境 X, 服务 X
            sm = re.match(r'^(设施|卫生|环境|服务)\s+([\d.]+)$', line)
            if sm:
                sub_ratings[sm.group(1)] = float(sm.group(2))
                j -= 1
                continue
            # 异常分（紧接在"反馈异常点评"下方）
            am = re.match(r'^([\d.]+)$', line)
            if am:
                val = float(am.group(1))
                if val <= 5:
                    abnormal_score = val
                j -= 1
                continue
            # 主评分显示（如 "4.8超棒"、"5超棒"）——在子评分上方，需跳过
            main_rating = re.match(r'^(\d+(?:\.\d+)?)([一-龥]{1,4})$', line)
            if main_rating:
                val = float(main_rating.group(1))
                if val <= 5:
                    rating = val  # 主评分比子评分均值更准确
                j -= 1
                continue
            # 状态标签
            if line in ('反馈异常点评', 'AI点评保护') or '不计入' in line:
                j -= 1
                continue
            # 非评分行，结束
            break

        # 计算实际评分：主评分（携程显示分）优先，其次子评分均值，最后异常分
        main_rating_val = rating  # 可能被主评分行设置（如 "4.8超棒"）
        computed_rating = round(sum(sub_ratings.values()) / len(sub_ratings), 1) if len(sub_ratings) >= 2 else None
        if main_rating_val and 0 < main_rating_val <= 5:
            rating = main_rating_val
        elif computed_rating:
            rating = computed_rating
        elif abnormal_score is not None:
            rating = abnormal_score
        else:
            rating = 3.0

        # 5. 跳过评分区前空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 6. 房型（含"房"或"套"且不超过30字）
        room_type = ""
        if j >= 0:
            line = lines[j].strip()
            if ('房' in line or '套' in line) and len(line) <= 30:
                # 排除客人名误匹配：真正的房型不会是很短的词
                if not re.match(r'^[\w*_]+$', line) or len(line) >= 4:
                    room_type = line
                    j -= 1

        # 跳过空行
        while j >= 0 and not lines[j].strip():
            j -= 1

        # 7. 入住年月
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

        # 8. 客人名（块最顶部的非空行）
        guest_name = ""
        if j >= 0:
            line = lines[j].strip()
            # 过滤明显不是客人名的内容
            is_metadata = any(k in line for k in [
                '点评', '回复', '酒店', '携程', '筛选', '下载', '发表于',
                '反馈', '不计入', '保护', '规则', '查看', '返现', '排序',
                '首页', '订单', '房价', '商机', '帮助', '下载App',
            ])
            is_room_type = ('房' in line and '豪华' in line) or ('套' in line and '套房' in line) or ('居室' in line)
            if not is_metadata and not is_room_type and len(line) <= 40:
                guest_name = line

        # 用 guest_name + 日期 + 内容前50字生成稳定 ID（hashlib 保证跨进程一致）
        raw_id = hashlib.md5(f"{guest_name}_{review_date.strftime('%Y%m%d')}_{content[:50]}".encode()).hexdigest()

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
        prev_boundary = -1  # 上一个"发表于:"位置，用于避免块重叠

        for pub_idx in pub_indices:
            # 跳过前一条点评的回复/补充区域
            block_start = prev_boundary + 1
            for skip_i in range(prev_boundary + 1, pub_idx):
                line = lines[skip_i]
                if '回复员工' in line or line.strip().startswith('补充点评'):
                    block_start = skip_i + 1
            start = max(block_start, pub_idx - 30)
            end = min(len(lines), pub_idx + 5)
            block = '\n'.join(lines[start:end])

            r = self._parse_review_text(block)
            if r and r.content and len(r.content) >= 3:
                if not any(existing.platform_review_id == r.platform_review_id for existing in reviews):
                    reviews.append(r)

            prev_boundary = pub_idx  # 下一条点评从这里之后开始

        return reviews

    async def submit_reply(self, page: Page, review_id: str, reply_text: str) -> bool:
        """提交单条回复（兼容旧接口，实际委托给批量方法）"""
        return False  # 实际使用 submit_replies_batch

    async def submit_replies_batch(self, page: Page, review_pairs: list) -> list:
        """批量提交回复到携程后台

        Args:
            review_pairs: [{"guest_name": "...", "content": "...", "reply_text": "..."}, ...]

        Returns:
            [{"index": 0, "success": True}, {"index": 1, "success": False, "error": "..."}]
        """
        results = []
        try:
            # 确保在点评列表页
            current_url = page.url.lower()
            if "comment" not in current_url or "ebooking" not in current_url:
                await page.goto("https://ebooking.ctrip.com/comment/commentList",
                                wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)

            # 点击"待回复"标签
            tab_clicked = False
            for tab_sel in ["text=待回复", "span:has-text('待回复')", "div:has-text('待回复')"]:
                try:
                    el = await page.query_selector(tab_sel)
                    if el:
                        await el.click()
                        await asyncio.sleep(2)
                        tab_clicked = True
                        break
                except Exception:
                    continue

            if not tab_clicked:
                return [{"index": i, "success": False, "error": "找不到待回复标签"} for i in range(len(review_pairs))]

            # 等待页面渲染
            await page.wait_for_selector("text=发表于:", timeout=10000)
            await asyncio.sleep(1)

            # 逐条处理
            for idx, pair in enumerate(review_pairs):
                try:
                    result = await self._submit_one_reply(page, pair)
                    results.append({"index": idx, **result})
                except Exception as e:
                    results.append({"index": idx, "success": False, "error": str(e)[:200]})

                # 避免触发反爬
                if idx < len(review_pairs) - 1:
                    await asyncio.sleep(1)

            return results
        except Exception as e:
            return [{"index": i, "success": False, "error": str(e)[:200]} for i in range(len(review_pairs))]

    async def _submit_one_reply(self, page: Page, pair: dict) -> dict:
        """提交单条回复到携程

        携程"待回复"页面的实际UI结构（React SPA + Trip.com UI kit）：
        - 每条点评卡片里直接嵌入了 textarea（不是弹窗模式）
        - 在 textarea 中输入文本后，"发表回复"和"取消"按钮才会动态出现
        - 点击"发表回复"提交，成功消息："更改后的点评将在24小时内更新到前端网站"
        """
        guest_name = pair.get("guest_name", "")
        content = pair.get("content", "")
        reply_text = pair.get("reply_text", "")

        if not reply_text:
            return {"success": False, "error": "回复内容为空"}

        # 1. 通过JS在匹配的点评卡片上标记 data-auto-submit 属性
        marked = await page.evaluate("""
            ({guestName, contentSnippet}) => {
                const cards = document.querySelectorAll('[class*="ct61sa9"]');
                for (let i = 0; i < cards.length; i++) {
                    const text = cards[i].textContent || '';
                    let score = 0;
                    if (guestName && text.includes(guestName)) score += 10;
                    if (contentSnippet && text.includes(contentSnippet)) score += 15;
                    if (text.includes('酒店回复内容')) score -= 100;
                    if (score >= 15) {
                        cards[i].setAttribute('data-auto-submit', 'true');
                        return true;
                    }
                }
                return false;
            }
        """, {"guestName": guest_name, "contentSnippet": (content or "")[:40]})

        if not marked:
            return {"success": False, "error": "找不到匹配的点评卡片"}

        # 2. 获取该卡片内的 textarea
        card = page.locator('[data-auto-submit="true"]')
        ta = card.locator('textarea').first
        try:
            await ta.scroll_into_view_if_needed(timeout=3000)
            await asyncio.sleep(0.3)
        except Exception:
            pass

        # 3. 输入回复文本（触发React onChange，动态显示"发表回复"按钮）
        await ta.click()
        await asyncio.sleep(0.2)
        await ta.fill("")  # 清除可能已有的草稿
        await ta.fill(reply_text)
        await asyncio.sleep(0.8)

        # 4. 点击"发表回复"按钮（输入文本后才出现）
        submit_btn = card.locator('button:has-text("发表回复")')
        try:
            await submit_btn.wait_for(state="visible", timeout=5000)
        except Exception:
            # 清除标记
            await page.evaluate("""
                () => { const el = document.querySelector('[data-auto-submit="true"]');
                        if (el) el.removeAttribute('data-auto-submit'); }
            """)
            return {"success": False, "error": "发表回复按钮未出现"}

        await submit_btn.click()
        await asyncio.sleep(2)

        # 5. 验证提交结果
        result = await page.evaluate("""
            () => {
                const msgs = document.querySelectorAll('[class*="message"]');
                for (const m of msgs) {
                    if (m.offsetHeight > 0) {
                        const text = m.textContent || '';
                        if (text.includes('24小时') || text.includes('成功')) return {ok: true, msg: text.substring(0, 80)};
                        if (text.includes('失败') || text.includes('错误')) return {ok: false, msg: text.substring(0, 80)};
                    }
                }
                return {ok: true, msg: '已提交（无错误提示）'};
            }
        """)

        # 清除标记
        await page.evaluate("""
            () => { const el = document.querySelector('[data-auto-submit="true"]');
                    if (el) el.removeAttribute('data-auto-submit'); }
        """)

        if result.get("ok"):
            return {"success": True}
        return {"success": False, "error": result.get("msg", "未知提交结果")}

    async def _close_any_modal(self, page: Page):
        """关闭页面上可能残留的模态框"""
        try:
            # 尝试点遮罩层
            mask = page.locator('[class*="modal-mask"], [class*="Modal"] [class*="mask"]').first
            if await mask.is_visible(timeout=1000):
                await mask.click(timeout=2000)
                await asyncio.sleep(0.5)
                return
        except Exception:
            pass

        try:
            # 尝试点关闭按钮
            close_btn = page.locator('[class*="modal"] [class*="close"], [class*="Modal"] button[class*="close"], [aria-label="Close"], [aria-label="关闭"]').first
            if await close_btn.is_visible(timeout=1000):
                await close_btn.click(timeout=2000)
                await asyncio.sleep(0.5)
                return
        except Exception:
            pass

        try:
            # 按 Escape 键关闭
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception:
            pass
