---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f4ff5be3e1f50ff475cd88e8c986c75f_6524843180c311f1a446525400e6dd8f
    ReservedCode1: UnDKrHyVlule2DGehebRl6d+xatTbm1fKuy/lQvaQW785JPbd6Q61T+k2506hpTXzYoKR8n3FAt9MKbaH+2TM0auo7U+B5KGcaUz4Cx4d4NzIwYl9hjBNq4crkLzOxgz7uwC9Q0QVNu+wJg7RC74da3hMvhWrJ2hhZ/LtSGrXtdCnbVAWv13v3Tfj20=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f4ff5be3e1f50ff475cd88e8c986c75f_6524843180c311f1a446525400e6dd8f
    ReservedCode2: UnDKrHyVlule2DGehebRl6d+xatTbm1fKuy/lQvaQW785JPbd6Q61T+k2506hpTXzYoKR8n3FAt9MKbaH+2TM0auo7U+B5KGcaUz4Cx4d4NzIwYl9hjBNq4crkLzOxgz7uwC9Q0QVNu+wJg7RC74da3hMvhWrJ2hhZ/LtSGrXtdCnbVAWv13v3Tfj20=
---

# PROJECT_SUMMARY — video_maker_app

> 生成日期：2026-07-16  
> 用途：供 AI Agent 快速了解项目全貌，覆盖背景、技术栈、功能、API、设计决策与已知限制。

---

## 1. 项目概述

**图片故事视频生成器** — 基于 Web 的工具，将多张图片 + 对应旁白文字合成为带字幕、语音旁白和背景音乐的 MP4 视频。核心价值在于：创作者只需准备图片和文字，其余（字幕排版、TTS 配音、BGM 混音、视频编码）全部自动化。

---

## 2. 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| Web 框架 | FastAPI + uvicorn | HTTP API 服务 + 内嵌 HTML 前端（SPA） |
| 视频合成 | moviepy (ImageClip / AudioFileClip / CompositeAudioClip / concatenate_videoclips) | 图片→视频帧、字幕叠加、音频轨道合成、编码输出 |
| TTS 引擎 | edge-tts | 调用微软免费云端神经网络语音接口，生成 .mp3 旁白 |
| 图像处理 | Pillow (PIL) | 图片尺寸适配、字幕渲染（含中文换行与字体加载） |
| 测试 | pytest + (playwright 可选) | API 自动化测试 / UI 自动化测试 |
| 运行环境 | Python 3.10+ / Windows 11 | 主开发与部署环境 |

核心依赖安装命令：

```bash
pip install fastapi uvicorn moviepy Pillow edge-tts
```

---

## 3. 功能清单

### 3.1 已完成功能

| 功能 | 说明 |
|------|------|
| **图片上传** | 支持拖拽 / 点击上传多张图片，自动生成缩略图预览 |
| **配置加载** | 支持加载外部 `prompts.json` 配置文件，按风格分组（set）批量导入图片与字幕 |
| **本地图片引用** | 可直接引用本地图片路径（不复制），通过 `/api/file-image` 服务 |
| **目录扫描** | `POST /api/scan-dir` 扫描指定目录，返回所有图片文件列表 |
| **字幕叠加** | 三种模式：半透明黑底 / 无背景 / 纯黑底；支持中文自动换行 |
| **布局模式** | `small`（小缩略图）/ `medium`（中缩略图）/ `large`（上下结构：图片在上、字幕区在下） |
| **过渡效果** | 片段间支持 FadeIn 过渡，时长可调 |
| **视频合成** | `_compose_video()` 将多张图片拼接为 MP4，支持自定义 FPS |
| **TTS 语音** | 基于 edge-tts 的三种中文音色，单段生成 + 批量生成 |
| **TTS 批量进度** | `POST /api/tts/generate-all` 异步生成 + `GET /api/tts/progress` 轮询进度 |
| **TTS 试听** | 前端支持逐段试听已生成的语音 |
| **BGM 混音** | 10 首预置背景音乐（5 类风格），支持循环匹配视频时长、独立音量控制 |
| **音量独立控制** | 语音音量和 BGM 音量分别可调（0~200%），通过 `CompositeAudioClip` 混音 |
| **时长自动延长** | TTS 语音时长超过图片预设时长时，自动延长该段至语音结束 |
| **配置持久化** | `app_config.json` 记住上次使用的 prompts.json 路径和图片根目录 |
| **自动化测试** | `tests/` 目录包含 30 个 TTS 测试用例（API + UI），pytest 一键运行 |

### 3.2 待完成 / 设计中有但未实现

| 功能 | 状态 |
|------|------|
| BGM 音乐选择器前端 UI（下拉 + 试听 + 标签筛选） | `music_design.md` 已设计，前端未实现，当前 `/api/generate` 的 `music_track` 参数虽定义但未暴露到 UI |
| BGM 结尾淡出 | `music_design.md` 已设计，当前实现为直接 `loop()` + `subclipped()`，无 fade-out |
| 音量绝对值/相对比例模式切换 | `tts_prd.md` 已设计，当前仅实现绝对值模式 |

---

## 4. 项目结构

```
video_maker_app/
├── video_maker_app.py          # 主程序（FastAPI 后端 + 内嵌 HTML 前端，约 1480 行）
├── music_manifest.json         # BGM 曲目索引（10 首，5 类风格，含标签/时长/BPM/授权）
├── app_config.json.example     # 配置文件示例
├── README.md                   # 项目说明（简要版）
├── music_design.md             # 背景音乐功能详细方案设计
├── tts_prd.md                  # TTS 语音功能 PRD
├── tts_design.md               # TTS 语音功能详细设计
├── tts_test_plan.md            # TTS 测试方案（30 个测试用例）
├── .gitignore                  # 忽略 app_config.json / uploads/ / videos/ / tts/ / temp/ / __pycache__/
├── music/                      # BGM 素材（按风格分子目录）
│   ├── warm/                   #   温馨治愈
│   ├── epic/                   #   激昂史诗
│   ├── lively/                 #   轻快活泼
│   ├── calm/                   #   静谧舒缓
│   └── tech/                   #   科技现代
├── tts/                        # TTS 生成的语音文件（{segment_id}.mp3），不自动清理
├── temp/tts/                   # 批量 TTS 进度临时文件
├── uploads/                    # 用户上传的图片（按 task_id 分子目录）
├── videos/                     # 输出视频产物
└── tests/                      # 自动化测试
    ├── conftest.py             #   pytest 配置
    ├── run_all.py              #   一键运行全部测试脚本
    ├── test_tts_api.py         #   TTS API 测试（TC-01 ~ TC-25）
    ├── test_tts_ui.py          #   TTS 前端 UI 测试（TC-26 ~ TC-30）
    └── README.md               #   测试说明
```

---

## 5. API 端点总览

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/` | 返回完整 HTML 前端页面 |
| `POST` | `/api/generate` | 接收图片+文本+参数，合成 MP4 视频 |
| `GET` | `/api/download/{filename}` | 下载已生成的视频文件 |
| `POST` | `/api/load-config` | 加载 `prompts.json` 配置文件并扫描匹配图片 |
| `POST` | `/api/load-config-content` | 与上同，但直接接收 JSON 内容而非文件路径 |
| `POST` | `/api/scan-dir` | 扫描目录返回图片文件列表 |
| `GET` | `/api/file-image` | 返回本地图片文件（用于前端缩略图） |
| `GET` | `/api/config` | 读取 `app_config.json` |
| `PUT` | `/api/config` | 更新 `app_config.json`（增量合并） |
| `POST` | `/api/tts/generate` | 为单段旁白生成 TTS 语音 |
| `POST` | `/api/tts/generate-all` | 批量生成全部段 TTS 语音（异步 + 进度可查） |
| `GET` | `/api/tts/progress` | 轮询批量 TTS 生成进度 |
| `GET` | `/api/tts/audio/{segment_id}` | 返回已生成的语音 .mp3 供试听 |
| `DELETE` | `/api/tts/audio/{segment_id}` | 删除某段语音（重新生成前清理） |

---

## 6. TTS 音色配置

| 前端 key | edge-tts ShortName | 描述 |
|----------|---------------------|------|
| `gentle_female` | `zh-CN-XiaoxiaoNeural` | 温柔女声（晓晓） |
| `tvb_style` | `zh-CN-XiaoyiNeural` | TVB 风格女声（晓依） |
| `shaw_style` | `zh-CN-YunxiNeural` | 邵氏风格男声（云希） |

音色映射定义在 `video_maker_app.py` 顶部的 `TTS_VOICES` 字典中，修改该映射即可切换音色。

---

## 7. 关键设计决策（对后续开发重要）

1. **`tts/` 目录不自动清理**：生成的 TTS 语音文件不会在视频合成后自动删除。设计理由：允许用户反复合成同一批素材而无需重新生成 TTS。若需清理，通过 `DELETE /api/tts/audio/{segment_id}` 手动删除。

2. **视频合成不支持动态延长已渲染 clip**：moviepy 的 `ImageClip` 在创建后 duration 即固定。若 TTS 语音长于图片预设时长，必须在调用 `_compose_video()` **之前**预先延长 `durations` 数组。当前实现在 `/api/generate` 中通过预读取 TTS 文件时长来完成此操作。

3. **BGM 循环混音**：背景音乐使用 `loop(duration=video_duration)` 循环填充整个视频时长；若 BGM 长于视频则 `subclipped(0, video_duration)` 截取。当前无结尾淡出（fade-out 已在 `music_design.md` 设计中但未实现）。

4. **无音频"闪避" (ducking)**：语音和 BGM 同时播放时不做自动音量避让，用户通过两个独立滑块自行平衡。

5. **前端为纯静态内嵌 SPA**：HTML/CSS/JS 全部写在 `video_maker_app.py` 的 `HTML_TEMPLATE` 字符串中，无需额外前端构建工具。状态管理全部在浏览器内存中（`slides`、`ttsSegments` 等变量）。

6. **`music_track` 参数已定义但前端未暴露**：`/api/generate` 接收 `music_track` 参数，但当前前端 UI 未实现音乐选择器，BGM 功能仅在后端就绪。实际使用时需通过修改请求或 curl 调用。

7. **`temp/tts/` 目录**：设计文档中预留给批量 TTS 进度文件，但当前实际实现将进度数据存储在内存 `_batch_progress` 字典中，未落地磁盘。目录保留备用。

---

## 8. 已知限制 / 下一步方向

### 8.1 已知限制

- **CPU 编码**：video 使用 libx264 软件编码，无 GPU 加速，长视频合成耗时较长。
- **edge-tts 需联网**：TTS 功能依赖微软云端接口，离线环境不可用。
- **仅支持中文 TTS**：三种音色均为 `zh-CN` 系列，英文旁白需额外配置音色映射。
- **无音乐前端选择器**：BGM 选择需通过 API 直接传参，无 GUI。
- **moviepy 版本兼容**：项目使用 moviepy v2.x 的新 API（`.with_effects()` / `.subclipped()` / `concatenate_videoclips` 等），与 moviepy v1.x 不兼容。
- **无并发保护**：`_batch_progress` 虽有线程锁保护读写，但同一 batch_id 重复 POST 会静默覆盖。

### 8.2 建议下一步

1. **实现 BGM 前端选择器**：按 `music_design.md` 设计，增加音乐列表下拉、试听、标签筛选和音量滑块。
2. **BGM 结尾淡出**：在 `_compose_video` 的 BGM 处理中添加 `afx.AudioFadeOut`。
3. **GPU 加速编码**：探索 moviepy 的 `ffmpeg_params` 传入 NVENC / AMF 参数。
4. **多语言 TTS**：扩展 `TTS_VOICES` 映射，支持英文 / 日文等音色。
5. **视频片段预览**：合成前允许预览单个图片片段（静态图 + 字幕 + 语音试听）。
6. **进度回调更细粒度**：视频合成阶段目前无实时进度，可考虑 moviepy 的 `progress_bar` 回调。

---

## 9. 启动方式

```bash
# 1. 安装依赖
pip install fastapi uvicorn moviepy Pillow edge-tts

# 2. 启动服务
cd d:\LEO\project\temp\video_maker_app
python video_maker_app.py

# 3. 浏览器访问
# http://127.0.0.1:8765
```

启动后控制台输出 `启动服务: http://127.0.0.1:8765`，服务运行在 `uvicorn`，日志级别为 `warning`。

**运行测试**（需安装 pytest）：

```bash
# API 测试（自动启动 test client，无需单独启动服务）
pytest tests/test_tts_api.py -v

# 全部测试
python tests/run_all.py
```
*（内容由AI生成，仅供参考）*
