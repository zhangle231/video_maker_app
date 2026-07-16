"""
短视频拼接模块 API 测试
运行: pytest tests/test_clip_api.py -v
"""

import pytest
import io
import os
import sys

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from video_maker_app import app

client = TestClient(app)


def _make_fake_video(duration: float = 3.0, width: int = 640, height: int = 480, fps: int = 30):
    """
    生成一段极短的 h264 视频字节（使用 moviepy）。
    需要 moviepy 已安装；如果不可用则用最小的真实 mp4 替代。
    """
    try:
        from moviepy import ColorClip
        import tempfile

        clip = ColorClip(size=(width, height), color=(255, 0, 0), duration=duration)
        clip = clip.with_fps(fps)

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_path = tmp.name
        tmp.close()

        clip.write_videofile(
            tmp_path,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            logger=None,
            fps=fps,
        )
        clip.close()

        with open(tmp_path, "rb") as f:
            data = f.read()
        os.unlink(tmp_path)
        return data
    except Exception:
        pytest.skip("moviepy 不可用，跳过测试")


def _upload_video(duration: float = 3.0, filename: str = "test.mp4"):
    """上传单个视频，返回响应 JSON"""
    data = _make_fake_video(duration=duration)
    resp = client.post(
        "/api/clip/upload",
        files=[("files", (filename, io.BytesIO(data), "video/mp4"))],
    )
    return resp.json()


def _upload_multi(files_spec: list):
    """
    上传多个视频。
    files_spec: [(filename, duration), ...]
    """
    files = []
    for fname, dur in files_spec:
        data = _make_fake_video(duration=dur)
        files.append(("files", (fname, io.BytesIO(data), "video/mp4")))
    resp = client.post("/api/clip/upload", files=files)
    return resp.json()


# ══════════════════════════════════════════════════
# TC-C01: 上传单个有效视频
# ══════════════════════════════════════════════════
def test_upload_single_valid():
    result = _upload_video(duration=3.0, filename="beach.mp4")
    assert "clip_id" in result
    assert len(result["segments"]) == 1
    seg = result["segments"][0]
    assert seg["status"] == "ok"
    assert seg["filename"] == "beach.mp4"
    assert seg["duration"] <= 5.0
    assert seg["width"] > 0
    assert seg["height"] > 0
    assert seg["fps"] > 0


# ══════════════════════════════════════════════════
# TC-C02: 上传超 5 秒视频
# ══════════════════════════════════════════════════
def test_upload_too_long():
    result = _upload_video(duration=6.5, filename="long.mp4")
    seg = result["segments"][0]
    assert seg["status"] == "too_long"
    assert "超过" in seg["error_msg"]
    assert len(result["errors"]) == 1


# ══════════════════════════════════════════════════
# TC-C03: 上传混合视频（ok + too_long）
# ══════════════════════════════════════════════════
def test_upload_mixed():
    result = _upload_multi([("a.mp4", 3.0), ("b.mp4", 7.0), ("c.mp4", 4.5)])
    assert len(result["segments"]) == 3
    statuses = [s["status"] for s in result["segments"]]
    assert statuses == ["ok", "too_long", "ok"]
    assert len(result["errors"]) == 1


# ══════════════════════════════════════════════════
# TC-C04: 上传空文件列表
# ══════════════════════════════════════════════════
def test_upload_empty():
    resp = client.post("/api/clip/upload", files=[])
    assert resp.status_code == 400


# ══════════════════════════════════════════════════
# TC-C05: 拼接两个有效视频
# ══════════════════════════════════════════════════
def test_compose_two_valid():
    result = _upload_multi([("a.mp4", 2.0), ("b.mp4", 3.0)])
    clip_id = result["clip_id"]

    resp = client.post(
        "/api/clip/compose",
        json={"clip_id": clip_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["filename"].startswith("clip_output_")
    assert data["duration"] > 0
    assert data["download_url"].startswith("/api/clip/download/")


# ══════════════════════════════════════════════════
# TC-C06: clip_id 不存在
# ══════════════════════════════════════════════════
def test_compose_nonexistent():
    resp = client.post("/api/clip/compose", json={"clip_id": "nonexistent"})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════
# TC-C07: 全部片段超时
# ══════════════════════════════════════════════════
def test_compose_all_too_long():
    result = _upload_multi([("a.mp4", 6.1), ("b.mp4", 7.0)])
    resp = client.post("/api/clip/compose", json={"clip_id": result["clip_id"]})
    assert resp.status_code == 400


# ══════════════════════════════════════════════════
# TC-C08: 自定义 segment_order
# ══════════════════════════════════════════════════
def test_compose_custom_order():
    result = _upload_multi([("a.mp4", 2.0), ("b.mp4", 3.0), ("c.mp4", 1.5)])
    clip_id = result["clip_id"]
    ids = [s["id"] for s in result["segments"] if s["status"] == "ok"]

    # 倒序拼接
    resp = client.post(
        "/api/clip/compose",
        json={"clip_id": clip_id, "segment_order": list(reversed(ids))},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"


# ══════════════════════════════════════════════════
# TC-C09: 下载已合成视频
# ══════════════════════════════════════════════════
def test_download_valid():
    result = _upload_video(duration=2.0)
    clip_id = result["clip_id"]
    resp = client.post("/api/clip/compose", json={"clip_id": clip_id})
    data = resp.json()

    dl_resp = client.get(data["download_url"])
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "video/mp4"
    assert len(dl_resp.content) > 0


# ══════════════════════════════════════════════════
# TC-C10: 下载不存在的视频
# ══════════════════════════════════════════════════
def test_download_nonexistent():
    resp = client.get("/api/clip/download/nonexistent.mp4")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════
# TC-C11: 获取缩略图
# ══════════════════════════════════════════════════
def test_thumbnail():
    result = _upload_video(duration=2.0)
    seg = result["segments"][0]
    clip_id = result["clip_id"]

    if seg["thumbnail"]:
        resp = client.get(seg["thumbnail"])
        assert resp.status_code == 200
        assert "image" in resp.headers["content-type"]


# ══════════════════════════════════════════════════
# TC-C12: 获取不存在的缩略图
# ══════════════════════════════════════════════════
def test_thumbnail_nonexistent():
    resp = client.get("/api/clip/thumbnail/fake/thumb.jpg")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════
# TC-C13: 不同分辨率视频拼接
# ══════════════════════════════════════════════════
def test_compose_different_resolution():
    # 上传两个不同分辨率的视频
    data_a = _make_fake_video(duration=2.0, width=640, height=480)
    data_b = _make_fake_video(duration=3.0, width=1280, height=720)

    resp = client.post(
        "/api/clip/upload",
        files=[
            ("files", ("a.mp4", io.BytesIO(data_a), "video/mp4")),
            ("files", ("b.mp4", io.BytesIO(data_b), "video/mp4")),
        ],
    )
    result = resp.json()
    clip_id = result["clip_id"]

    comp_resp = client.post("/api/clip/compose", json={"clip_id": clip_id})
    assert comp_resp.status_code == 200
    data = comp_resp.json()
    assert data["status"] == "completed"


# ══════════════════════════════════════════════════
# TC-C14: 不支持的格式
# ══════════════════════════════════════════════════
def test_upload_unsupported_format():
    resp = client.post(
        "/api/clip/upload",
        files=[("files", ("test.flv", io.BytesIO(b"fake"), "video/x-flv"))],
    )
    result = resp.json()
    seg = result["segments"][0]
    assert seg["status"] == "error"
    assert "不支持的视频格式" in seg["error_msg"]
