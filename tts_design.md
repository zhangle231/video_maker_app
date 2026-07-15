---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f4ff5be3e1f50ff475cd88e8c986c75f_1402c5847ff911f1b242525400e6dd8f
    ReservedCode1: TRPCwEq/XlwK7vBfPoiuWzAwgZVjucMehbx+7rLT9vMJ5XyHFUQQEwoeGQiSNtu/4uO8kvLH1uPU+A0Z5GDF6vNmzuY5weryUHHfNTER8pKG7TfxLSttVv8PWA3UbHY/uR1k7npW7d3SRH1vhp/P9evpvGHR+HbJFdu1JK91by85T177EtvZg7sWk1Q=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f4ff5be3e1f50ff475cd88e8c986c75f_1402c5847ff911f1b242525400e6dd8f
    ReservedCode2: TRPCwEq/XlwK7vBfPoiuWzAwgZVjucMehbx+7rLT9vMJ5XyHFUQQEwoeGQiSNtu/4uO8kvLH1uPU+A0Z5GDF6vNmzuY5weryUHHfNTER8pKG7TfxLSttVv8PWA3UbHY/uR1k7npW7d3SRH1vhp/P9evpvGHR+HbJFdu1JK91by85T177EtvZg7sWk1Q=
---

# 详细设计：TTS 语音旁白功能

> 项目：video_maker_app  
> 版本：v2.0  
> 状态：草稿，待评审  
> 日期：2026-07-15  
> 关联 PRD：tts_prd.md

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    前端 (SPA)                        │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │ 语音风格  │  │ 逐段 TTS │  │ 音量配置(语音/BGM) │ │
│  │ 选择器   │  │ 操作面板  │  │ 绝对值/比例切换    │ │
│  └──────────┘  └──────────┘  └───────────────────┘ │
│         │              │               │            │
└─────────┼──────────────┼───────────────┼────────────┘
          │              │               │
     ┌────▼──────────────▼───────────────▼────────────┐
     │               Flask 后端                        │
     │  ┌──────────────────────────────────────────┐  │
     │  │           TTS 模块 (新增)                 │  │
     │  │  - generate_tts_audio()                  │  │
     │  │  - edge-tts 调用封装                     │  │
     │  └──────────────────────────────────────────┘  │
     │  ┌──────────────────────────────────────────┐  │
     │  │           合成模块 (扩展)                 │  │
     │  │  - _compose_video() 叠加语音轨           │  │
     │  └──────────────────────────────────────────┘  │
     └───────────────────────────────────────────────┘
          │
     ┌────▼────────────┐
     │   edge-tts      │
     │  (微软云端 TTS)  │
     └─────────────────┘
```

## 2. 项目结构变更

```
video_maker_app/
├── video_maker_app.py          # 主程序（扩展）
├── music_manifest.json         # 音乐元数据（已有）
├── tts/                        # 【新增】TTS 音频存放目录
│   └── {segment_id}.mp3        # 逐段生成的语音文件
├── temp/tts/                   # 【新增】批量生成临时进度文件
│   └── progress.json
├── music/                       # 音乐素材（已有）
├── uploads/                     # 图片上传（已有）
└── videos/                      # 输出视频（已有）
```

## 3. 模块详细设计

### 3.1 TTS 引擎封装

**文件位置**：`video_maker_app.py` 内新增辅助函数

#### 3.1.1 `_generate_tts_audio(text, style, output_path)`

```python
def _generate_tts_audio(text: str, style: str, output_path: str) -> Tuple[bool, str]:
    """
    调用 edge-tts 生成语音文件
    
    Args:
        text: 待转换的旁白文字
        style: edge-tts ShortName，如 "zh-CN-XiaoxiaoNeural"
        output_path: 输出的 .mp3 文件绝对路径
    
    Returns:
        (success: bool, message: str)
    """
```

**流程**：
1. 校验 `text` 非空
2. 调用 `edge_tts.Communicate(text, voice=style)`
3. 使用 `save(output_path)` 写入文件
4. 捕获网络异常、超时异常，返回友好错误信息

**依赖安装**：
```bash
pip install edge-tts -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 3.1.2 TTS 音色映射

```python
TTS_VOICES = {
    "gentle_female": "zh-CN-XiaoxiaoNeural",  # 温柔女声
    "tvb_style":     "zh-CN-XiaoyiNeural",     # TVB 风格
    "shaw_style":    "zh-CN-YunxiNeural",      # 邵氏风格
}
```

前端传风格 key，后端映射为 ShortName。若需调优音色，仅改此映射即可。

### 3.2 API 详细设计

#### 3.2.1 `POST /api/tts/generate`

为单段旁白生成语音。

**请求**：
```json
{
    "segment_id": "seg_0",
    "text": "这是第一张图片的旁白文字",
    "style": "gentle_female"
}
```

**响应（成功）**：
```json
{
    "success": true,
    "segment_id": "seg_0",
    "audio_path": "/api/tts/audio/seg_0",
    "duration": 3.5
}
```

**响应（失败）**：
```json
{
    "success": false,
    "segment_id": "seg_0",
    "error": "TTS 网络请求超时，请重试"
}
```

**实现逻辑**：
1. 从请求体中提取 `segment_id`、`text`、`style`
2. 将 `style` 映射为 edge-tts ShortName
3. 目标文件路径：`tts/{segment_id}.mp3`
4. 调用 `_generate_tts_audio()`
5. 成功后返回音频 URL 和时长（用 moviepy 读取时长）

#### 3.2.2 `POST /api/tts/generate-all`

批量生成所有段的语音，异步执行。

**请求**：
```json
{
    "segments": [
        {"segment_id": "seg_0", "text": "旁白文字1"},
        {"segment_id": "seg_1", "text": "旁白文字2"}
    ],
    "style": "gentle_female"
}
```

**响应**：
```json
{
    "success": true,
    "task_id": "batch_20260715_103000",
    "total": 2
}
```

**实现逻辑**：
1. 生成 `task_id`
2. 在 `temp/tts/progress.json` 写入初始进度：
   ```json
   {
       "task_id": "batch_20260715_103000",
       "total": 2,
       "completed": 0,
       "current": null,
       "status": "running",
       "segments": {
           "seg_0": {"status": "pending"},
           "seg_1": {"status": "pending"}
       }
   }
   ```
3. 使用 `threading.Thread` 启动后台任务，逐段生成
4. 每完成一段，更新 `progress.json`
5. 全部完成后，`status` 设为 `"done"`；若任一段失败，`status` 设为 `"partial"`

#### 3.2.3 `GET /api/tts/progress`

轮询批量生成进度。

**响应（进行中）**：
```json
{
    "task_id": "batch_20260715_103000",
    "total": 2,
    "completed": 1,
    "current": "seg_1",
    "status": "running",
    "segments": {
        "seg_0": {"status": "done", "duration": 3.5},
        "seg_1": {"status": "running"}
    }
}
```

**响应（完成）**：
```json
{
    "task_id": "batch_20260715_103000",
    "total": 2,
    "completed": 2,
    "current": null,
    "status": "done",
    "segments": {
        "seg_0": {"status": "done", "duration": 3.5},
        "seg_1": {"status": "done", "duration": 5.2}
    }
}
```

**轮询策略**：前端每 2 秒轮询一次，直到 `status` 为 `done` 或 `partial`。

#### 3.2.4 `GET /api/tts/audio/<segment_id>`

返回已生成的语音文件供前端试听。

**实现**：使用 Flask 的 `send_file()` 返回 `tts/{segment_id}.mp3`，Content-Type 为 `audio/mpeg`。

#### 3.2.5 `DELETE /api/tts/audio/<segment_id>`

删除某段语音文件。在用户切换风格后重新生成前调用。

**实现**：删除 `tts/{segment_id}.mp3`，文件不存在时返回成功（幂等）。

### 3.3 合成模块扩展

#### 3.3.1 `_compose_video` 签名变更

```python
def _compose_video(
    image_paths: List[str],
    subtitles: List[str],
    durations: List[float],
    output_path: str,
    music_track: Optional[str] = None,      # 已有
    music_volume: float = 0.6,               # 已有
    music_fade_out: float = 2.0,             # 已有
    tts_enabled: bool = False,               # 【新增】
    tts_style: str = "zh-CN-XiaoxiaoNeural", # 【新增】
    voice_volume: float = 0.8,               # 【新增】
    bgm_volume: float = 0.6,                 # 【新增】
):
```

#### 3.3.2 合成流程

```
对每个图片段 i：
    1. 创建图片 clip，时长 = durations[i]
    2. 若 tts_enabled 且有 tts/{segment_i}.mp3：
       a. 读取语音文件 → AudioFileClip
       b. 语音时长 > 图片时长 → 延长图片时长至语音时长
       c. 语音时长 ≤ 图片时长 → 语音播完图片继续展示
       d. 语音音量 = voice_volume
    3. 若有背景音乐：
       a. 音乐 clip，时长 = 当前段调整后的时长
       b. 音乐音量 = bgm_volume
       c. 音乐 fade_out = music_fade_out
    4. 音频叠加：
       - 若同时有语音和 BGM → CompositeAudioClip([语音, BGM])
       - 若仅有语音 → 语音 clip
       - 若仅有 BGM → BGM clip
    5. 图片 clip.set_audio(合成音频)
    6. 追加到 clips 列表
    7. 若有字幕，叠加字幕
最终：concatenate_videoclips(clips) → 写入 output_path
```

### 3.4 `/api/generate` 扩展

在现有请求参数基础上，新增：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tts_enabled` | bool | false | 是否启用 TTS 语音 |
| `tts_style` | string | `gentle_female` | TTS 风格 key |
| `voice_volume` | float | 0.8 | 语音音量（0.0~2.0） |
| `bgm_volume` | float | 0.6 | 背景音乐音量（0.0~2.0） |

`tts_enabled=false` 时，其余 TTS 参数忽略，完全走原有逻辑。

## 4. 前端详细设计

### 4.1 组件结构

```
┌─ 音乐选择面板（已有） ─────────────────────┐
├─ TTS 语音面板（新增） ─────────────────────┤
│  ┌──────────────────────────────────────┐  │
│  │ ☑ 启用 TTS 语音                      │  │
│  │                                      │  │
│  │ 语音风格：[温柔女声 ▾]               │  │
│  │                                      │  │
│  │ [全部生成语音]  (进度: 2/3 已完成)   │  │
│  └──────────────────────────────────────┘  │
│  ┌─ 逐段操作 ──────────────────────────┐  │
│  │ 图片1: "这是第一张图片的旁白..."     │  │
│  │ [生成语音] [▶ 试听 3.5s] [重新生成] │  │
│  │                                      │  │
│  │ 图片2: "第二张的介绍文字..."         │  │
│  │ [生成语音]  (未生成)                 │  │
│  └──────────────────────────────────────┘  │
│                                          │
│  语音音量：  [========|====] 80%         │
│  背景音乐：  [=====|=======] 60%         │
│  ○ 绝对值  ● 相对比例 (4:3)             │
└──────────────────────────────────────────┘
```

### 4.2 交互流程

#### 4.2.1 逐段生成

```
用户点击某段的 [生成语音]
  → 按钮变为 "生成中..."
  → POST /api/tts/generate {segment_id, text, style}
  → 成功后：显示时长、[▶ 试听] 按钮可用
  → 失败：显示错误提示，按钮恢复为 [生成语音]
```

#### 4.2.2 批量生成

```
用户点击 [全部生成语音]
  → 按钮变为 "生成中..."
  → POST /api/tts/generate-all {segments, style}
  → 启动轮询：每 2s GET /api/tts/progress
  → 更新进度条 "2/5 已完成"
  → 全部完成：每段更新为 [▶ 试听]
  → 若有失败：标记失败的段，按钮恢复为 [重新生成]
```

#### 4.2.3 重新生成

```
用户切换风格后，某段点击 [重新生成]
  → DELETE /api/tts/audio/{segment_id}
  → POST /api/tts/generate {segment_id, text, new_style}
```

### 4.3 音量配置交互

- **绝对值模式**：两个独立滑块，各 0-200%
- **相对比例模式**：一个比例选择器（如 4:3、2:1、1:1），系统自动换算：
  ```
  voice_volume = 比例_a / (比例_a + 比例_b) * 1.4
  bgm_volume   = 比例_b / (比例_a + 比例_b) * 1.4
  ```
  （1.4 系数使总和约 140%，避免音量过低）

### 4.4 JS 函数清单

| 函数 | 说明 |
|------|------|
| `generateTTS(segmentId)` | 调用 `/api/tts/generate`，更新该段 UI |
| `generateAllTTS()` | 调用 `/api/tts/generate-all`，启动轮询 |
| `startProgressPolling(taskId)` | 每 2s 调用 `pollTTSProgress()` |
| `pollTTSProgress()` | GET `/api/tts/progress`，更新进度条和各段状态 |
| `previewTTS(segmentId)` | 创建 `<audio>` 元素播放 `/api/tts/audio/{id}` |
| `regenerateTTS(segmentId)` | DELETE + POST 重新生成 |
| `updateVoiceVolume(val)` | 更新语音音量 |
| `updateBGMVolume(val)` | 更新 BGM 音量 |
| `toggleVolumeMode()` | 切换绝对值/相对比例模式 |

## 5. 错误处理策略

| 场景 | 处理 |
|------|------|
| edge-tts 网络超时 | 返回错误提示"网络超时，请检查网络后重试"，不阻塞其他段 |
| 文字为空 | 拒绝生成，提示"旁白文字不能为空" |
| 音频文件不存在 | `/api/tts/audio/` 返回 404，前端隐藏试听按钮 |
| 批量生成中某段失败 | 标记该段 `status: "failed"`，继续处理后续段，最终 `status: "partial"` |
| 合成时语音文件缺失 | 静默降级，跳过该段语音，图片段使用原始时长，BGM 正常播放 |
| Python 环境缺少 edge-tts | 后端启动时检测，若缺少则在控制台提示安装命令 |

## 6. 待确认项

- [ ] 3 种风格的 edge-tts ShortName 需实际测试验证效果，若不满意再调整
*（内容由AI生成，仅供参考）*
