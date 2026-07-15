"""
TTS 语音功能 - 前端 UI 自动化测试 (Playwright)
测试范围: TC-26 ~ TC-30
运行方式: pytest tests/test_tts_ui.py -v
前置条件: video_maker_app.py 已启动 (python video_maker_app.py)
"""
import os
import sys
import json
import time
import pytest

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

BASE_URL = "http://127.0.0.1:5000"


# ============================================================
# Playwright fixtures
# ============================================================

@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(10000)
    yield page
    context.close()


def navigate_to_app(page):
    """打开应用主页并等待加载"""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    time.sleep(1)


def fill_image_text(page, index, text):
    """在指定索引的图片段填入旁白文字"""
    # 假设每段旁白文字使用 textarea 或 input，按索引定位
    textareas = page.locator("textarea, input[type='text']")
    if textareas.count() > index:
        textareas.nth(index).fill(text)


def find_segment_generate_btn(page, index):
    """找到第 index 段的生成语音按钮"""
    buttons = page.locator("button:has-text('生成语音')")
    if buttons.count() > index:
        return buttons.nth(index)
    return None


def find_segment_preview_btn(page, index):
    """找到第 index 段的试听按钮"""
    buttons = page.locator("button:has-text('试听')")
    if buttons.count() > index:
        return buttons.nth(index)
    return None


# ============================================================
# TC-26: 逐段生成 UI
# ============================================================

class TestSingleGenerateUI:
    """TC-26: 逐段生成 UI 交互"""

    def test_generate_button_state_transition(self, page):
        """点击生成语音后按钮状态变化，最终显示试听"""
        navigate_to_app(page)

        # 填入旁白文字
        fill_image_text(page, 0, "前端测试旁白文字")

        btn = find_segment_generate_btn(page, 0)
        assert btn is not None, "未找到生成语音按钮"
        btn.click()

        # 等待生成完成（最长 15 秒）
        page.wait_for_timeout(5000)
        # 检查试听按钮出现
        preview_btn = find_segment_preview_btn(page, 0)
        assert preview_btn is not None, "生成完成后应出现试听按钮"


# ============================================================
# TC-27: 试听播放
# ============================================================

class TestPreviewPlayback:
    """TC-27: 试听功能"""

    def test_audio_element_created(self, page):
        """试听按钮点击后应触发音频加载"""
        navigate_to_app(page)

        # 先生成语音
        fill_image_text(page, 0, "试听测试文字")
        gen_btn = find_segment_generate_btn(page, 0)
        if gen_btn:
            gen_btn.click()
            page.wait_for_timeout(5000)

        # 点击试听
        preview_btn = find_segment_preview_btn(page, 0)
        if preview_btn:
            preview_btn.click()
            page.wait_for_timeout(1000)
            # 检查页面出现 audio 元素
            audio_el = page.locator("audio")
            assert audio_el.count() > 0, "试听后应出现 audio 元素"


# ============================================================
# TC-28: 批量生成 UI
# ============================================================

class TestBatchGenerateUI:
    """TC-28: 批量生成进度条"""

    def test_batch_progress_bar_visible(self, page):
        """全部生成后进度条可见"""
        navigate_to_app(page)

        fill_image_text(page, 0, "批量测试第一段")
        fill_image_text(page, 1, "批量测试第二段")

        all_btn = page.locator("button:has-text('全部生成')")
        if all_btn.count() == 0:
            all_btn = page.locator("button:has-text('批量生成')")
        if all_btn.count() == 0:
            pytest.skip("未找到全部生成按钮")
            return

        all_btn.first.click()
        page.wait_for_timeout(3000)

        # 检查进度文字出现
        progress_text = page.locator("text=/\\d+\\/\\d+.*完成/")
        assert progress_text.count() > 0, "批量生成后应显示进度文字"


# ============================================================
# TC-29: 音量比例切换
# ============================================================

class TestVolumeModeToggle:
    """TC-29: 绝对值/相对比例切换"""

    def test_volume_mode_switch_exists(self, page):
        """音量模式切换控件存在"""
        navigate_to_app(page)

        # 查找绝对值/相对比例相关的 radio 或 toggle
        abs_radio = page.locator("text=绝对值")
        ratio_radio = page.locator("text=相对比例")

        has_mode_switch = abs_radio.count() > 0 or ratio_radio.count() > 0
        assert has_mode_switch, "应存在音量模式切换控件"

    def test_ratio_inputs_change_on_toggle(self, page):
        """切换到相对比例后滑块或输入变化"""
        navigate_to_app(page)

        ratio_radio = page.locator("text=相对比例")
        if ratio_radio.count() > 0:
            ratio_radio.first.click()
            page.wait_for_timeout(500)

            # 检查是否出现比例相关输入
            ratio_input = page.locator("text=/\\d+:\\d+/")
            assert ratio_input.count() > 0, "切换到相对比例后应出现比例控件"


# ============================================================
# TC-30: 切换风格后重新生成
# ============================================================

class TestStyleSwitchRegenerate:
    """TC-30: 风格切换 + 重新生成"""

    def test_style_dropdown_exists(self, page):
        """风格下拉菜单存在"""
        navigate_to_app(page)

        style_selector = page.locator("select, [role='listbox']")
        has_style = style_selector.count() > 0
        assert has_style, "应存在风格选择控件"

    def test_regenerate_button_appears_after_generate(self, page):
        """生成语音后出现重新生成按钮"""
        navigate_to_app(page)

        fill_image_text(page, 0, "重新生成测试")
        gen_btn = find_segment_generate_btn(page, 0)
        if gen_btn:
            gen_btn.click()
            page.wait_for_timeout(5000)

        regen_btn = page.locator("button:has-text('重新生成')")
        assert regen_btn.count() > 0, "生成完成后应出现重新生成按钮"
