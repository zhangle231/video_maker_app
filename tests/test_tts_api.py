"""
TTS 语音功能 API 自动化测试
测试范围: TC-01 ~ TC-25
运行方式: pytest tests/test_tts_api.py -v
"""
import os
import sys
import json
import time
import shutil
import pytest

# 项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video_maker_app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def setup_teardown():
    """每个测试前后清理 tts 目录"""
    tts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tts")
    temp_tts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp", "tts")
    os.makedirs(tts_dir, exist_ok=True)
    os.makedirs(temp_tts_dir, exist_ok=True)
    yield
    for d in [tts_dir, temp_tts_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)


# ============================================================
# 3.1 TTS 单段生成 (TC-01 ~ TC-06)
# ============================================================

class TestSingleGenerate:
    """TC-01 ~ TC-06: 单段 TTS 生成"""

    def test_normal_generate(self, client):
        """TC-01: 正常生成"""
        resp = client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": "这是第一段旁白文字",
            "style": "gentle_female"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["segment_id"] == "seg_0"
        assert data["duration"] > 0
        assert "audio_path" in data

    def test_empty_text(self, client):
        """TC-02: 空文本应拒绝"""
        resp = client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": "",
            "style": "gentle_female"
        })
        data = resp.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_long_text(self, client):
        """TC-03: 极长文本 500 字"""
        text = "今天天气真好" * 100  # 600 字
        resp = client.post("/api/tts/generate", json={
            "segment_id": "seg_long",
            "text": text,
            "style": "gentle_female"
        })
        data = resp.get_json()
        assert data["success"] is True
        assert data["duration"] > 5  # 长文本应有较长时长

    def test_all_styles(self, client):
        """TC-04: 三种风格均能生成"""
        styles = ["gentle_female", "tvb_style", "shaw_style"]
        for i, style in enumerate(styles):
            resp = client.post("/api/tts/generate", json={
                "segment_id": f"seg_style_{i}",
                "text": "测试不同风格的语音生成效果",
                "style": style
            })
            data = resp.get_json()
            assert data["success"] is True, f"风格 {style} 生成失败: {data}"
            assert data["duration"] > 0

    def test_overwrite_same_segment(self, client):
        """TC-05: 重复生成相同段应覆盖"""
        # 第一次
        resp1 = client.post("/api/tts/generate", json={
            "segment_id": "seg_dup",
            "text": "第一次生成",
            "style": "gentle_female"
        })
        assert resp1.get_json()["success"] is True
        # 第二次
        resp2 = client.post("/api/tts/generate", json={
            "segment_id": "seg_dup",
            "text": "第二次覆盖生成",
            "style": "tvb_style"
        })
        assert resp2.get_json()["success"] is True

    def test_special_characters(self, client):
        """TC-06: 特殊字符"""
        resp = client.post("/api/tts/generate", json={
            "segment_id": "seg_special",
            "text": "Hello! 这是一段包含数字123、标点，以及\n换行的文本。",
            "style": "gentle_female"
        })
        data = resp.get_json()
        assert data["success"] is True
        assert data["duration"] > 0


# ============================================================
# 3.2 批量生成与进度轮询 (TC-07 ~ TC-11)
# ============================================================

class TestBatchGenerate:
    """TC-07 ~ TC-11: 批量生成与轮询"""

    def test_batch_two_segments(self, client):
        """TC-07: 2 段批量生成"""
        resp = client.post("/api/tts/generate-all", json={
            "segments": [
                {"segment_id": "seg_0", "text": "第一段旁白"},
                {"segment_id": "seg_1", "text": "第二段旁白"}
            ],
            "style": "gentle_female"
        })
        data = resp.get_json()
        assert data["success"] is True
        assert data["total"] == 2
        assert "task_id" in data

    def test_poll_progress(self, client):
        """TC-08: 轮询进度直到完成"""
        # 先发起批量生成
        resp = client.post("/api/tts/generate-all", json={
            "segments": [
                {"segment_id": "seg_a", "text": "一段"},
                {"segment_id": "seg_b", "text": "二段"}
            ],
            "style": "gentle_female"
        })
        assert resp.get_json()["success"] is True

        # 轮询直到 done
        max_attempts = 30
        for _ in range(max_attempts):
            time.sleep(2)
            resp = client.get("/api/tts/progress")
            data = resp.get_json()
            if data["status"] in ("done", "partial"):
                break

        assert data["status"] == "done"
        assert data["completed"] == 2
        for seg_id in ("seg_a", "seg_b"):
            assert data["segments"][seg_id]["status"] == "done"

    def test_batch_with_empty_text(self, client):
        """TC-09: 含空文本段时的部分失败"""
        resp = client.post("/api/tts/generate-all", json={
            "segments": [
                {"segment_id": "seg_ok", "text": "正常文本"},
                {"segment_id": "seg_empty", "text": ""}
            ],
            "style": "gentle_female"
        })
        assert resp.get_json()["success"] is True

        # 轮询
        for _ in range(30):
            time.sleep(2)
            resp = client.get("/api/tts/progress")
            data = resp.get_json()
            if data["status"] in ("done", "partial"):
                break

        assert data["status"] == "partial"
        assert data["segments"]["seg_ok"]["status"] == "done"
        assert data["segments"]["seg_empty"]["status"] == "failed"

    def test_batch_empty_list(self, client):
        """TC-10: 空列表"""
        resp = client.post("/api/tts/generate-all", json={
            "segments": [],
            "style": "gentle_female"
        })
        data = resp.get_json()
        # 空列表要么拒绝要么 total=0
        assert data.get("success") is False or data.get("total") == 0

    def test_progress_updates_increment(self, client):
        """TC-11: 多次轮询值递增"""
        resp = client.post("/api/tts/generate-all", json={
            "segments": [
                {"segment_id": "seg_1", "text": "第一段语音"},
                {"segment_id": "seg_2", "text": "第二段语音"},
                {"segment_id": "seg_3", "text": "第三段语音"}
            ],
            "style": "gentle_female"
        })
        assert resp.get_json()["success"] is True

        completed_values = []
        for _ in range(30):
            time.sleep(1.5)
            resp = client.get("/api/tts/progress")
            data = resp.get_json()
            completed_values.append(data["completed"])
            if data["status"] == "done":
                break

        assert completed_values[-1] == 3
        # 验证单调递增
        for i in range(1, len(completed_values)):
            assert completed_values[i] >= completed_values[i-1]


# ============================================================
# 3.3 语音文件访问 (TC-12 ~ TC-15)
# ============================================================

class TestAudioFileAccess:
    """TC-12 ~ TC-15: 语音文件 CRUD"""

    @pytest.fixture(autouse=True)
    def generate_audio(self, client):
        """前置：生成一段语音供测试"""
        resp = client.post("/api/tts/generate", json={
            "segment_id": "seg_audio",
            "text": "用于文件访问测试的语音",
            "style": "gentle_female"
        })
        assert resp.get_json()["success"] is True

    def test_access_existing_audio(self, client):
        """TC-12: 访问已生成语音"""
        resp = client.get("/api/tts/audio/seg_audio")
        assert resp.status_code == 200
        assert "audio" in resp.content_type

    def test_access_nonexistent_audio(self, client):
        """TC-13: 访问不存在的语音"""
        resp = client.get("/api/tts/audio/nonexist")
        assert resp.status_code == 404

    def test_delete_existing_audio(self, client):
        """TC-14: 删除已生成语音"""
        resp = client.delete("/api/tts/audio/seg_audio")
        data = resp.get_json()
        assert data["success"] is True
        # 确认文件已删除
        resp2 = client.get("/api/tts/audio/seg_audio")
        assert resp2.status_code == 404

    def test_delete_nonexistent_audio(self, client):
        """TC-15: 删除不存在语音（幂等）"""
        resp = client.delete("/api/tts/audio/nonexist")
        data = resp.get_json()
        assert data["success"] is True


# ============================================================
# 3.4 视频合成集成 (TC-16 ~ TC-22)
# ============================================================

class TestVideoComposeIntegration:
    """TC-16 ~ TC-22: 视频合成集成测试"""

    IMAGE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_image.jpg")
    OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_videos")

    @classmethod
    def setup_class(cls):
        """创建测试图片和输出目录"""
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)
        if not os.path.exists(cls.IMAGE):
            from PIL import Image
            img = Image.new("RGB", (640, 480), color="blue")
            img.save(cls.IMAGE)

    def test_tts_only_no_bgm(self, client):
        """TC-16: 仅 TTS 无 BGM"""
        # 先生成语音
        client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": "纯语音无背景音乐的测试",
            "style": "gentle_female"
        })
        # 合成
        output = os.path.join(self.OUTPUT_DIR, "tc16_tts_only.mp4")
        resp = client.post("/api/generate", json={
            "image_paths": [self.IMAGE],
            "subtitles": ["测试字幕"],
            "durations": [10],
            "output_path": output,
            "tts_enabled": True,
            "tts_style": "gentle_female",
            "voice_volume": 1.0,
            "bgm_volume": 0.0
        })
        data = resp.get_json()
        assert data["success"] is True
        assert os.path.exists(output)
        assert os.path.getsize(output) > 1000

    def test_tts_with_bgm(self, client):
        """TC-17: TTS + BGM 混合"""
        # 生成语音
        client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": "语音加背景音乐的混合测试",
            "style": "gentle_female"
        })
        # 用 warm 风格的第一首音乐
        import json as j
        manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "music_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = j.load(f)
            music_id = list(manifest.keys())[0] if manifest else None
        else:
            music_id = None

        output = os.path.join(self.OUTPUT_DIR, "tc17_tts_bgm.mp4")
        params = {
            "image_paths": [self.IMAGE],
            "subtitles": ["混合测试"],
            "durations": [10],
            "output_path": output,
            "tts_enabled": True,
            "voice_volume": 0.8,
            "bgm_volume": 0.4
        }
        if music_id:
            params["music_id"] = music_id

        resp = client.post("/api/generate", json=params)
        data = resp.get_json()
        assert data["success"] is True
        assert os.path.exists(output)

    def test_voice_longer_than_image(self, client):
        """TC-18: 语音长于图片，自动延长"""
        long_text = "这是一段比较长的文字" * 10
        client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": long_text,
            "style": "gentle_female"
        })
        output = os.path.join(self.OUTPUT_DIR, "tc18_long_voice.mp4")
        resp = client.post("/api/generate", json={
            "image_paths": [self.IMAGE],
            "subtitles": [long_text],
            "durations": [2],  # 图片仅 2 秒
            "output_path": output,
            "tts_enabled": True,
            "voice_volume": 1.0,
            "bgm_volume": 0.0
        })
        data = resp.get_json()
        assert data["success"] is True

        # 验证视频时长 > 2 秒
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(output)
        actual_duration = clip.duration
        clip.close()
        assert actual_duration > 2, f"预期视频时长 > 2s，实际 {actual_duration}s"

    def test_voice_shorter_than_image(self, client):
        """TC-19: 语音短于图片，图片持续完整"""
        client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": "短",
            "style": "gentle_female"
        })
        output = os.path.join(self.OUTPUT_DIR, "tc19_short_voice.mp4")
        resp = client.post("/api/generate", json={
            "image_paths": [self.IMAGE],
            "subtitles": ["短"],
            "durations": [10],
            "output_path": output,
            "tts_enabled": True,
            "voice_volume": 1.0,
            "bgm_volume": 0.0
        })
        data = resp.get_json()
        assert data["success"] is True

        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(output)
        assert abs(clip.duration - 10) < 0.5, f"预期 ~10s，实际 {clip.duration}s"
        clip.close()

    def test_tts_disabled(self, client):
        """TC-20: TTS 关闭走原逻辑"""
        output = os.path.join(self.OUTPUT_DIR, "tc20_no_tts.mp4")
        resp = client.post("/api/generate", json={
            "image_paths": [self.IMAGE],
            "subtitles": ["无语音"],
            "durations": [5],
            "output_path": output,
            "tts_enabled": False
        })
        data = resp.get_json()
        assert data["success"] is True
        assert os.path.exists(output)

    def test_volume_extremes(self, client):
        """TC-21: 音量极值"""
        client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": "音量极值测试",
            "style": "gentle_female"
        })
        output = os.path.join(self.OUTPUT_DIR, "tc21_volume.mp4")
        resp = client.post("/api/generate", json={
            "image_paths": [self.IMAGE],
            "subtitles": ["极值"],
            "durations": [8],
            "output_path": output,
            "tts_enabled": True,
            "voice_volume": 2.0,
            "bgm_volume": 0.0
        })
        data = resp.get_json()
        assert data["success"] is True

    def test_multi_style_segments(self, client):
        """TC-22: 多段不同风格（通过分别生成实现）"""
        # 当前设计: 风格是全局的，此测试验证不同风格音频文件均可被合成使用
        client.post("/api/tts/generate", json={
            "segment_id": "seg_0",
            "text": "温柔女声的语音",
            "style": "gentle_female"
        })
        client.post("/api/tts/generate", json={
            "segment_id": "seg_1",
            "text": "邵氏风格的语音",
            "style": "shaw_style"
        })
        output = os.path.join(self.OUTPUT_DIR, "tc22_multistyle.mp4")
        resp = client.post("/api/generate", json={
            "image_paths": [self.IMAGE, self.IMAGE],
            "subtitles": ["温柔", "邵氏"],
            "durations": [8, 8],
            "output_path": output,
            "tts_enabled": True,
            "voice_volume": 1.0,
            "bgm_volume": 0.0
        })
        data = resp.get_json()
        assert data["success"] is True


# ============================================================
# 3.5 异常场景 (TC-23 ~ TC-25)
# ============================================================

class TestErrorScenarios:
    """TC-23 ~ TC-25: 异常场景"""

    def test_missing_audio_on_compose(self, client):
        """TC-24: 合成时语音文件不存在应静默跳过"""
        output = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "test_videos", "tc24_missing_audio.mp4"
        )
        os.makedirs(os.path.dirname(output), exist_ok=True)
        resp = client.post("/api/generate", json={
            "image_paths": [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_image.jpg")
            ],
            "subtitles": ["测试"],
            "durations": [5],
            "output_path": output,
            "tts_enabled": True,
            "voice_volume": 1.0,
            "bgm_volume": 0.0
        })
        # 即使没有 TTS 文件也不应崩溃
        data = resp.get_json()
        assert data["success"] is True

    def test_duplicate_batch_submission(self, client):
        """TC-25: 快速两次批量生成"""
        # 第一次
        resp1 = client.post("/api/tts/generate-all", json={
            "segments": [{"segment_id": "seg_a", "text": "测试A"}],
            "style": "gentle_female"
        })
        # 第二次（覆盖）
        resp2 = client.post("/api/tts/generate-all", json={
            "segments": [{"segment_id": "seg_b", "text": "测试B"}],
            "style": "gentle_female"
        })
        assert resp1.get_json()["success"] is True
        assert resp2.get_json()["success"] is True
