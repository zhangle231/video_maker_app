---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f4ff5be3e1f50ff475cd88e8c986c75f_caa7250880c811f188a8525400826444
    ReservedCode1: 1zcyFX3hqq4pgFxSuGYu7nOqPYKAgK7eN8K2CtGC6DoA6+pVz9GFGuRu7ZIZfRrJ62IodLdVcwPPMYai1LBlTCaMZXrUS3T3lPZcai7ADamcKcTAYz7A3404Dg5X7P6OD8n+o7boK3V09+ZMdRwAqAzc7Rjm/NxLHNj5yECVLlCEdNckQ1i/yeDTx30=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f4ff5be3e1f50ff475cd88e8c986c75f_caa7250880c811f188a8525400826444
    ReservedCode2: 1zcyFX3hqq4pgFxSuGYu7nOqPYKAgK7eN8K2CtGC6DoA6+pVz9GFGuRu7ZIZfRrJ62IodLdVcwPPMYai1LBlTCaMZXrUS3T3lPZcai7ADamcKcTAYz7A3404Dg5X7P6OD8n+o7boK3V09+ZMdRwAqAzc7Rjm/NxLHNj5yECVLlCEdNckQ1i/yeDTx30=
Status: 已评审通过
---

# Video Clip 拼接模块 PRD

> 版本：v0.1  
> 日期：2026-07-16  
> 状态：待审阅

---

## 1. 背景与目标

当前 `video_maker_app` 仅支持图片素材。新增"短视频拼接"模块，允许用户上传多个时长 ≤5 秒的短视频，将其按顺序拼接为一个完整 MP4 文件。

**核心定位**：独立模块，与现有图片故事模块并行，不混合编排。最小可行产品（MVP）。

---

## 2. 用户故事

1. 用户打开页面，切换到"短视频拼接"标签 / 页面
2. 用户拖拽或点击上传多个短视频文件（.mp4 / .mov 等）
3. 系统校验每个视频时长，超过 5 秒的拒绝并提示
4. 用户可拖拽调整片段顺序
5. 点击"合成"按钮，系统将视频按顺序拼接为一个 MP4
6. 提供下载链接
7. 合成参数（分辨率 / FPS）统一使用第一个视频的参数

---

## 3. 功能范围

### 3.1 v0.1 范围内

| 功能 | 说明 |
|------|------|
| 视频上传 | 前端拖拽/点击上传，支持 .mp4 / .mov / .avi / .webm |
| 时长校验 | 超过 5 秒拒绝，前端提示 + 后端二次校验 |
| 片段排序 | 前端可拖拽调整顺序 |
| 视频拼接 | 后端使用 moviepy `concatenate_videoclips` 拼接 |
| 缩略图预览 | 上传后显示视频首帧缩略图 |
| 下载 | `/api/clip/download/{filename}` |

### 3.2 v0.1 范围内不做

| 功能 | 处理方式 | 备注 |
|------|----------|------|
| 字幕叠加 | 不做 | PRD issue 备忘 |
| TTS 配音 | 不做 | PRD issue 备忘 |
| 过渡效果 | 不做 | 直接硬切拼接 |
| BGM 混音 | 不做 | 保留原视频音频，不做额外混音 |
| 视频截取/裁剪 | 不做 | 用户自行准备 ≤5s 素材 |
| 与图片混合编排 | 不做 | 方案 B，纯视频拼接 |

---

## 4. API 设计

### 4.1 上传视频片段

```
POST /api/clip/upload
Content-Type: multipart/form-data

参数：
  - files: List[UploadFile]  视频文件列表

返回：
{
  "clip_id": "uuid",
  "segments": [
    {
      "id": "seg_0",
      "filename": "xxx.mp4",
      "duration": 4.8,
      "width": 1920,
      "height": 1080,
      "fps": 30.0,
      "thumbnail": "/api/clip/thumbnail/xxx.jpg",
      "status": "ok" | "too_long"
    },
    ...
  ],
  "errors": [...]
}
```

### 4.2 拼接合成

```
POST /api/clip/compose

参数（JSON Body）：
{
  "clip_id": "uuid",
  "segment_order": ["seg_2", "seg_0", "seg_1"]   // 可选，不传按上传顺序
}

返回：
{
  "status": "completed",
  "filename": "clip_output_xxx.mp4",
  "duration": 14.2,
  "width": 1920,
  "height": 1080,
  "fps": 30.0,
  "download_url": "/api/clip/download/clip_output_xxx.mp4"
}
```

### 4.3 下载

```
GET /api/clip/download/{filename}
```

### 4.4 缩略图

```
GET /api/clip/thumbnail/{filename}
```

---

## 5. 前端 UI 设计

在现有页面增加**标签切换**（图片故事 / 短视频拼接），短视频标签下包含：

| 区域 | 内容 |
|------|------|
| 上传区 | 拖拽/点击上传，显示已上传缩略图列表 |
| 片段列表 | 每个片段显示缩略图 + 文件名 + 时长，支持拖拽排序 |
| 校验提示 | 超过 5 秒的视频在列表中标红并禁用合成按钮 |
| 操作按钮 | 合成（需至少 1 个有效片段）、清空 |
| 结果区 | 合成完成后显示视频预览 + 下载链接 |

---

## 6. 后端处理逻辑

1. 接收上传文件，保存到 `uploads/clips/{clip_id}/`
2. 逐文件读取元数据（moviepy `VideoFileClip`），校验时长 ≤ 5s
3. 合成时按 `segment_order` 加载 `VideoFileClip`，用 `concatenate_videoclips` 拼接
4. 输出分辨率 / FPS 取第一个视频片段的参数
5. 编码：libx264，`preset="medium"`，`bitrate="5000k"`
6. 输出到 `videos/clip_output_{uuid}.mp4`

---

## 7. 文件存储

```
video_maker_app/
├── uploads/
│   └── clips/          # 新增：短视频上传目录（按 clip_id 分子目录）
├── videos/
│   └── clip_output_*   # 新增：拼接输出视频
└── ...
```

---

## 8. 预研结论

moviepy 的 `concatenate_videoclips` 已满足需求：
- 支持不同分辨率 / FPS 的视频拼接（自动兼容处理）
- 保留原视频音轨
- 项目已依赖 moviepy，无新增依赖

---

## 9. 后续 Issue 备忘

| Issue | 描述 |
|-------|------|
| VIDEO-001 | 短视频片段支持字幕叠加 |
| VIDEO-002 | 短视频片段支持 TTS 配音 |
| VIDEO-003 | 片段间过渡效果（FadeIn / Crossfade） |
| VIDEO-004 | BGM 混音覆盖短视频片段 |
| VIDEO-005 | 与图片片段混合编排 |
| VIDEO-006 | 视频截取/裁剪（用户可指定起止时间） |

---

## 10. 验收标准

- [ ] 上传 ≤5s 视频成功，超 5s 被拒绝并有提示
- [ ] 拖拽调整顺序后拼接结果顺序正确
- [ ] 拼接后音画同步
- [ ] 不同分辨率视频可正常拼接
- [ ] 下载链接可正常下载并播放
- [ ] 自动化测试覆盖核心 API
*（内容由AI生成，仅供参考）*
