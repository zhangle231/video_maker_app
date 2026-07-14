# 背景音乐功能方案设计

> **项目**: `video_maker_app` — 图片故事视频生成器  
> **日期**: 2026-07-14  
> **现状**: 基于 FastAPI + moviepy，视频合成时 `audio=False`，无音频轨道

---

## 1. 免费无版权音乐来源

### 1.1 推荐来源库（按优先级）

| 来源 | 授权模式 | 音质 | 风格丰富度 | 下载方式 | 备注 |
|------|----------|------|-----------|----------|------|
| **Pixabay Music** | CC0 / Pixabay License | 高（320kbps MP3） | ★★★★★ | 网页下载（无需登录） | 首推，量大质优，中文界面友好 |
| **Mixkit** | Mixkit License（免费商用） | 高 | ★★★★ | 网页下载（需邮箱） | 分类精细，适合视频配乐 |
| **YouTube Audio Library** | 免版税（部分需署名） | 高 | ★★★★★ | YouTube 创作者工作室内下载 | 需 Google 账号，曲库最大 |
| **Freesound** | CC0 / CC-BY | 中~高 | ★★★ | 网页下载（需注册） | 音效为主，也有少量音乐 |
| **Uppbeat** | 免费计划（需署名） | 高 | ★★★★ | 网页下载（需注册） | 独立音乐人作品，风格独特 |

### 1.2 推荐预置策略

建议项目预置 **10~15 首精选背景音乐**，覆盖常见视频场景，按风格分标签：

- **温馨/治愈**（旅行、日常、亲情）
- **激昂/史诗**（产品展示、宣传片、成果汇报）
- **轻快/活泼**（宠物、儿童、趣味内容）
- **静谧/舒缓**（自然风景、冥想、文艺）
- **科技/现代**（技术演示、商业、都市）

预置音乐随项目发布，来源优先 Pixabay Music（CC0，无需署名），用户亦可自行替换。

---

## 2. 技术选型方案

### 2.1 推荐方案：moviepy（与现有架构一致）

**理由**：

- 项目已使用 `moviepy` 进行视频合成，零额外依赖
- moviepy 底层基于 ffmpeg，音频处理能力完整
- `CompositeAudioClip` / `AudioFileClip` 直接支持音频合并、裁剪、淡入淡出、音量调节
- 保持代码风格一致，降低维护成本

### 2.2 核心 API 调用链

```
音频文件 (.mp3)
    → AudioFileClip 加载
    → afx.MultiplyVolume (音量调节)
    → afx.AudioFadeOut / AudioFadeIn (淡入淡出)
    → loop / set_duration (循环匹配视频时长)
    → CompositeAudioClip 混合
    → final.write_videofile(audio=True)
```

### 2.3 备选方案：ffmpeg 命令行

保留作为降级兜底，用于：
- 批量后处理已生成视频追加音频
- moviepy 无法处理的特殊音频格式
- 性能敏感的大文件场景（ffmpeg 原生更快）

---

## 3. 与现有项目架构的集成方式

### 3.1 项目结构变更

```
video_maker_app/
├── video_maker_app.py          # 主应用（修改）
├── app_config.json.example     # 配置示例（扩展）
├── README.md                   # 更新说明
├── music/                      # 🆕 音乐素材目录
│   ├── warm/                   # 温馨治愈
│   │   ├── acoustic-sunset.mp3
│   │   └── ...
│   ├── epic/                   # 激昂史诗
│   ├── lively/                 # 轻快活泼
│   ├── calm/                   # 静谧舒缓
│   └── tech/                   # 科技现代
├── music_manifest.json         # 🆕 音乐索引清单
└── uploads/                    # 不变
└── videos/                     # 不变
```

### 3.2 music_manifest.json 格式

```json
{
  "version": 1,
  "tracks": [
    {
      "id": "warm_01",
      "file": "music/warm/acoustic-sunset.mp3",
      "name": "Acoustic Sunset",
      "artist": "Pixabay",
      "tags": ["温馨", "治愈", "吉他", "旅行"],
      "duration": 180,
      "bpm": 80,
      "source": "Pixabay Music",
      "license": "CC0"
    }
  ]
}
```

### 3.3 现有代码改动点

| 位置 | 改动内容 |
|------|----------|
| `_compose_video()` | 新增 `music_id` / `music_volume` / `music_fade` 参数；音频加载与合成逻辑 |
| `/api/generate` | 接收前端传来的音乐参数 |
| `HTML_TEMPLATE` | UI 增加「背景音乐」配置区：音乐列表下拉 + 试听 + 音量滑块 |
| `/api/music/list` | 🆕 新增 API：返回可用音乐列表 |
| `/api/music/preview/{id}` | 🆕 新增 API：返回音乐片段供前端试听 |
| `app_config.json` | 扩展 `music_dir` 字段（可选，默认 `music/`） |

### 3.4 集成示意（`_compose_video` 改动核心逻辑）

```python
def _compose_video(
    image_paths, texts, durations, output_path,
    font_size=36, text_color="#ffffff", text_bg="semi",
    fade_duration=0.3, fps=24, layout_mode="medium",
    music_track=None,      # 🆕 dict: {"file": ..., "volume": 0.8, "fade_out": 2.0}
):
    # ... 现有图片处理逻辑不变 ...

    final = concatenate_videoclips(clips, method="compose")

    # ── 🆕 音乐合成 ──
    if music_track and music_track.get("file"):
        audio = AudioFileClip(music_track["file"])
        # 剪辑/循环匹配视频时长
        video_duration = final.duration
        if audio.duration < video_duration:
            audio = audio.loop(duration=video_duration)
        else:
            audio = audio.subclipped(0, video_duration)
        # 淡出
        fade_out = music_track.get("fade_out", 2.0)
        if fade_out > 0:
            audio = audio.with_effects([afx.AudioFadeOut(fade_out)])
        # 音量
        volume = music_track.get("volume", 0.8)
        if volume != 1.0:
            audio = audio.with_effects([afx.MultiplyVolume(volume)])
        final = final.with_audio(audio)

    final.write_videofile(output_path, fps=fps, codec="libx264",
                          audio=True, logger=None)
    final.close()
```

---

## 4. 音乐素材管理策略

### 4.1 本地缓存与目录结构

```
music/
├── warm/        # 温馨治愈
├── epic/        # 激昂史诗
├── lively/      # 轻快活泼
├── calm/        # 静谧舒缓
├── tech/        # 科技现代
└── custom/      # 🆕 用户自定义（不被版本控制覆盖）
```

- `music/custom/` 目录加入 `.gitignore`，用户自行放入的音乐不会被版本管理
- `music_manifest.json` 在应用启动时加载并缓存到内存
- 支持运行时扫描 `custom/` 目录，自动发现用户新增音乐文件

### 4.2 分类标签体系

每首音乐可打多个标签，按维度划分：

| 维度 | 标签示例 |
|------|----------|
| **情绪** | 温馨、激昂、轻快、舒缓、冷静、伤感、浪漫、紧张 |
| **场景** | 旅行、日常、产品、自然、宠物、运动、美食、婚礼 |
| **风格** | 吉他、钢琴、电子、管弦乐、民谣、爵士、Lo-fi、中国风 |
| **节奏** | 快节奏、中速、慢速 |

前端 UI 支持按标签筛选 + 关键词搜索。

### 4.3 音乐元数据自动提取

使用 Python 标准库 + `mutagen`（可选依赖）自动提取：
- **时长**: `AudioFileClip(file).duration`
- **格式**: 文件扩展名
- **大小**: `os.path.getsize()`
- **比特率**: mutagen 读取（可选）

`mutagen` 为可选依赖：安装时提供更丰富的元数据（BPM、艺术家、专辑），未安装则仅提取时长和文件信息。

### 4.4 试听片段生成

启动时自动为每首音乐生成 15 秒试听片段（缓存到 `music/.previews/`），避免前端试听时加载完整文件。片段仅在音乐文件更新时重新生成，通过文件修改时间判断。

---

## 5. 整体流程设计

### 5.1 用户操作流

```
用户打开页面
    │
    ├─ 加载音乐列表 → 显示音乐选择器
    │     ├─ 按标签/关键词筛选
    │     ├─ 点击试听（播放 15s 预览）
    │     └─ 选择音乐 / 无音乐
    │
    ├─ 调整音量滑块 (0% ~ 100%，默认 80%)
    │
    ├─ 上传图片 / 加载配置 → 编辑字幕（现有流程不变）
    │
    └─ 点击「生成视频」
          │
          ├─ 后端接收 music_id + volume + fade_out
          ├─ _compose_video 合成
          │     ├─ 图片 → ImageClip → 字幕叠加 → concatenate_videoclips
          │     └─ 音频 → AudioFileClip → 循环/裁剪 → 音量 → 淡出 → 合并
          └─ 输出 MP4（带音频轨道）
```

### 5.2 后端处理流

```
POST /api/generate
    │
    ├─ 1. 解析参数（图片、文本、时长、music_id、volume 等）
    ├─ 2. 从 music_manifest 查找 music_id → 获取文件路径
    ├─ 3. 校验音频文件存在
    ├─ 4. 构造 music_track dict → 传入 _compose_video
    └─ 5. 返回结果
```

### 5.3 异常处理

| 场景 | 处理策略 |
|------|----------|
| 音频文件缺失 | 跳过音乐，正常生成无音频视频，前端提示 |
| 音频格式不支持 | 尝试 ffmpeg 转码为 mp3 临时文件，失败则跳过低质音频 |
| 音频时长 < 视频 | `loop()` 循环填充 |
| 音频时长 > 视频 | `subclipped()` 截取前段 |
| 用户未选择音乐 | 走原有 `audio=False` 逻辑，保持向后兼容 |

---

## 6. 接口 / 函数设计草案

### 6.1 新增 API

#### `GET /api/music/list`

返回可用音乐列表。

**响应示例**:

```json
{
  "tracks": [
    {
      "id": "warm_01",
      "name": "Acoustic Sunset",
      "artist": "Pixabay",
      "tags": ["温馨", "治愈", "吉他"],
      "duration": 180,
      "duration_str": "3:00",
      "has_preview": true
    }
  ],
  "tags": ["温馨", "治愈", "吉他", "激昂", "史诗", ...]
}
```

#### `GET /api/music/preview/{track_id}`

返回 15 秒 MP3 试听片段（`audio/mpeg`），`Range` 请求支持。

#### `GET /api/music/custom-scan`

触发扫描 `music/custom/` 目录，返回新发现的音乐文件列表。返回结构与 `/api/music/list` 相同但仅包含 custom 目录中的曲目。

### 6.2 修改现有 API

#### `POST /api/generate` — 新增参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `music_id` | `str` | `""` | 音乐 ID（来自 manifest），空字符串表示无音乐 |
| `music_volume` | `float` | `0.8` | 音量系数 (0.0 ~ 1.0) |
| `music_fade_out` | `float` | `2.0` | 结尾淡出秒数（0 表示不淡出） |

### 6.3 新增模块函数

#### `load_music_manifest(manifest_path: Path) -> dict`

启动时加载 `music_manifest.json`，缓存到内存。同时扫描 `music/custom/` 目录自动发现用户自定义音乐。

```python
def load_music_manifest(manifest_path: Path, custom_dir: Path) -> dict:
    """加载音乐索引并合并 custom 目录扫描结果"""
```

#### `find_track_by_id(track_id: str, manifest: dict) -> dict | None`

根据 ID 查找音乐条目，若未找到返回 None。

#### `get_track_file_path(track: dict, base_dir: Path) -> Path`

返回音乐文件的绝对路径，并校验文件存在。

#### `generate_preview(audio_path: Path, preview_dir: Path, duration: float = 15.0)`

生成 MP3 试听片段，缓存到 `music/.previews/`。通过文件修改时间判断是否需要重新生成。

```python
def generate_preview(audio_path: Path, preview_dir: Path, duration: float = 15.0) -> Path:
    """用 moviepy 截取前 N 秒作为试听片段"""
```

#### `apply_audio_to_clip(video_clip, music_track: dict) -> VideoClip`

将音乐轨道应用到视频 clip，处理循环、音量、淡出。

```python
def apply_audio_to_clip(video_clip, music_track: dict) -> VideoClip:
    """
    输入: video_clip (已合成的视频片段)
    输出: 带音频轨道的视频片段
    
    内部处理:
    1. AudioFileClip 加载
    2. loop / subclip 匹配时长
    3. MultiplyVolume 音量调节
    4. AudioFadeOut 结尾淡出
    5. video_clip.with_audio()
    """
```

### 6.4 `_compose_video` 函数签名变更

```python
def _compose_video(
    image_paths: list,
    texts: list,
    durations: list,
    output_path: str,
    font_size: int = 36,
    text_color: str = "#ffffff",
    text_bg: str = "semi",
    fade_duration: float = 0.3,
    fps: int = 24,
    layout_mode: str = "medium",
    music_track: dict | None = None,   # 🆕
):
```

### 6.5 前端 UI 新增区域（HTML 模板改动）

在「全局设置」区域下方新增：

```html
<!-- 背景音乐 -->
<div class="global-settings">
    <h3>背景音乐</h3>
    <div>
        <label>选择音乐</label>
        <select id="musicSelect">
            <option value="">无音乐</option>
            <!-- 动态填充 -->
        </select>
    </div>
    <div>
        <label>音量</label>
        <input type="range" id="musicVolume" min="0" max="100" value="80">
        <span id="musicVolumeLabel">80%</span>
    </div>
    <div>
        <label>结尾淡出(秒)</label>
        <input type="number" id="musicFadeOut" value="2" min="0" max="10" step="0.5">
    </div>
    <div>
        <button class="btn btn-secondary" id="btnPreviewMusic" onclick="previewMusic()" disabled>试听</button>
    </div>
    <div style="margin-left:auto; display:none;" id="musicTags">
        <!-- 标签筛选 -->
    </div>
</div>
```

试听功能：点击试听按钮播放 15 秒片段（`<audio>` 元素），按钮变为"停止"。

---

## 7. 实施建议与注意事项

### 7.1 向后兼容

- 所有音乐参数均设置默认值（`music_id=""`, `volume=0.8`, `fade_out=2.0`）
- 若 `music_id` 为空字符串，完全走原有 `audio=False` 路径
- 音乐目录不存在时自动降级，不影响原有功能

### 7.2 依赖变更

无需新增任何依赖。现有 `moviepy` 已完整覆盖音频处理需求。可选依赖 `mutagen` 仅用于增强元数据提取。

### 7.3 文件大小控制

- 预置音乐使用中等码率（192kbps MP3），控制总体积在 30MB 以内
- 试听片段为 64kbps 低码率，15 秒约 120KB/首
- `music/.previews/` 和 `music/custom/` 加入 `.gitignore`

### 7.4 预置音乐清单（建议）

| ID | 文件名 | 风格 | 来源 | 时长 |
|----|--------|------|------|------|
| `warm_01` | acoustic-sunset.mp3 | 温馨/吉他 | Pixabay | ~3:00 |
| `warm_02` | hopeful-journey.mp3 | 温馨/钢琴 | Pixabay | ~2:30 |
| `epic_01` | epic-inspiration.mp3 | 激昂/管弦 | Pixabay | ~3:30 |
| `epic_02` | rising-up.mp3 | 激昂/电子 | Mixkit | ~2:45 |
| `lively_01` | happy-days.mp3 | 轻快/民谣 | Pixabay | ~2:15 |
| `lively_02` | upbeat-summer.mp3 | 活泼/流行 | Pixabay | ~3:00 |
| `calm_01` | peaceful-morning.mp3 | 静谧/钢琴 | Pixabay | ~3:45 |
| `calm_02` | soft-ambient.mp3 | 舒缓/电子 | Mixkit | ~3:00 |
| `tech_01` | digital-future.mp3 | 科技/电子 | Pixabay | ~2:40 |
| `tech_02` | corporate-light.mp3 | 现代/商业 | Mixkit | ~2:30 |

> 实际曲目以最终版权审查和用户偏好调整为准。
