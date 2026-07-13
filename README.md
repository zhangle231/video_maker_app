# 图片故事视频生成器

将多张图片 + 对应文本合成为 MP4 视频的 Web 工具。

## 功能

- 拖拽/上传图片，为每张图填写故事文本
- 支持加载 prompts.json 配置，按风格分组批量导入图片
- 三种字幕模式：叠加半透明底、无背景、纯黑底
- Large 模式：图片在上、字幕区在下，互不遮挡
- 可调参数：时长、字号、颜色、过渡效果、FPS

## 依赖

- Python 3.10+
- FastAPI + uvicorn
- moviepy
- Pillow

```bash
pip install fastapi uvicorn moviepy Pillow
```

## 启动

```bash
python video_maker_app.py
```

打开浏览器访问 `http://127.0.0.1:8765`

## 配置说明

首次运行时会在同目录生成 `app_config.json`，用于记住 prompts.json 路径和图片根目录。该文件已加入 `.gitignore`，不会提交到仓库。

`prompts.json` 格式参考 `app_config.json.example` 中的说明。
