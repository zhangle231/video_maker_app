"""
一键运行全部自动化测试
"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("video_maker_app 自动化测试")
print("=" * 60)

# 1. TTS API 测试
print("\n[1/3] 运行 TTS API 测试...")
result_tts = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_tts_api.py", "-v", "--tb=short"],
    capture_output=False
)

# 2. 短视频拼接 API 测试
print("\n[2/3] 运行短视频拼接 API 测试...")
result_clip = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_clip_api.py", "-v", "--tb=short"],
    capture_output=False
)

# 3. UI 测试（需要服务运行）
print("\n[3/3] 运行 UI 测试...")
print("(确保 video_maker_app.py 已启动)")
result_ui = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_tts_ui.py", "-v", "--tb=short"],
    capture_output=False
)

print("\n" + "=" * 60)
print("全部测试完成")
print("=" * 60)
