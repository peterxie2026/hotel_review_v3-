"""交互式诊断：在携程待回复页面输入文本，观察UI变化"""
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
            return

        # 保存cookie
        new_cookies = json.dumps(await context.cookies())
        account.cookies_json = new_cookies
        db.commit()

        # 导航到点评列表
        print("导航到点评列表...")
        await page.goto("https://ebooking.ctrip.com/comment/commentList",
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 点击待回复tab
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

        await page.wait_for_selector("text=发表于:", timeout=10000)
        await asyncio.sleep(2)

        # 截图初始状态
        await page.screenshot(path="/tmp/ctrip_debug/step0_initial.png", full_page=True)
        print("step0: 初始截图已保存")

        # === 步骤1: 找到所有textarea并分析 ===
        print("\n=== 分析textarea ===")
        ta_info = await page.evaluate("""
            () => {
                const tas = document.querySelectorAll('textarea[id="content"]');
                const results = [];
                for (let i = 0; i < tas.length; i++) {
                    const ta = tas[i];
                    const card = ta.closest('[class*="ct61sa9"]') || ta.closest('.row');
                    results.push({
                        index: i,
                        visible: ta.offsetHeight > 0 && ta.offsetWidth > 0,
                        placeholder: ta.placeholder,
                        rect: ta.getBoundingClientRect(),
                        cardClass: card?.className?.toString()?.substring(0, 100) || '',
                        parentFormCount: ta.closest('form') ? 1 : 0,
                    });
                }
                return results;
            }
        """)
        print(f"找到 {len(ta_info)} 个textarea")
        for t in ta_info:
            print(f"  #{t['index']}: visible={t['visible']}, rect={t['rect']}")

        if not ta_info or not any(t['visible'] for t in ta_info):
            print("没有可见的textarea!")
            return

        # === 步骤2: 在第一个textarea中输入文本，观察变化 ===
        print("\n=== 输入文本测试 ===")
        first_ta = await page.query_selector('textarea[id="content"]')
        if not first_ta:
            print("找不到textarea!")
            return

        # 先点击textarea聚焦
        await first_ta.click()
        await asyncio.sleep(1)

        # 输入测试文本
        test_text = "尊敬的宾客，感谢您的点评！欢迎再次光临西金阁酒店。"
        await first_ta.fill(test_text)
        await asyncio.sleep(1.5)

        # 截图输入后状态
        await page.screenshot(path="/tmp/ctrip_debug/step1_after_input.png", full_page=True)
        print("step1: 输入文本后截图已保存")

        # 查找是否出现了提交按钮
        after_input = await page.evaluate("""
            () => {
                const result = {newButtons: [], newElements: []};

                // 查找任何包含"提交"、"发送"、"发布"文字的可见元素
                const allEls = document.querySelectorAll('button, span, div, a');
                for (const el of allEls) {
                    const text = (el.textContent || '').trim();
                    if (['提交', '发送', '发布', '确认提交', 'submit'].some(t => text === t || text.includes(t))) {
                        if (el.offsetHeight > 0) {
                            result.newButtons.push({
                                tag: el.tagName,
                                text: text.substring(0, 30),
                                className: el.className?.toString()?.substring(0, 100) || '',
                                rect: el.getBoundingClientRect(),
                            });
                        }
                    }
                }

                // 检查textarea所在form的变化
                const ta = document.querySelector('textarea[id="content"]');
                if (ta) {
                    const form = ta.closest('form');
                    if (form) {
                        const formChildren = form.querySelectorAll('*');
                        result.formChildCount = formChildren.length;
                        // 列出form内所有可见元素
                        const visibleInForm = [];
                        for (const child of formChildren) {
                            if (child.offsetHeight > 0 && child !== ta) {
                                const t = (child.textContent || '').trim();
                                if (t && t.length < 20) {
                                    visibleInForm.push({tag: child.tagName, text: t, className: child.className?.toString()?.substring(0, 80) || ''});
                                }
                            }
                        }
                        result.visibleInForm = visibleInForm;
                    }
                }

                return result;
            }
        """)
        print(f"  输入后新出现的按钮: {after_input['newButtons']}")
        print(f"  Form内可见元素: {after_input.get('visibleInForm', [])}")

        # === 步骤3: 尝试按Enter提交 ===
        print("\n=== 尝试Enter提交 ===")
        await first_ta.press("Enter")
        await asyncio.sleep(1.5)
        await page.screenshot(path="/tmp/ctrip_debug/step2_after_enter.png", full_page=True)
        print("step2: 按Enter后截图已保存")

        # 检查页面变化
        after_enter = await page.evaluate("""
            () => {
                const ta = document.querySelector('textarea[id="content"]');
                return {
                    textareaValue: ta ? ta.value?.substring(0, 50) : 'NOT_FOUND',
                    textareaExists: !!ta,
                    alertMessages: Array.from(document.querySelectorAll('[class*="alert"], [class*="message"], [class*="toast"], [class*="notification"]')).map(e => ({
                        text: (e.textContent || '').trim().substring(0, 100),
                        visible: e.offsetHeight > 0,
                    })),
                };
            }
        """)
        print(f"  Enter后: {after_enter}")

        # === 步骤4: 尝试Ctrl+Enter ===
        print("\n=== 尝试Ctrl+Enter提交 ===")
        # 清空再输入
        await first_ta.fill("")
        await asyncio.sleep(0.3)
        await first_ta.fill(test_text)
        await asyncio.sleep(0.5)

        # Ctrl+Enter (Mac上是Meta+Enter)
        await first_ta.press("Meta+Enter")
        await asyncio.sleep(2)
        await page.screenshot(path="/tmp/ctrip_debug/step3_after_ctrl_enter.png", full_page=True)
        print("step3: Ctrl+Enter后截图已保存")

        after_ctrl = await page.evaluate("""
            () => {
                const ta = document.querySelector('textarea[id="content"]');
                // Check for any modal/dialog
                const modals = document.querySelectorAll('[class*="modal"], [class*="dialog"], [class*="popup"], [class*="drawer"]');
                const visibleModals = [];
                for (const m of modals) {
                    if (m.offsetHeight > 0) {
                        visibleModals.push({
                            className: m.className?.toString()?.substring(0, 100) || '',
                            text: (m.textContent || '').trim().substring(0, 150),
                        });
                    }
                }
                return {
                    textareaValue: ta ? ta.value?.substring(0, 50) : 'NOT_FOUND',
                    visibleModals: visibleModals.slice(0, 5),
                };
            }
        """)
        print(f"  Ctrl+Enter后: {after_ctrl}")

        # === 步骤5: 查找页面级别的批量提交按钮 ===
        print("\n=== 搜索页面级别操作 ===")
        page_level = await page.evaluate("""
            () => {
                const result = {allButtons: [], allClickables: []};

                // 页面顶部的所有按钮
                const topArea = document.querySelector('[class*="c1qaiz9o"], [class*="clts02n"], [class*="header"]');
                if (topArea) {
                    const buttons = topArea.querySelectorAll('button, a, span[class*="btn"]');
                    for (const b of buttons) {
                        if (b.offsetHeight > 0) {
                            result.allButtons.push({
                                tag: b.tagName,
                                text: (b.textContent || '').trim().substring(0, 40),
                                className: b.className?.toString()?.substring(0, 100) || '',
                            });
                        }
                    }
                }

                // 查找是否有全选复选框
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                result.checkboxCount = checkboxes.length;

                // 查找footer区域（可能有固定提交栏）
                const footers = document.querySelectorAll('[class*="footer"], [class*="fixed"], [class*="sticky"], [class*="bottom"]');
                for (const f of footers) {
                    if (f.offsetHeight > 0) {
                        const ftext = (f.textContent || '').trim().substring(0, 200);
                        if (ftext.length > 5) {
                            result.footers = result.footers || [];
                            result.footers.push({text: ftext, className: f.className?.toString()?.substring(0, 100) || ''});
                        }
                    }
                }

                // Check the form surrounding the textarea for siblings
                const ta = document.querySelector('textarea[id="content"]');
                if (ta) {
                    const form = ta.closest('form');
                    const parentContainer = form?.parentElement?.parentElement;
                    if (parentContainer) {
                        result.parentContainerClass = parentContainer.className?.toString()?.substring(0, 200) || '';
                        // Get all children of the form's grandparent
                        const siblings = Array.from(parentContainer.children).map(c => ({
                            tag: c.tagName,
                            className: c.className?.toString()?.substring(0, 100) || '',
                            text: (c.textContent || '').trim().substring(0, 100),
                            visible: c.offsetHeight > 0,
                        }));
                        result.parentSiblings = siblings;
                    }
                }

                return result;
            }
        """)
        print(f"  页面按钮: {page_level.get('allButtons', [])}")
        print(f"  Checkbox数量: {page_level.get('checkboxCount', 0)}")
        print(f"  Footer: {page_level.get('footers', [])}")
        print(f"  父容器class: {page_level.get('parentContainerClass', '')[:120]}")
        print(f"  同级元素: {page_level.get('parentSiblings', [])}")

        # === 步骤6: 保存最终HTML ===
        html = await page.content()
        with open("/tmp/ctrip_debug/interact_full.html", "w") as f:
            f.write(html)
        print(f"\n最终HTML已保存: /tmp/ctrip_debug/interact_full.html ({len(html)} 字节)")

    finally:
        await page.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
