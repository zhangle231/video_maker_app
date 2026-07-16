---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f4ff5be3e1f50ff475cd88e8c986c75f_427e508980c911f188a8525400826444
    ReservedCode1: fPmKBicnIe3xgRVOO5RJXyD/l3wxwVhTZTM4Nvv6Dbz5Er756OxadJTNCPj5eG2U3+vg5G7vleHue1+gtashS5gqy4T35VL4vqz26UgwfJy5eE5fOiYsai2Qi5QC0Iea0fCbbfDe2HOJFz6HeZ48ZHXWij8OacUL3anmmjNmiIe7SX/aHCJ+e1nh2AU=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f4ff5be3e1f50ff475cd88e8c986c75f_427e508980c911f188a8525400826444
    ReservedCode2: fPmKBicnIe3xgRVOO5RJXyD/l3wxwVhTZTM4Nvv6Dbz5Er756OxadJTNCPj5eG2U3+vg5G7vleHue1+gtashS5gqy4T35VL4vqz26UgwfJy5eE5fOiYsai2Qi5QC0Iea0fCbbfDe2HOJFz6HeZ48ZHXWij8OacUL3anmmjNmiIe7SX/aHCJ+e1nh2AU=
Status: 已评审通过
---

# Video Clip 拼接模块 详细设计

> 版本：v0.1  
> 日期：2026-07-16  
> 依赖 PRD：`video_clip_prd.md`

---

## 1. 设计目标

在现有 `video_maker_app.py` 中新增短视频拼接功能，作为独立标签页与图片故事模块并存。后端新增 4 个 API 端点，前端新增一个标签页 UI。

核心原则：**最小侵入** — 所有新增代码集中在文件末尾的独立区块，不修改现有图片模块的任何逻辑。

---

## 2. 架构概览

```
video_maker_app.py  (约 1480 行)
├── [现有] 图片故事模块
│   ├── 配置 / 常量 / TTS_VOICES / MUSIC_TRACKS ...
│   ├── /api/generate, /api/tts/*, /api/load-config ...
│   └── HTML_TEMPLATE (图片故事标签页)
│
└── [新增] 短视频拼接模块
    ├── 常量
    │   ├── MAX_CLIP_DURATION = 5.0 (秒)
    │   ├── CLIP_OUTPUT_DIR = "videos"
    │   └── CLIP_UPLOAD_DIR = "uploads/clips"
    ├── API 端点
    │   ├── POST /api/clip/upload
    │   ├── POST /api/clip/compose
    │   ├── GET  /api/clip/download/{filename}
    │   └── GET  /api/clip/thumbnail/{filename}
    └── HTML 新增：标签页 + CSS + JS
```

---

## 3. 数据结构

### 3.1 内存状态（`_clip_sessions` 字典）

```python
_clip_sessions: dict[str, dict] = {}
# Key = clip_id (uuid4)
# Value = {
#     "segments": [
#         {
#             "id": "seg_0",           # 片段 ID
#             "filename": "xxx.mp4",    # 原始文件名
#             "saved_path": "uploads/clips/<clip_id>/seg_0.mp4",  # 磁盘路径
#             "duration": 4.8,          # 时长（秒）
#             "width": 1920,            # 视频宽度
#             "height": 1080,           # 视频高度
#             "fps": 30.0,              # 帧率
#             "status": "ok" | "too_long" | "error",
#             "error_msg": "",          # 仅 status != "ok" 时
#         },
#         ...
#     ],
#     "segment_order": ["seg_0", "seg_1", ...],  # 用户排序后的顺序
#     "created_at": "2026-07-16T10:30:00",
# }
```

选择内存存储的理由：
- 与现有图片模块的 `slides` 状态管理方式一致（浏览器内存）
- 短视频拼接任务生命周期短（上传 → 排序 → 合成 → 下载），无需持久化
- 避免引入数据库依赖

### 3.2 文件存储约定

```
uploads/clips/<clip_id>/         # 每个 session 独立目录
├── seg_0.mp4                    # 统一重命名为 seg_{index}.mp4
├── seg_1.mp4
├── thumb_seg_0.jpg              # 缩略图
└── thumb_seg_1.jpg

videos/clip_output_<uuid>.mp4    # 输出视频
```

---

## 4. API 详细设计

### 4.1 POST /api/clip/upload

**功能**：接收多个视频文件上传，校验时长，生成缩略图。

**请求**：
```
Content-Type: multipart/form-data
files: List[UploadFile]  (字段名 "files")
```

**处理流程**：
```
1. 生成 clip_id = uuid4()
2. 创建 uploads/clips/<clip_id>/ 目录
3. 遍历 files:
   a. 保存到 uploads/clips/<clip_id>/seg_{index}.mp4 （保留原始扩展名）
   b. 使用 moviepy.VideoFileClip 读取元数据 (duration, size, fps)
   c. 校验 duration <= MAX_CLIP_DURATION (5.0)
      - 超过 → status="too_long", error_msg="视频时长 X.Xs，超过 5 秒限制"
      - 未超 → status="ok"
   d. 提取首帧缩略图：clip.get_frame(0) → PIL Image → save thumb_seg_{index}.jpg
   e. 记录 segment 信息到 _clip_sessions[clip_id]["segments"]
   f. 关闭 VideoFileClip 释放资源
4. 初始化 segment_order 为上传顺序
```

**响应**：
```json
{
  "clip_id": "abc123",
  "segments": [
    {
      "id": "seg_0",
      "filename": "beach.mp4",
      "duration": 4.2,
      "width": 1920,
      "height": 1080,
      "fps": 30.0,
      "thumbnail": "/api/clip/thumbnail/abc123/seg_0.jpg",
      "status": "ok",
      "error_msg": null
    },
    {
      "id": "seg_1",
      "filename": "sunset.mp4",
      "duration": 6.5,
      "width": 1280,
      "height": 720,
      "fps": 25.0,
      "thumbnail": "/api/clip/thumbnail/abc123/seg_1.jpg",
      "status": "too_long",
      "error_msg": "视频时长 6.5s，超过 5 秒限制"
    }
  ],
  "errors": [
    "sunset.mp4: 视频时长 6.5s，超过 5 秒限制"
  ]
}
```

**错误处理**：
- 文件格式不支持 → status="error"，提示"不支持的视频格式"
- moviepy 无法解析 → status="error"，提示"无法读取视频文件，请检查文件是否损坏"

---

### 4.2 POST /api/clip/compose

**功能**：按用户指定的顺序拼接视频片段。

**请求**：
```json
{
  "clip_id": "abc123",
  "segment_order": ["seg_1", "seg_0"]   // 可选，不传用上传顺序
}
```

**处理流程**：
```
1. 根据 clip_id 查找 _clip_sessions
2. 确定有效片段：过滤掉 status != "ok" 的 segment
3. 如果有效片段数 == 0 → 返回错误
4. 确定拼接顺序：
   - 若请求传了 segment_order，按 segment_order 排列，只取 status=="ok" 的
   - 没传则按 _clip_sessions[clip_id]["segment_order"] （默认上传顺序）
5. 加载 VideoFileClip 列表
6. 使用 concatenate_videoclips(clips, method="compose") 拼接
   - method="compose"：自动处理不同分辨率（统一到最大分辨率，黑边填充）
7. 输出参数：
   - 分辨率：使用第一个有效片段的分辨率（若不一致则 compose 自动统一）
   - FPS：使用第一个有效片段的 FPS
   - 编码：libx264, preset="medium", bitrate="5000k"
   - 音频编码：aac
8. 输出到 videos/clip_output_{uuid}.mp4
9. 更新 _clip_sessions[clip_id]["output"] 信息
10. 关闭所有 VideoFileClip 释放资源
```

**响应**：
```json
{
  "status": "completed",
  "filename": "clip_output_abc123.mp4",
  "duration": 12.6,
  "width": 1920,
  "height": 1080,
  "fps": 30.0,
  "download_url": "/api/clip/download/clip_output_abc123.mp4"
}
```

**异常处理**：
- clip_id 不存在 → 404
- 无有效片段 → 400 "没有有效的视频片段可供合成"
- 合成过程异常 → 500，返回错误信息

---

### 4.3 GET /api/clip/download/{filename}

**功能**：下载拼接后的视频。

```python
@app.get("/api/clip/download/{filename}")
async def clip_download(filename: str):
    file_path = os.path.join(CLIP_OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)
```

`FileResponse` 需从 `fastapi.responses` 导入（FastAPI 内置）。

---

### 4.4 GET /api/clip/thumbnail/{clip_id}/{filename}

**功能**：获取视频首帧缩略图。

```python
@app.get("/api/clip/thumbnail/{clip_id}/{filename}")
async def clip_thumbnail(clip_id: str, filename: str):
    thumb_path = os.path.join(CLIP_UPLOAD_DIR, clip_id, filename)
    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="缩略图不存在")
    return FileResponse(thumb_path, media_type="image/jpeg")
```

---

## 5. 前端 UI 设计

### 5.1 标签页切换

在现有 HTML 顶部导航区域新增标签：

```html
<div class="tab-bar">
    <button class="tab active" data-tab="story">📷 图片故事</button>
    <button class="tab" data-tab="clip">🎬 短视频拼接</button>
</div>
```

标签切换逻辑：
```javascript
// 点击标签：隐藏旧面板、显示新面板、切换 active 类
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // 切换 tab active
        // 隐藏/显示对应面板 (story-panel / clip-panel)
    });
});
```

### 5.2 短视频拼接面板结构

```
clip-panel
├── 上传区域 (drop-zone)
│   ├── 拖拽/点击上传
│   ├── 隐藏的 <input type="file" accept="video/*" multiple>
│   └── 上传中 loading 提示
│
├── 片段列表 (segment-list) — 空时显示占位提示
│   ├── 片段卡片 (可拖拽，HTML5 Drag & Drop API)
│   │   ├── 缩略图 <img>
│   │   ├── 文件名 + 时长
│   │   ├── 拖拽手柄图标 (⠿)
│   │   └── 状态标签：正常(隐藏) / 超时(红色警告) / 错误(红色)
│   │
│   └── ...
│
├── 操作栏
│   ├── [合成视频] 按钮（≥1 个有效片段时可用）
│   ├── [清空全部] 按钮
│   └── 有效片段计数："已选 X 个有效片段"
│
└── 结果区 (result-area) — 合成完成后显示
    ├── <video> 预览播放器
    └── [下载视频] 链接
```

### 5.3 CSS 关键样式

新增 CSS 集中在 `<style>` 块末尾：

```css
/* ===== 短视频拼接模块 ===== */
.tab-bar { display: flex; gap: 0; border-bottom: 2px solid #e0e0e0; margin-bottom: 20px; }
.tab { padding: 10px 24px; border: none; background: none; cursor: pointer; font-size: 15px;
       border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.2s; }
.tab.active { border-bottom-color: #4A90D9; color: #4A90D9; font-weight: 600; }
.tab:hover:not(.active) { color: #666; }

.clip-panel { display: none; }
.clip-panel.visible { display: block; }

.segment-list { display: flex; flex-direction: column; gap: 8px; margin: 16px 0; }
.segment-card { display: flex; align-items: center; gap: 12px; padding: 10px;
                border: 1px solid #e0e0e0; border-radius: 8px; background: #fff;
                cursor: grab; transition: box-shadow 0.2s; }
.segment-card.dragging { opacity: 0.5; }
.segment-card.drag-over { box-shadow: 0 0 0 2px #4A90D9; }
.segment-card.error { border-color: #e74c3c; background: #fff5f5; }
.segment-card .thumb { width: 80px; height: 45px; object-fit: cover; border-radius: 4px; }
.segment-card .info { flex: 1; }
.segment-card .info .name { font-size: 13px; font-weight: 500; }
.segment-card .info .meta { font-size: 12px; color: #888; }
.segment-card .drag-handle { color: #ccc; font-size: 18px; cursor: grab; }
.segment-card .status-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.segment-card .status-badge.error { background: #fde8e8; color: #c0392b; }

.placeholder-hint { text-align: center; padding: 40px; color: #aaa; font-size: 14px; }

.result-area { margin-top: 24px; padding: 16px; border: 1px solid #e0e0e0; border-radius: 8px; }
.result-area video { width: 100%; max-height: 400px; border-radius: 4px; margin-bottom: 12px; }
```

### 5.4 JavaScript 核心逻辑

状态变量：
```javascript
let clipState = {
    clipId: null,
    segments: [],      // 与后端 /api/clip/upload 返回的 segments 列表同步
    composing: false,
    result: null       // { download_url, filename, duration, width, height, fps }
};
```

上传处理：
```javascript
async function handleClipUpload(files) {
    const formData = new FormData();
    Array.from(files).forEach(f => formData.append('files', f));

    const resp = await fetch('/api/clip/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    clipState.clipId = data.clip_id;
    clipState.segments = data.segments;
    renderSegmentList();
}
```

拖拽排序（HTML5 Drag & Drop）：
```javascript
function renderSegmentList() {
    // 为每个 segment 渲染 .segment-card
    // 绑定 dragstart / dragover / drop / dragend 事件
    // 拖拽结束后更新 clipState.segments 数组顺序
    // 超时/错误的卡片不参与拖拽（不可拖拽、放在末尾）
}

async function composeClip() {
    clipState.composing = true;
    const validOrder = clipState.segments
        .filter(s => s.status === 'ok')
        .map(s => s.id);

    const resp = await fetch('/api/clip/compose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            clip_id: clipState.clipId,
            segment_order: validOrder
        })
    });
    const data = await resp.json();
    clipState.result = data;
    clipState.composing = false;
    renderResult();
}
```

---

## 6. 错误处理矩阵

| 场景 | HTTP 状态码 | 用户提示 |
|------|------------|----------|
| 上传文件格式不支持 | 200 (status: error) | "xxx.mkv: 不支持的视频格式，请上传 mp4/mov/avi/webm" |
| 视频读取失败 | 200 (status: error) | "xxx.mp4: 无法读取视频文件，请检查文件是否损坏" |
| 视频超 5 秒 | 200 (status: too_long) | "xxx.mp4: 视频时长 6.2s，超过 5 秒限制" |
| 无文件上传 | 400 | "请至少上传一个视频文件" |
| clip_id 不存在 | 404 | "会话不存在或已过期" |
| 无有效片段 | 400 | "没有有效的视频片段可供合成，请检查上传的视频" |
| 合成失败 | 500 | "视频合成失败: {详细错误}" |
| 文件不存在(下载) | 404 | "文件不存在" |

---

## 7. 依赖变更

**无新增依赖**。moviepy / FastAPI / Pillow / uvicorn 均已在项目中。

---

## 8. 测试计划

### 8.1 API 测试（pytest）

测试文件：`tests/test_clip_api.py`

| 用例 ID | 测试场景 | 预期 |
|---------|----------|------|
| TC-C01 | 上传单个 ≤5s 视频 | status=ok, 返回 segment 信息 |
| TC-C02 | 上传单个 >5s 视频 | status=too_long, 有 error_msg |
| TC-C03 | 上传多个视频（混合 ok + too_long） | 分别返回对应 status |
| TC-C04 | 上传空文件列表 | 400 |
| TC-C05 | 拼接两个有效视频 | status=completed, 返回 download_url |
| TC-C06 | clip_id 不存在时拼接 | 404 |
| TC-C07 | 全部片段 too_long 时拼接 | 400 "没有有效的视频片段" |
| TC-C08 | 自定义 segment_order 拼接 | 验证顺序正确（通过输出视频时长校验） |
| TC-C09 | 下载已合成的视频 | 200, 返回 video/mp4 |
| TC-C10 | 下载不存在的视频 | 404 |
| TC-C11 | 获取缩略图 | 200, 返回 image/jpeg |
| TC-C12 | 获取不存在的缩略图 | 404 |
| TC-C13 | 不同分辨率视频拼接 | 成功，compose 自动处理 |
| TC-C14 | 不同 FPS 视频拼接 | 成功 |

### 8.2 前端 UI 测试（可选，playwright）

测试文件：`tests/test_clip_ui.py`

| 用例 ID | 测试场景 |
|---------|----------|
| TC-C15 | 标签页切换到短视频拼接面板 |
| TC-C16 | 上传文件后渲染片段列表 |
| TC-C17 | 超时片段标红显示 |
| TC-C18 | 拖拽调整顺序 |
| TC-C19 | 合成按钮状态（无效时禁用） |

---

## 9. 文件清单（本次新增/修改）

| 文件 | 操作 | 说明 |
|------|------|------|
| `video_maker_app.py` | 修改 | 新增约 200 行代码（API + HTML/CSS/JS） |
| `tests/test_clip_api.py` | 新增 | API 自动化测试（~14 个用例） |
| `tests/test_clip_ui.py` | 新增 | UI 自动化测试（~5 个用例） |
| `tests/run_all.py` | 修改 | 加入 clip 测试套件 |
| `video_clip_prd.md` | 已存在 | PRD（评审已通过） |
| `video_clip_design.md` | 新增 | 本文档 |
*（内容由AI生成，仅供参考）*
