"""
一键运行全部 TTS 自动化测试
"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("TTS 语音功能自动化测试")
print("=" * 60)

# 1. API 测试
print("\n[1/2] 运行 API 测试...")
result_api = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_tts_api.py", "-v", "--tb=short"],
    capture_output=False
)

# 2. UI 测试
print("\n[2/2] 运行 UI 测试...")
print("(确保 video_maker_app.py 已启动)")
result_ui = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_tts_ui.py", "-v", "--tb=short"],
    capture_output=False
)

print("\n" + "=" * 60)
print("全部测试完成")
print("=" * 60)
