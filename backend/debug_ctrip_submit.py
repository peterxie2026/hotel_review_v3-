"""诊断脚本：打开携程待回复页面，导出DOM结构"""
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models import OTAAccount, Hotel
from app.services.crypto_service import decrypt_password
from app.browser import get_browser_pool

os.makedirs("/tmp/ctrip_debug", exist_ok=True)


async def main():
    db = SessionLocal()
    # 找西金阁的OTA账号
    hotel = db.query(Hotel).filter(Hotel.name.contains("西金阁")).first()
    if not hotel:
        print("找不到西金阁酒店")
        return

    account = db.query(OTAAccount).filter(
        OTAAccount.hotel_id == hotel.id,
        OTAAccount.platform == "ctrip",
        OTAAccount.is_active == True,
    ).first()
    if not account:
        print("找不到携程OTA账号")
        return

    password = decrypt_password(account.encrypted_password or "")
    print(f"账号: {account.username}")

    pool = await get_browser_pool()
    context = await pool.get_context(account.id, account.cookies_json)
    page = await context.new_page()

    try:
        # 登录
        print("登录中...")
        from app.ota.ctrip import CtripAdapter
        adapter = CtripAdapter()
        logged_in = await adapter.login(page, account.username, password)
        print(f"登录结果: {logged_in}")

        if not logged_in:
            print("登录失败!")
            await page.screenshot(path="/tmp/ctrip_debug/login_fail.png", full_page=True)
            return

        # 保存 cookie
        new_cookies = json.dumps(await context.cookies())
        account.cookies_json = new_cookies
        db.commit()

        # 导航到点评列表
        print("导航到点评列表...")
        await page.goto("https://ebooking.ctrip.com/comment/commentList",
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 点击待回复
        print("点击待回复标签...")
        for tab_sel in ["text=待回复", "span:has-text('待回复')", "div:has-text('待回复')"]:
            try:
                el = await page.query_selector(tab_sel)
                if el:
                    await el.click()
                    await asyncio.sleep(2)
                    print(f"  点击成功: {tab_sel}")
                    break
            except Exception as e:
                print(f"  {tab_sel}: {e}")

        # 等待页面渲染
        await page.wait_for_selector("text=发表于:", timeout=10000)
        await asyncio.sleep(2)

        # 截图
        await page.screenshot(path="/tmp/ctrip_debug/submit_debug.png", full_page=True)
        print("截图已保存: /tmp/ctrip_debug/submit_debug.png")

        # 保存完整HTML
        html = await page.content()
        with open("/tmp/ctrip_debug/submit_full.html", "w") as f:
            f.write(html)
        print(f"HTML已保存: /tmp/ctrip_debug/submit_full.html ({len(html)} 字节)")

        # JS枚举所有点评卡片中的可交互元素
        print("\n=== DOM分析 ===")
        dom_info = await page.evaluate("""
            () => {
                const result = {reviewCards: [], allButtons: [], allClickables: []};

                // 找所有包含"发表于:"的元素（点评卡片）
                const allEls = document.querySelectorAll('div, li, tr, section');
                for (const el of allEls) {
                    const text = el.textContent || '';
                    if (!text.includes('发表于:')) continue;
                    if (text.length < 50 || text.length > 5000) continue;

                    const cardInfo = {
                        tagName: el.tagName,
                        className: el.className?.toString()?.substring(0, 200) || '',
                        textPreview: text.substring(0, 150),
                        childButtons: [],
                        childLinks: [],
                        childSpans: [],
                    };

                    // 列出所有子按钮
                    const btns = el.querySelectorAll('button');
                    for (const btn of btns) {
                        cardInfo.childButtons.push({
                            text: (btn.textContent || '').trim().substring(0, 50),
                            className: btn.className?.toString()?.substring(0, 200) || '',
                            visible: btn.offsetHeight > 0,
                        });
                        result.allButtons.push(cardInfo.childButtons[cardInfo.childButtons.length - 1]);
                    }

                    // 列出所有链接
                    const links = el.querySelectorAll('a');
                    for (const link of links) {
                        if (link.offsetHeight > 0) {
                            cardInfo.childLinks.push({
                                text: (link.textContent || '').trim().substring(0, 50),
                                href: (link.href || '').substring(0, 100),
                                className: link.className?.toString()?.substring(0, 200) || '',
                            });
                        }
                    }

                    // 列出所有span（可能有图标文字）
                    const spans = el.querySelectorAll('span');
                    for (const span of spans) {
                        const t = (span.textContent || '').trim();
                        if (t && t.length < 20 && span.offsetHeight > 0) {
                            cardInfo.childSpans.push(t);
                        }
                    }

                    result.reviewCards.push(cardInfo);
                }

                // 全局找所有包含"回复"文字的按钮
                const allPageBtns = document.querySelectorAll('button, a, span[role="button"]');
                for (const btn of allPageBtns) {
                    const t = (btn.textContent || '').trim();
                    if (t.includes('回复') && btn.offsetHeight > 0) {
                        result.allClickables.push({
                            tag: btn.tagName,
                            text: t.substring(0, 50),
                            className: btn.className?.toString()?.substring(0, 200) || '',
                        });
                    }
                }

                return result;
            }
        """)

        print(f"找到 {len(dom_info['reviewCards'])} 个点评卡片")
        for i, card in enumerate(dom_info['reviewCards']):
            print(f"\n--- 卡片 {i+1}: <{card['tagName']}> class='{card['className'][:80]}' ---")
            print(f"  内容: {card['textPreview'][:80]}...")
            print(f"  按钮({len(card['childButtons'])}): {[b['text'] for b in card['childButtons'] if b['visible']]}")
            print(f"  链接({len(card['childLinks'])}): {[l['text'] for l in card['childLinks']]}")
            print(f"  span文字: {card['childSpans'][:10]}")

        print(f"\n全局'回复'相关元素: {len(dom_info['allClickables'])}")
        for el in dom_info['allClickables']:
            print(f"  <{el['tag']}> class='{el['className'][:80]}' text='{el['text']}'")

    finally:
        await page.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
