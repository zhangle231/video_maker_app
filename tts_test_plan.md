---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f4ff5be3e1f50ff475cd88e8c986c75f_729984dc7ff911f18018525400826444
    ReservedCode1: 2gZSs3MEnKxzJPgCczAM1kuTLb4TnUa5XLOYO/kPwoQY3FNHYeGrwggBLjOy/XMr5SExmwJKR/MCOPgx+/wchjZnOlZFHpKMXM56g2oPsYqyDzE4MQscDvLC/iGDFxxfRpZSR86VlD17OAQPT77mdq7BNvBMtumzaEgZukj6g7xLsFYwZELvCSzwYhU=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f4ff5be3e1f50ff475cd88e8c986c75f_729984dc7ff911f18018525400826444
    ReservedCode2: 2gZSs3MEnKxzJPgCczAM1kuTLb4TnUa5XLOYO/kPwoQY3FNHYeGrwggBLjOy/XMr5SExmwJKR/MCOPgx+/wchjZnOlZFHpKMXM56g2oPsYqyDzE4MQscDvLC/iGDFxxfRpZSR86VlD17OAQPT77mdq7BNvBMtumzaEgZukj6g7xLsFYwZELvCSzwYhU=
---

# 测试方案：TTS 语音旁白功能

> 项目：video_maker_app  
> 版本：v2.0  
> 状态：草稿，待评审  
> 日期：2026-07-15  
> 关联 PRD：tts_prd.md  
> 关联设计：tts_design.md

---

## 1. 测试范围

### 1.1 测试对象

- `POST /api/tts/generate` — 单段语音生成
- `POST /api/tts/generate-all` — 批量语音生成
- `GET /api/tts/progress` — 批量生成进度轮询
- `GET /api/tts/audio/<segment_id>` — 语音文件试听
- `DELETE /api/tts/audio/<segment_id>` — 删除语音文件
- `POST /api/generate` 扩展 — 含 TTS 参数的视频合成
- `_compose_video` — 语音 + 背景音乐混音合成
- 前端 TTS 面板 — 风格选择、逐段操作、音量配置、批量生成 UI

### 1.2 测试类型

| 类型 | 说明 |
|------|------|
| 功能测试 | 验证各 API 和 UI 交互是否按设计工作 |
| 边界测试 | 空文本、极长文本、音量极值等 |
| 异常测试 | 网络中断、文件缺失、并发请求等 |
| 集成测试 | TTS + 背景音乐 + 图片合成 |
| 兼容测试 | 无 TTS 参数时走原有逻辑 |

## 2. 测试环境

| 项 | 值 |
|---|-----|
| Python | 3.12 |
| 操作系统 | Windows 11 |
| 浏览器 | Chrome / Edge 最新版 |
| 依赖 | `edge-tts` 已安装 |
| 启动方式 | `python video_maker_app.py` |

## 3. 测试用例

### 3.1 TTS 单段生成

| 编号 | 用例 | 输入 | 预期结果 |
|------|------|------|----------|
| TC-01 | 正常生成 | segment_id="seg_0", text="这是第一段旁白", style="gentle_female" | 返回 success=true, audio_path, duration>0 |
| TC-02 | 空文本 | segment_id="seg_0", text="", style="gentle_female" | 返回 success=false, error 提示文字不能为空 |
| TC-03 | 极长文本 | segment_id="seg_0", text=500 字中文 | 成功生成，duration 与文字长度匹配 |
| TC-04 | 所有风格各生成一次 | 分别用 gentle_female / tvb_style / shaw_style | 三者均成功，语音听感不同 |
| TC-05 | 重复生成相同段 | 同一 segment_id 生成两次 | 第二次覆盖前一次文件 |
| TC-06 | 特殊字符 | text 含标点、空格、换行、数字 | 正常生成，语音停顿位置合理 |

### 3.2 批量生成与进度轮询

| 编号 | 用例 | 输入 | 预期结果 |
|------|------|------|----------|
| TC-07 | 2 段批量生成 | segments=[seg_0, seg_1], style="gentle_female" | 返回 task_id, total=2 |
| TC-08 | 轮询进度 | 连续 5 次 GET /api/tts/progress | completed 从 0→1→2，status 从 running→done |
| TC-09 | 轮询失败段 | segments=[seg_0(正常), seg_2(空文本)] | status=partial, 各 segment 状态正确 |
| TC-10 | 无文字段批量 | segments=[] | 返回 success=false 或 total=0 |
| TC-11 | 轮询间隔校验 | 启动批量后 0.5s、2s、5s 各轮询一次 | 0.5s 时 completed=0, 2s 时应有进展 |

### 3.3 语音文件访问

| 编号 | 用例 | 输入 | 预期结果 |
|------|------|------|----------|
| TC-12 | 访问已生成语音 | GET /api/tts/audio/seg_0 | 返回 audio/mpeg 文件, 可试听 |
| TC-13 | 访问不存在的语音 | GET /api/tts/audio/nonexist | 返回 404 |
| TC-14 | 删除已生成语音 | DELETE /api/tts/audio/seg_0 | 返回 success=true, 文件被删除 |
| TC-15 | 删除不存在的语音 | DELETE /api/tts/audio/nonexist | 返回 success=true（幂等） |

### 3.4 视频合成（集成测试）

| 编号 | 用例 | 参数 | 预期结果 |
|------|------|------|----------|
| TC-16 | 仅 TTS 无 BGM | tts_enabled=true, tts_style=gentle_female, 无 music_id | 视频含语音, 图片时长≥语音时长 |
| TC-17 | TTS + BGM | tts_enabled=true, music_id=xxx, voice_volume=0.8, bgm_volume=0.4 | 同时有语音和背景音乐, 混合正常 |
| TC-18 | 语音长于图片 | 图片默认时长 3s, 语音 5s | 图片段自动延长至 5s |
| TC-19 | 语音短于图片 | 图片默认时长 10s, 语音 4s | 图片持续 10s, 4s 后仅有 BGM |
| TC-20 | TTS 关闭 | tts_enabled=false | 完全走原有无语音逻辑, 视频与之前一致 |
| TC-21 | 音量极值 | voice_volume=2.0, bgm_volume=0.0 | 语音最大, 无 BGM |
| TC-22 | 多段语音 + 变风格 | 3 段分别用不同风格 | 各段语音风格与指定一致 |

### 3.5 异常场景

| 编号 | 用例 | 操作 | 预期结果 |
|------|------|------|----------|
| TC-23 | 网络断开时生成 | 拔网线后 POST /api/tts/generate | 返回网络超时错误，前端显示可重试 |
| TC-24 | TTS 音频文件被手动删除后合成 | 删掉 tts/seg_0.mp3 后合成 | 静默跳过缺失段, 其他段正常 |
| TC-25 | 同时发起多次批量生成 | 快速点击 [全部生成] 两次 | 第二次覆盖前一次的 task_id，或拒绝 |

### 3.6 前端交互

| 编号 | 用例 | 操作 | 预期结果 |
|------|------|------|----------|
| TC-26 | 逐段生成 UI | 点击某段 [生成语音] | 按钮动画 → 显示时长和试听按钮 |
| TC-27 | 试听播放 | 点击 [▶ 试听] | 播放语音, 有暂停/继续控制 |
| TC-28 | 批量生成 UI | 点击 [全部生成语音] | 显示进度条, 逐段更新状态 |
| TC-29 | 音量比例切换 | 勾选"相对比例" → 修改比例值 | 音频实时更新, 切换回绝对值时保留数值 |
| TC-30 | 切换风格后重新生成 | 切换风格 → 点击 [重新生成] | 新风格生效, 试听确认 |

## 4. 测试流程

### 4.1 冒烟测试

1. 启动服务：`python video_maker_app.py`
2. 打开浏览器访问前端页面
3. 逐段生成语音并试听
4. 批量生成所有语音
5. 关闭 TTS 合成一次视频
6. 开启 TTS 合成一次视频

### 4.2 全覆盖测试

按上述 30 个 TC 逐条执行，在项目目录下的 `tests/tts_test_log.md` 中记录结果。

## 5. 通过标准

- 所有 TC 通过率 ≥ 95%（允许已知低优先级缺陷）
- TC-16/TC-17/TC-20（核心流程）必须通过
- 无 P0 级缺陷（会导致服务崩溃或视频无声/无法合成）
*（内容由AI生成，仅供参考）*
