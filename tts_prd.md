---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f4ff5be3e1f50ff475cd88e8c986c75f_027ed3407ff311f18018525400826444
    ReservedCode1: IyhmVsFfCvfoGDlHXJa9Uyrm1XMBvK6aAzglHs+AzE4PWDYmCJQ5kIvXpjDvY9vgyVm9G6FWIGpMj5zlHu1hkj/u82XPZzI+5XU4kVvlsKS6PxmpI663Ox7rCicGOuUrQ2kCBqBc3fA+hAC/Je9pYL9wauwzsDUbk+y/tOEIBGNQgH2bFilaGU/czUk=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f4ff5be3e1f50ff475cd88e8c986c75f_027ed3407ff311f18018525400826444
    ReservedCode2: IyhmVsFfCvfoGDlHXJa9Uyrm1XMBvK6aAzglHs+AzE4PWDYmCJQ5kIvXpjDvY9vgyVm9G6FWIGpMj5zlHu1hkj/u82XPZzI+5XU4kVvlsKS6PxmpI663Ox7rCicGOuUrQ2kCBqBc3fA+hAC/Je9pYL9wauwzsDUbk+y/tOEIBGNQgH2bFilaGU/czUk=
---



# PRD：TTS 语音旁白功能

> 项目：video_maker_app  
> 版本：v2.0  
> 状态：草稿，待评审  
> 日期：2026-07-15

---

## 1. 功能概述

为图片故事视频生成器增加 **TTS 文字转语音** 功能。用户在编辑图片段时，将已有的旁白文字通过 TTS 引擎自动转化为语音，分段绑定到对应图片上。语音长度可反向决定该图片段的展示时长。语音与背景音乐共存时，用户可独立调整两者的音量比例。

## 2. 用户故事

- 作为内容创作者，我希望把写好的旁白文字直接转成语音，避免自己录音或找配音。
- 作为用户，我希望每段语音自动匹配到对应的图片上，语音播完图片继续展示，不会突兀截断。
- 作为用户，我希望在合成视频前能逐段试听语音效果，满意后再合成。
- 作为用户，我希望语音和背景音乐的音量可以分别控制。

## 3. 功能需求

### 3.1 TTS 引擎选型

选用 **edge-tts**（Python 库），理由：

| 维度 | 说明 |
|------|------|
| 费用 | 完全免费，调用微软公有语音接口，无需 API Key |
| 硬件 | CPU 即可，无 GPU 要求 |
| 质量 | 微软神经网络语音，中文音色丰富 |
| 依赖 | `pip install edge-tts`，纯 Python，与现有技术栈一致 |
| 风险 | 需联网；微软接口若变更需跟进适配，属于低概率风险 |

### 3.2 语音风格

提供 3 种预设风格，对应 edge-tts 的 ShortName：

| 风格 | 描述 | edge-tts ShortName | 备注 |
|------|------|---------------------|------|
| 温柔女声 | 温柔亲切的中文女声 | `zh-CN-XiaoxiaoNeural` | 晓晓，偏温柔自然 |
| TVB 风格 | 粤语韵味的中文女声 | `zh-CN-XiaoyiNeural` | 晓依，声音偏成熟 |
| 邵氏风格 | 低沉富有磁性的男声 | `zh-CN-YunxiNeural` | 云希，叙事感强 |

> 注：edge-tts 的"粤语"相关音色（如 `zh-HK`）会带有粤语口音，但旁白文字为简体中文时，优先使用 `zh-CN` 系列。实际测试后若不满意再微调 ShortName。

### 3.3 分段绑定与时长策略

- **输入源**：复用现有图片段的"旁白文字"字段。每段旁白文字对应生成一个音频文件。
- **分段绑定**：音频与图片段一对一绑定。
- **时长策略**：
  - 语音时长 ≤ 图片段原定时长：语音播完后图片继续展示至原定时长结束，期间背景音乐持续播放。
  - 语音时长 > 图片段原定时长：**自动延长该图片段时长至语音结束**，确保语音完整播放。
  - 注意：不存在静音情况——语音结束后背景音乐仍在播，直至该图片段结束。

### 3.4 混音策略

- **音量控制**：语音音量和背景音乐音量分别独立设置。
- **配置方式**：提供两种输入模式，用户可切换：
  - 绝对值模式：语音 80%、背景音乐 60%（各自相对于原始音量的百分比）
  - 相对比例模式：语音:背景 = 4:3（系统自动换算为百分比）
- **共存逻辑**：两者同时播放，不做自动避让（ducking），用户通过滑块自行平衡。

### 3.5 试听与生成

- **逐段试听**：生成单段语音后，前端提供播放按钮，用户可试听该段效果。
- **一键全部生成**：提供"全部生成语音"按钮，批量生成所有段的 TTS 音频。
- **重新生成**：单段语音不满意时，可切换风格后重新生成该段。
- **合成最终视频**：所有语音生成完毕后，进入最终合成（语音 + 背景音乐 + 图片）。

## 4. 技术方案

### 4.1 后端改动（video_maker_app.py）

#### 4.1.1 新增依赖

```
edge-tts
```

#### 4.1.2 新增 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/tts/generate` | 为单段旁白生成语音 |
| POST | `/api/tts/generate-all` | 批量生成所有段的语音 |
| GET | `/api/tts/audio/{segment_id}` | 返回已生成的语音文件供试听 |
| DELETE | `/api/tts/audio/{segment_id}` | 删除某段语音（重新生成前清理） |

#### 4.1.3 `/api/generate` 扩展

新增参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tts_enabled` | bool | false | 是否启用 TTS 语音 |
| `tts_style` | string | `zh-CN-XiaoxiaoNeural` | TTS 音色 ShortName |
| `voice_volume` | float | 0.8 | 语音音量（0.0~2.0） |
| `bgm_volume` | float | 0.6 | 背景音乐音量（0.0~2.0） |

#### 4.1.4 核心函数

- `_generate_tts_audio(text, style, output_path)` — 调用 edge-tts 生成语音文件
- `_compose_video` 扩展 — 在图片段合成时叠加对应语音轨

### 4.2 前端改动

#### 4.2.1 UI 组件

- **语音风格选择器**：下拉菜单，3 个预设风格 + 试听样本（可选）
- **逐段语音操作区**：每张图片的编辑区域增加：
  - 「生成语音」按钮
  - 语音状态指示（未生成 / 生成中 / 已完成）
  - 试听播放器
  - 「重新生成」按钮
- **音量配置区**：
  - 语音音量滑块（0-200%）
  - 背景音乐音量滑块（0-200%）
  - 绝对值/相对比例切换开关
- **全局操作**：「全部生成语音」按钮

#### 4.2.2 JS 函数

- `generateTTS(segmentId)` — 调用 `/api/tts/generate`
- `generateAllTTS()` — 调用 `/api/tts/generate-all`
- `previewTTS(segmentId)` — 试听单段语音
- `updateVoiceVolume()` / `updateBGMVolume()` — 音量调整

### 4.3 数据流

```
用户输入旁白文字
    → 选择 TTS 风格
    → 点击「生成语音」
    → 后端 edge-tts 合成 → 保存为 .mp3（temp 目录）
    → 前端试听
    → 全部确认后点击「合成视频」
    → compose_video 叠加语音轨 + 背景音乐 + 图片
    → 输出最终视频
```

## 5. 非功能需求

- **性能**：单段语音生成耗时约 1~3 秒（取决于文字长度和网络），批量生成需异步处理并提供进度反馈。
- **存储**：生成的 .mp3 音频存放于项目 `temp/tts/` 目录，视频合成结束后可选择清理。
- **容错**：网络异常时提示用户重试，不阻塞整体流程。
- **兼容**：`tts_enabled=false` 时完全走原有逻辑，不影响现有功能。

## 6. 待确认项

- [ ] 3 种风格的 edge-tts ShortName 需实际测试验证效果，若不满意再调整
- [ ] 批量生成语音时是否需要进度条（推荐：SSE 或轮询方式）
- [ ] 生成的临时 TTS 音频是否在视频合成成功后自动清理
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
