"""
图片故事视频生成器 - FastAPI Web 工具
将多张图片 + 对应文本合成为 MP4 视频
"""

import os
import json
import shutil
import uuid
import asyncio
import threading
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, File, Form, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from moviepy import (
    ImageClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
    vfx,
    afx,
)
from PIL import Image

# ── 路径配置 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "videos"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
TTS_DIR = BASE_DIR / "tts"
TEMP_TTS_DIR = BASE_DIR / "temp" / "tts"
TTS_DIR.mkdir(exist_ok=True)
TEMP_TTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="图片故事视频生成器")

CONFIG_FILE = BASE_DIR / "app_config.json"

# ── TTS 音色映射 ──────────────────────────────────────────
TTS_VOICES = {
    "gentle_female": "zh-CN-XiaoxiaoNeural",
    "tvb_style":     "zh-CN-XiaoyiNeural",
    "shaw_style":    "zh-CN-YunxiNeural",
}

# ── 批量生成进度管理 ──────────────────────────────────────
_batch_progress = {}
_progress_lock = threading.Lock()


# ── HTML 前端 ──────────────────────────────────────────────
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>图片故事视频生成器</title>
<style>
    :root {
        --bg: #1a1a2e;
        --card: #16213e;
        --accent: #e94560;
        --accent2: #0f3460;
        --text: #eee;
        --text2: #aaa;
        --border: #2a2a4a;
        --success: #2ecc71;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
        font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
        background: var(--bg); color: var(--text); min-height: 100vh;
    }
    .header {
        background: var(--card); padding: 18px 32px;
        border-bottom: 1px solid var(--border);
        display: flex; align-items: center; gap: 12px;
    }
    .header h1 { font-size: 20px; font-weight: 600; }
    .header .badge { 
        background: var(--accent); font-size: 11px; padding: 3px 10px;
        border-radius: 10px; font-weight: 500;
    }
    .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
    
    /* 上传区 */
    .drop-zone {
        border: 2px dashed var(--border); border-radius: 12px;
        padding: 40px; text-align: center; cursor: pointer;
        transition: all .2s; margin-bottom: 20px;
    }
    .drop-zone:hover, .drop-zone.dragover {
        border-color: var(--accent); background: rgba(233,68,96,0.05);
    }
    .drop-zone p { color: var(--text2); font-size: 14px; margin-top: 8px; }
    .drop-zone .icon { font-size: 40px; }
    
    /* 目录导入 */
    .dir-import {
        display: flex; gap: 10px; align-items: center; margin-bottom: 20px;
        padding: 12px 16px; background: var(--card); border-radius: 10px;
        border: 1px solid var(--border);
    }
    
    /* 图片列表 */
    .slide-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; }
    .slide-item {
        background: var(--card); border-radius: 10px; padding: 14px;
        display: flex; gap: 14px; align-items: flex-start;
        border: 1px solid var(--border);
    }
    .slide-item .thumb {
        border-radius: 6px; object-fit: cover; flex-shrink: 0; background: #111;
        width: 240px; height: 160px;
    }
    /* 小 */
    .slide-list[data-size="small"] .thumb { width: 120px; height: 80px; }
    /* 大 */
    .slide-list[data-size="large"] .thumb {
        width: 100%; height: auto; max-height: 500px; object-fit: contain;
    }
    .slide-list[data-size="large"] .slide-item { flex-direction: column; }
    .slide-item .info { flex: 1; display: flex; flex-direction: column; gap: 8px; }
    .slide-item .filename { font-size: 12px; color: var(--text2); }
    .slide-item textarea {
        width: 100%; background: var(--bg); border: 1px solid var(--border);
        border-radius: 6px; color: var(--text); padding: 8px 10px;
        font-size: 13px; resize: vertical; min-height: 48px;
        font-family: inherit;
    }
    .slide-item .row { display: flex; gap: 10px; align-items: center; }
    .slide-item .row label { font-size: 12px; color: var(--text2); }
    .slide-item .row input[type=number] {
        width: 60px; background: var(--bg); border: 1px solid var(--border);
        border-radius: 4px; color: var(--text); padding: 4px 6px;
        font-size: 13px; text-align: center;
    }
    .slide-item .del-btn {
        background: none; border: none; color: var(--accent);
        cursor: pointer; font-size: 18px; padding: 4px 8px;
    }
    
    /* 全局设置 */
    .global-settings {
        background: var(--card); border-radius: 10px; padding: 16px 20px;
        display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
        margin-bottom: 20px; border: 1px solid var(--border);
    }
    .global-settings h3 { width: 100%; font-size: 14px; margin-bottom: -8px; }
    .global-settings label { font-size: 12px; color: var(--text2); }
    .global-settings input[type=number],
    .global-settings input[type=color],
    .global-settings select {
        background: var(--bg); border: 1px solid var(--border);
        border-radius: 4px; color: var(--text); padding: 5px 8px;
        font-size: 13px;
    }
    .global-settings input[type=number] { width: 70px; }
    .global-settings input[type=color] { width: 36px; height: 30px; padding: 2px; cursor: pointer; }
    
    /* 按钮 */
    .btn-row { display: flex; gap: 12px; margin-bottom: 20px; }
    .btn {
        padding: 10px 24px; border-radius: 8px; border: none;
        font-size: 14px; font-weight: 600; cursor: pointer;
        transition: all .2s; font-family: inherit;
    }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover { background: #d63850; }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-secondary { background: var(--accent2); color: #fff; }
    .btn-secondary:hover { background: #1a4a80; }
    
    /* 进度 */
    .progress-wrap { display: none; margin-bottom: 20px; }
    .progress-wrap.show { display: block; }
    .progress-bar {
        height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;
    }
    .progress-fill {
        height: 100%; background: var(--accent); width: 0%;
        transition: width .3s; border-radius: 3px;
    }
    .progress-text { font-size: 12px; color: var(--text2); margin-top: 6px; }
    
    /* 结果 */
    .result-wrap { display: none; margin-bottom: 20px; }
    .result-wrap.show { display: block; }
    .result-card {
        background: var(--card); border-radius: 10px; padding: 20px;
        border: 1px solid var(--success); text-align: center;
    }
    .result-card video { max-width: 100%; max-height: 400px; border-radius: 6px; }
    .result-card .info { margin-top: 10px; font-size: 13px; color: var(--text2); }
    
    .empty-state {
        text-align: center; padding: 60px 20px; color: var(--text2);
    }
    .empty-state .icon { font-size: 50px; margin-bottom: 10px; }

    /* TTS & BGM Panel */
    .tts-panel {
        background: var(--card); border-radius: 10px; padding: 16px 20px;
        display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
        margin-bottom: 20px; border: 1px solid var(--border);
    }
    .tts-panel h3 { width: 100%; font-size: 14px; margin-bottom: -4px; }
    .tts-panel label { font-size: 12px; color: var(--text2); }
    .tts-panel select, .tts-panel input[type=range], .tts-panel input[type=number] {
        background: var(--bg); border: 1px solid var(--border);
        border-radius: 4px; color: var(--text); font-size: 13px;
    }
    .tts-panel select { padding: 5px 8px; }
    .tts-panel input[type=range] { width: 80px; }
    .tts-panel input[type=number] { width: 60px; padding: 4px 6px; text-align: center; }
    .tts-btn {
        font-size: 11px; padding: 4px 8px; border-radius: 4px;
        border: 1px solid var(--border); background: var(--bg);
        color: var(--text); cursor: pointer; margin-left: 4px;
    }
    .tts-btn:hover { border-color: var(--accent); }
    .tts-btn.generating { opacity: 0.5; cursor: wait; }
    .tts-status { font-size: 11px; margin-left: 6px; }
    .tts-status.ok { color: var(--success); }
    .tts-status.err { color: var(--accent); }
    .tts-status.pending { color: var(--text2); }

</style>
</head>
<body>
<div class="header">
    <h1>图片故事视频生成器</h1>
    <span class="badge">BETA</span>
    <span style="font-size:10px;color:var(--text2);margin-left:auto;">v20260713-1700</span>
</div>

<div class="container">
    <!-- 加载 Prompt 配置 -->
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:20px;padding:16px;background:var(--card);border-radius:10px;border:1px solid var(--border)">
        <span style="font-size:12px;color:var(--accent);font-weight:600;white-space:nowrap;">Prompt 配置</span>
        <input type="text" id="promptsJsonPath" placeholder="prompts.json 路径" 
            style="flex:1;min-width:200px; background:var(--card); border:1px solid var(--border); border-radius:6px; 
            color:var(--text); padding:8px 12px; font-size:13px; font-family:inherit;"
            onblur="saveConfigField('prompts_json_path', this.value)">
        <label class="btn btn-secondary" style="cursor:pointer;margin:0;padding:7px 14px;font-size:12px;">
            选文件
            <input type="file" id="promptsJsonPicker" accept=".json" hidden onchange="pickJsonFile(this)">
        </label>
        <input type="text" id="imgRootPath" placeholder="图片根目录，如 D:\project\result\4" 
            style="flex:1;min-width:180px; background:var(--card); border:1px solid var(--border); border-radius:6px; 
            color:var(--text); padding:8px 12px; font-size:13px; font-family:inherit;"
            onblur="saveConfigField('img_root_path', this.value)">
        <button class="btn btn-secondary" onclick="loadPromptConfig()">加载配置</button>
        <span id="cfgStatus" style="font-size:12px;color:var(--text2);"></span>
    </div>

    <!-- Set 选择区（加载配置后显示） -->
    <div id="setPanel" style="display:none;margin-bottom:20px;padding:16px;background:var(--card);border-radius:10px;border:1px solid var(--border);">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
            <span style="font-size:12px;color:var(--accent);font-weight:600;">选择风格</span>
            <button class="btn btn-secondary" style="font-size:11px;padding:4px 10px;" onclick="selectAllSets()">全选</button>
            <button class="btn btn-secondary" style="font-size:11px;padding:4px 10px;" onclick="deselectAllSets()">全不选</button>
        </div>
        <div id="setToggles" style="display:flex;flex-wrap:wrap;gap:8px;"></div>
    </div>

    <!-- 图片列表 -->
    <div class="slide-list" id="slideList">
        <div class="empty-state" id="emptyState">
            <div class="icon">🖼️</div>
            <p>还没有添加图片，请上传图片开始制作</p>
        </div>
    </div>

    <!-- 全局设置 -->
    <div class="global-settings">
        <h3>全局设置</h3>
        <div>
            <label>默认时长(秒)</label>
            <input type="number" id="defaultDuration" value="3" min="1" max="30" step="0.5">
        </div>
        <div>
            <label>字号</label>
            <input type="number" id="fontSize" value="36" min="12" max="120">
        </div>
        <div>
            <label>文字颜色</label>
            <input type="color" id="textColor" value="#ffffff">
        </div>
        <div>
            <label>背景条</label>
            <select id="textBg">
                <option value="semi">半透明黑底</option>
                <option value="none">无背景</option>
                <option value="solid">纯黑底</option>
            </select>
        </div>
        <div>
            <label>过渡(秒)</label>
            <input type="number" id="fadeDuration" value="0.3" min="0" max="2" step="0.1">
        </div>
        <div>
            <label>输出FPS</label>
            <input type="number" id="fps" value="24" min="12" max="60">
        </div>
        <div>
            <label>应用默认</label>
            <button class="btn btn-secondary" onclick="applyDefaults()">应用到全部</button>
        </div>
        <div style="margin-left:auto; display:flex; align-items:center; gap:8px;">
            <label>预览大小</label>
            <label style="cursor:pointer;padding:4px 10px;border-radius:4px;" id="lblSmall" onclick="setViewSize('small')">小</label>
            <label style="cursor:pointer;padding:4px 10px;border-radius:4px;background:var(--accent);" id="lblMedium" onclick="setViewSize('medium')">中</label>
            <label style="cursor:pointer;padding:4px 10px;border-radius:4px;" id="lblLarge" onclick="setViewSize('large')">大</label>
        </div>
    </div>

    
    <!-- TTS & BGM 面板 -->
    <div class="tts-panel" id="ttsPanel">
        <h3>TTS 语音 & 背景音乐</h3>
        <div>
            <label><input type="checkbox" id="ttsEnabled" onchange="toggleTTSPanel()"> 启用语音</label>
        </div>
        <div>
            <label>音色</label>
            <select id="ttsStyle">
                <option value="gentle_female">温柔女声 (Xiaoxiao)</option>
                <option value="tvb_style">TVB 风格 (Xiaoyi)</option>
                <option value="shaw_style">邵氏风格 (Yunxi)</option>
            </select>
        </div>
        <div>
            <label>语音音量</label>
            <input type="range" id="voiceVolume" min="0" max="200" value="100" step="5" oninput="document.getElementById('voiceVolVal').textContent=this.value+'%'">
            <span id="voiceVolVal" style="font-size:11px;color:var(--text2)">100%</span>
        </div>
        <div>
            <label>BGM 音量</label>
            <input type="range" id="musicVolume" min="0" max="200" value="30" step="5" oninput="document.getElementById('musicVolVal').textContent=this.value+'%'">
            <span id="musicVolVal" style="font-size:11px;color:var(--text2)">30%</span>
        </div>
        <div>
            <button class="btn btn-secondary" onclick="generateAllTTS()" id="btnGenAllTTS" disabled style="font-size:12px;padding:6px 14px;">批量生成语音</button>
            <span id="ttsBatchStatus" style="font-size:11px;color:var(--text2);margin-left:6px;"></span>
        </div>
    </div>

    <!-- 按钮 -->
    <div class="btn-row">
        <button class="btn btn-primary" id="btnGenerate" onclick="generateVideo()" disabled>生成视频</button>
        <button class="btn btn-secondary" onclick="clearAll()">清空全部</button>
    </div>

    <!-- 进度 -->
    <div class="progress-wrap" id="progressWrap">
        <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
        <div class="progress-text" id="progressText">准备中...</div>
    </div>

    <!-- 结果 -->
    <div class="result-wrap" id="resultWrap">
        <div class="result-card" id="resultCard"></div>
    </div>
</div>

<script>
// ── TTS 状态 ──
let ttsSegments = {};  // {index: {segment_id, path, status}}

// ── 状态 ──
let slides = [];
let viewSize = 'medium';

// ── 渲染 ──
function renderSlides() {
    const list = document.getElementById('slideList');
    document.getElementById('btnGenerate').disabled = slides.length === 0;

    if (slides.length === 0) {
        list.innerHTML = `<div class="empty-state" id="emptyState">
            <div class="icon">🖼️</div>
            <p>还没有添加图片，请上传图片开始制作</p>
        </div>`;
        return;
    }

    list.innerHTML = slides.map((s, i) => `
        <div class="slide-item">
            <img class="thumb" src="${s.dataUrl}" alt="slide ${i+1}">
            <div class="info">
                <div class="filename">第 ${i+1} 张 · ${escHtml(s.name || s.file?.name || s.path?.split(/[\\\/]/).pop() || '图片')}</div>
                <textarea placeholder="输入这段画面的故事文本..." 
                    onchange="updateSlide(${i}, 'text', this.value)">${escHtml(s.text)}</textarea>
                <div class="row">
                    <label>时长(秒)</label>
                    <input type="number" value="${s.duration}" min="1" max="30" step="0.5"
                        onchange="updateSlide(${i}, 'duration', parseFloat(this.value)||3)">
                    <button class="del-btn" onclick="removeSlide(${i})" title="移除">✕</button>                    <button class="tts-btn" onclick="event.stopPropagation();generateSlideTTS(${i})" id="ttsGenBtn_${i}">生成语音</button>                    <button class="tts-btn" onclick="event.stopPropagation();playSlideTTS(${i})" id="ttsPlayBtn_${i}" style="display:none;">试听</button>                    <span class="tts-status pending" id="ttsStatus_${i}"></span>
                </div>
            </div>
        </div>
    `).join('');
    list.setAttribute('data-size', viewSize);
list.setAttribute('data-size', viewSize);
    // Restore TTS button states
    setTimeout(() => {
        for (let i = 0; i < slides.length; i++) {
            const seg = ttsSegments[i];
            if (seg) {
                const statusEl = document.getElementById('ttsStatus_' + i);
                const playBtn = document.getElementById('ttsPlayBtn_' + i);
                const genBtn = document.getElementById('ttsGenBtn_' + i);
                if (statusEl) {
                    if (seg.status === 'ok') {
                        statusEl.textContent = '已生成';
                        statusEl.className = 'tts-status ok';
                    } else {
                        statusEl.textContent = '生成失败';
                        statusEl.className = 'tts-status err';
                    }
                }
                if (playBtn && seg.status === 'ok') playBtn.style.display = '';
                if (genBtn && seg.status === 'ok') genBtn.style.display = 'none';
            }
        }
    }, 100);
}

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function updateSlide(idx, key, val) { slides[idx][key] = val; }
function removeSlide(idx) { slides.splice(idx, 1); renderSlides(); }
function setViewSize(sz) {
    viewSize = sz;
    ['small','medium','large'].forEach(s => {
        const el = document.getElementById('lbl' + s.charAt(0).toUpperCase() + s.slice(1));
        if (el) el.style.background = s === sz ? 'var(--accent)' : '';
    });
    document.getElementById('slideList').setAttribute('data-size', sz);
}
function applyDefaults() {
    const d = parseFloat(document.getElementById('defaultDuration').value) || 3;
    slides.forEach(s => s.duration = d);
    renderSlides();
}
function clearAll() { slides = []; renderSlides(); }

// ── 加载 Prompt 配置 ──
let configData = null;
let selectedSetKeys = new Set();  // 显式状态，避免 DOM :checked 查询问题

// ── 配置加载 / 保存 ──
async function loadConfig() {
    try {
        const r = await fetch('/api/config');
        const cfg = await r.json();
        if (cfg.prompts_json_path) document.getElementById('promptsJsonPath').value = cfg.prompts_json_path;
        if (cfg.img_root_path) document.getElementById('imgRootPath').value = cfg.img_root_path;
    } catch(e) {}
}
function saveConfigField(field, value) {
    fetch('/api/config', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({[field]: value})}).catch(()=>{});
}
loadConfig();

function pickJsonFile(input) {
    if (input.files.length > 0) {
        const file = input.files[0];
        document.getElementById('promptsJsonPath').value = file.name;
        document.getElementById('promptsJsonPath')._file = file;
        document.getElementById('cfgStatus').textContent = '已选择: ' + file.name;
    }
}

async function loadPromptConfig() {
    const jsonInput = document.getElementById('promptsJsonPath');
    const jsonPath = jsonInput.value.trim();
    const jsonFile = jsonInput._file;  // 可能通过"选文件"缓存
    const imgRoot = document.getElementById('imgRootPath').value.trim();
    const status = document.getElementById('cfgStatus');

    if (!imgRoot) { status.textContent = '请填写图片根目录路径'; return; }
    if (!jsonPath && !jsonFile) { status.textContent = '请选择或输入 prompts.json'; return; }

    status.textContent = '加载中...';

    try {
        let resp;
        if (jsonFile) {
            // 通过 FileReader 读取文件内容，发送到后端
            const content = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = e => resolve(e.target.result);
                reader.onerror = reject;
                reader.readAsText(jsonFile);
            });
            resp = await fetch('/api/load-config-content', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({json_content: content, img_root: imgRoot}),
            });
        } else {
            resp = await fetch('/api/load-config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({prompts_json: jsonPath, img_root: imgRoot}),
            });
        }
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        configData = await resp.json();

        // 生成 toggle 按钮（纯 div 点击切换，避免 checkbox+label 交互问题）
        selectedSetKeys.clear();
        let html = '';
        for (const [key, s] of Object.entries(configData.sets)) {
            const missing = s.missing_panels.length;
            const label = `${key} · ${s.name}` + (missing ? ` (缺${missing}张)` : '');
            html += `<div class="set-toggle" data-key="${key}" onclick="onSetClick(this)"
                style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;
                background:var(--card);border:1px solid var(--border);border-radius:6px;cursor:pointer;font-size:13px;
                user-select:none;transition:all .2s;">
                ${label}
            </div>`;
        }
        document.getElementById('setToggles').innerHTML = html;
        document.getElementById('setPanel').style.display = '';
        status.textContent = `已加载 ${Object.keys(configData.sets).length} 组风格`;

        // 自动选中第一个 set
        const firstToggle = document.querySelector('#setToggles .set-toggle');
        if (firstToggle) { onSetClick(firstToggle); }
    } catch (e) {
        status.textContent = '加载失败: ' + e.message;
    }
}

function onSetClick(el) {
    const key = el.dataset.key;
    if (el.classList.contains('active')) {
        el.classList.remove('active');
        el.style.borderColor = 'var(--border)';
        el.style.background = 'var(--card)';
        el.style.color = 'var(--text)';
        selectedSetKeys.delete(key);
    } else {
        el.classList.add('active');
        el.style.borderColor = 'var(--accent)';
        el.style.background = 'var(--accent)';
        el.style.color = '#fff';
        el.style.fontWeight = '600';
        selectedSetKeys.add(key);
    }
    applySelectedSets();
}
function selectAllSets() {
    document.querySelectorAll('#setToggles .set-toggle').forEach(el => {
        el.classList.add('active');
        el.style.borderColor = 'var(--accent)';
        el.style.background = 'var(--accent)';
        el.style.color = '#fff';
        el.style.fontWeight = '600';
        selectedSetKeys.add(el.dataset.key);
    });
    applySelectedSets();
}
function deselectAllSets() {
    document.querySelectorAll('#setToggles .set-toggle').forEach(el => {
        el.classList.remove('active');
        el.style.borderColor = 'var(--border)';
        el.style.background = 'var(--card)';
        el.style.color = 'var(--text)';
        el.style.fontWeight = '';
    });
    selectedSetKeys.clear();
    slides = []; renderSlides();
    document.getElementById('cfgStatus').textContent = '已清空';
}

function applySelectedSets() {
    if (!configData || selectedSetKeys.size === 0) { slides = []; renderSlides(); return; }

    const baseDuration = parseFloat(document.getElementById('defaultDuration').value) || 3;
    const newSlides = [];

    selectedSetKeys.forEach(setKey => {
        const setInfo = configData.sets[setKey];
        if (!setInfo) return;
        for (let i = 0; i < setInfo.panels.length; i++) {
            const panel = setInfo.panels[i];
            if (!panel.path) continue;
            newSlides.push({
                id: 'cfg_' + setKey + '_' + i + '_' + Math.random().toString(36).slice(2,8),
                dataUrl: '/api/file-image?path=' + encodeURIComponent(panel.path),
                text: panel.subtitle_cn || panel.prompt,
                duration: baseDuration,
                path: panel.path,
                name: panel.path.split(/[\\\/]/).pop(),
            });
        }
    });

    if (newSlides.length === 0) { alert('所选风格下没有图片'); return; }
    slides = newSlides;
    renderSlides();
    document.getElementById('cfgStatus').textContent = `已选 ${selectedSetKeys.size} 组，共 ${newSlides.length} 张`;
}

// ── TTS 操作 ──
function toggleTTSPanel() {
    const on = document.getElementById('ttsEnabled').checked;
    document.getElementById('ttsStyle').disabled = !on;
    document.getElementById('voiceVolume').disabled = !on;
    document.getElementById('btnGenAllTTS').disabled = !on;
    if (!on) { ttsSegments = {}; renderSlides(); }
}

async function generateSlideTTS(idx) {
    const slide = slides[idx];
    if (!slide || !slide.text) return;
    const style = document.getElementById('ttsStyle').value;
    const segId = 'seg_' + Date.now().toString(36) + '_' + idx;
    const genBtn = document.getElementById('ttsGenBtn_' + idx);
    const statusEl = document.getElementById('ttsStatus_' + idx);
    genBtn.disabled = true;
    genBtn.classList.add('generating');
    statusEl.textContent = '生成中...';
    statusEl.className = 'tts-status pending';
    try {
        const resp = await fetch('/api/tts/generate', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: slide.text, style: style, segment_id: segId})
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        const data = await resp.json();
        ttsSegments[idx] = {segment_id: segId, path: data.path, status: 'ok', style: style};
        statusEl.textContent = '已生成';
        statusEl.className = 'tts-status ok';
        document.getElementById('ttsPlayBtn_' + idx).style.display = '';
    } catch(e) {
        statusEl.textContent = '失败: ' + e.message;
        statusEl.className = 'tts-status err';
    } finally {
        genBtn.disabled = false;
        genBtn.classList.remove('generating');
    }
}

function playSlideTTS(idx) {
    const seg = ttsSegments[idx];
    if (!seg || !seg.segment_id) return;
    const audio = new Audio('/api/tts/audio/' + seg.segment_id);
    audio.play();
}

async function generateAllTTS() {
    if (slides.length === 0) return;
    const style = document.getElementById('ttsStyle').value;
    const segments = slides.map((s, i) => ({
        text: s.text, style: style,
        segment_id: ttsSegments[i]?.segment_id || ('seg_' + Date.now().toString(36) + '_' + i)
    }));
    const statusEl = document.getElementById('ttsBatchStatus');
    const btn = document.getElementById('btnGenAllTTS');
    btn.disabled = true;
    statusEl.textContent = '提交中...';
    try {
        const resp = await fetch('/api/tts/generate-all', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({segments: segments})
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
        const data = await resp.json();
        pollTTSProgress(data.batch_id, segments);
    } catch(e) {
        statusEl.textContent = '失败: ' + e.message;
        btn.disabled = false;
    }
}

async function pollTTSProgress(batchId, segments) {
    const statusEl = document.getElementById('ttsBatchStatus');
    const btn = document.getElementById('btnGenAllTTS');
    const poll = async () => {
        try {
            const resp = await fetch('/api/tts/progress?batch_id=' + batchId);
            if (!resp.ok) { setTimeout(poll, 2000); return; }
            const data = await resp.json();
            const total = data.total || 0;
            const done = data.done || 0;
            const failed = data.failed || 0;
            statusEl.textContent = `${done+failed}/${total} (成功${done}, 失败${failed})`;
            if (data.status === 'done') {
                // Update ttsSegments with results
                if (data.results) {
                    for (const r of data.results) {
                        const idx = segments.findIndex(s => s.segment_id === r.segment_id);
                        if (idx >= 0) {
                            ttsSegments[idx] = {
                                segment_id: r.segment_id,
                                path: r.path,
                                status: r.ok ? 'ok' : 'err',
                                style: segments[idx].style
                            };
                        }
                    }
                }
                renderSlides();
                btn.disabled = false;
                return;
            }
            setTimeout(poll, 2000);
        } catch(e) { statusEl.textContent = '查询失败'; btn.disabled = false; }
    };
    poll();
}

// ── 生成 ──
async function generateVideo() {
    if (slides.length === 0) return;

    const btn = document.getElementById('btnGenerate');
    const progressWrap = document.getElementById('progressWrap');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const resultWrap = document.getElementById('resultWrap');

    btn.disabled = true;
    progressWrap.classList.add('show');
    resultWrap.classList.remove('show');
    progressFill.style.width = '10%';
    progressText.textContent = '上传图片中...';

    // 区分本地文件和上传文件
    const localPaths = [];
    const uploadFiles = [];
    const localTexts = [];   // 与 localPaths 对齐
    const localDurations = [];
    const uploadTexts = [];  // 与 uploadFiles 对齐
    const uploadDurations = [];

    for (const s of slides) {
        if (s.path) {
            localPaths.push(s.path);
            localTexts.push(s.text);
            localDurations.push(s.duration);
        } else if (s.file) {
            uploadFiles.push(s.file);
            uploadTexts.push(s.text);
            uploadDurations.push(s.duration);
        }
    }

    const formData = new FormData();
    for (const f of uploadFiles) { formData.append('files', f); }
    formData.append('texts', JSON.stringify(uploadTexts));
    formData.append('durations', JSON.stringify(uploadDurations));
    formData.append('local_paths', JSON.stringify(localPaths));
    formData.append('local_texts', JSON.stringify(localTexts));
    formData.append('local_durations', JSON.stringify(localDurations));
    formData.append('font_size', document.getElementById('fontSize').value);
    formData.append('text_color', document.getElementById('textColor').value);
    formData.append('text_bg', document.getElementById('textBg').value);
    formData.append('fade_duration', document.getElementById('fadeDuration').value);
    formData.append('fps', document.getElementById('fps').value);
    formData.append('layout_mode', viewSize);
formData.append('layout_mode', viewSize);
    formData.append('tts_enabled', document.getElementById('ttsEnabled').checked ? 'true' : 'false');
    formData.append('tts_style', document.getElementById('ttsStyle').value);
    formData.append('voice_volume', (parseInt(document.getElementById('voiceVolume').value) || 100) / 100);
    formData.append('music_volume', (parseInt(document.getElementById('musicVolume').value) || 30) / 100);
    // Build tts_segment_ids array
    const ttsIds = [];
    for (let i = 0; i < slides.length; i++) {
        ttsIds.push(ttsSegments[i]?.segment_id || '');
    }
    formData.append('tts_segment_ids', JSON.stringify(ttsIds));

    progressFill.style.width = '30%';
    progressText.textContent = '正在生成视频...';

    try {
        const resp = await fetch('/api/generate', { method: 'POST', body: formData });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '生成失败');
        }
        const data = await resp.json();

        progressFill.style.width = '100%';
        progressText.textContent = '完成！';

        // 显示结果
        resultWrap.classList.add('show');
        document.getElementById('resultCard').innerHTML = `
            <video controls src="/api/download/${data.filename}"></video>
            <div class="info">
                文件: ${data.filename} · 大小: ${data.size_mb} MB · 
                <a href="/api/download/${data.filename}" download>点击下载</a>
            </div>
        `;
    } catch (e) {
        progressText.textContent = '错误: ' + e.message;
        progressFill.style.background = '#e94560';
    } finally {
        btn.disabled = false;
    }
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE


@app.post("/api/generate")
async def generate_video(
    files: list[UploadFile] = File(default=[]),
    texts: str = Form("[]"),
    durations: str = Form("[]"),
    local_paths: str = Form("[]"),
    local_texts: str = Form("[]"),
    local_durations: str = Form("[]"),
    font_size: int = Form(36),
    text_color: str = Form("#ffffff"),
    text_bg: str = Form("semi"),
    fade_duration: float = Form(0.3),
    fps: int = Form(24),
    layout_mode: str = Form("medium"),
    tts_enabled: str = Form("false"),
    tts_style: str = Form("gentle_female"),
    tts_segment_ids: str = Form("[]"),
    voice_volume: float = Form(1.0),
    music_track: str = Form(""),
    music_volume: float = Form(0.3),
):
    """接收图片和参数，生成视频"""
    tts_enabled_bool = tts_enabled.lower() in ("true", "1", "yes")
    tts_segment_ids_list = json.loads(tts_segment_ids)
    upload_texts_list = json.loads(texts)
    upload_durations_list = json.loads(durations)
    local_paths_list = json.loads(local_paths)
    local_texts_list = json.loads(local_texts)
    local_durations_list = json.loads(local_durations)

    if not files and not local_paths_list:
        raise HTTPException(400, "请至少添加一张图片")

    # 收集所有图片路径
    all_image_paths = list(local_paths_list)  # 本地文件直接用原路径
    all_texts = list(local_texts_list)
    all_durations = list(local_durations_list)

    # 保存上传图片
    if files:
        task_id = uuid.uuid4().hex[:12]
        task_dir = UPLOAD_DIR / task_id
        task_dir.mkdir()
        for i, f in enumerate(files):
            if not f or not f.filename:
                continue
            ext = Path(f.filename).suffix or ".png"
            save_path = task_dir / f"img_{i:03d}{ext}"
            with open(save_path, "wb") as out:
                shutil.copyfileobj(f.file, out)
            all_image_paths.append(str(save_path))
            # 从上传对应的 texts/durations 取，长度可能不匹配需容错
            text = upload_texts_list[i] if i < len(upload_texts_list) else ""
            dur = upload_durations_list[i] if i < len(upload_durations_list) else 3.0
            all_texts.append(text)
            all_durations.append(dur)

    # 生成视频
    output_filename = f"story_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = OUTPUT_DIR / output_filename

    try:
        # Pre-extend durations for voiceovers longer than image duration
        compose_durations = list(all_durations)
        if tts_enabled_bool and tts_segment_ids_list:
            from moviepy import AudioFileClip as _AFC2
            for i, seg_id in enumerate(tts_segment_ids_list):
                if i >= len(compose_durations):
                    break
                tts_path = TTS_DIR / f"{seg_id}.mp3"
                if tts_path.exists():
                    try:
                        tmp = _AFC2(str(tts_path))
                        if tmp.duration > compose_durations[i]:
                            compose_durations[i] = tmp.duration
                        tmp.close()
                    except Exception:
                        pass
        _compose_video(
            image_paths=all_image_paths,
            texts=all_texts,
            durations=compose_durations,
            output_path=str(output_path),
            font_size=font_size,
            text_color=text_color,
            text_bg=text_bg,
            fade_duration=fade_duration,
            fps=fps,
            layout_mode=layout_mode,
            tts_enabled=tts_enabled_bool,
            tts_segment_ids=tts_segment_ids_list,
            voice_volume=voice_volume,
            music_track=music_track,
            music_volume=music_volume,
        )
    except Exception as e:
        raise HTTPException(500, f"视频合成失败: {e}")

    file_size_mb = round(os.path.getsize(output_path) / 1024 / 1024, 2)

    return JSONResponse({
        "filename": output_filename,
        "size_mb": file_size_mb,
        "url": f"/api/download/{output_filename}",
    })


@app.get("/api/download/{filename}")
async def download_video(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path, media_type="video/mp4", filename=filename)


@app.post("/api/load-config-content")
async def load_prompt_config_content(req: Request):
    """
    与 load-config 相同，但直接接收 JSON 内容而非文件路径。
    请求体: { "json_content": "...", "img_root": "path/to/result/4/" }
    """
    body = await req.json()
    json_content = body.get("json_content", "").strip()
    img_root = body.get("img_root", "").strip()

    if not json_content:
        raise HTTPException(400, "请提供 JSON 内容")
    if not img_root:
        raise HTTPException(400, "请提供图片根目录路径")

    img_root_path = Path(img_root)
    if not img_root_path.exists() or not img_root_path.is_dir():
        raise HTTPException(400, f"图片根目录不存在: {img_root}")

    try:
        config = json.loads(json_content)
    except Exception as e:
        raise HTTPException(400, f"无法解析 JSON 内容: {e}")

    return _build_config_result(config, img_root_path)


@app.post("/api/load-config")
async def load_prompt_config(req: Request):
    """
    读取 prompts.json 并扫描图片目录。
    """
    body = await req.json()
    json_path = body.get("prompts_json", "").strip()
    img_root = body.get("img_root", "").strip()

    if not json_path:
        raise HTTPException(400, "请提供 prompts.json 路径")
    if not img_root:
        raise HTTPException(400, "请提供图片根目录路径")

    json_file = Path(json_path)
    if not json_file.exists():
        raise HTTPException(400, f"prompts.json 不存在: {json_path}")

    img_root_path = Path(img_root)
    if not img_root_path.exists() or not img_root_path.is_dir():
        raise HTTPException(400, f"图片根目录不存在: {img_root}")

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        raise HTTPException(400, f"无法解析 prompts.json: {e}")

    return _build_config_result(config, img_root_path)


def _build_config_result(config: dict, img_root_path: Path):
    """提取公共扫描逻辑"""
    sets = config.get("sets", {})
    if not sets:
        raise HTTPException(400, "prompts.json 中没有 sets 数据")

    IMG_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    result_sets = {}

    for set_key in sorted(sets.keys()):
        set_info = sets[set_key]
        set_name = set_info.get("name", set_key)
        panels = set_info.get("panels", [])
        subtitles_cn = set_info.get("subtitles_cn", [])
        set_dir = img_root_path / set_key
        existing_files = {}
        if set_dir.exists() and set_dir.is_dir():
            for f in set_dir.iterdir():
                if f.is_file() and f.suffix.lower() in IMG_EXTS:
                    existing_files[f.stem] = str(f.resolve())

        # 匹配：panel 按索引对应目录下 panelX_* 的图片
        matched_panels = []
        missing_indices = []
        for idx, prompt in enumerate(panels):
            panel_num = idx + 1
            # 查找 panel1_* 开头的文件
            matched_path = None
            for stem, path in existing_files.items():
                if stem.startswith(f"panel{panel_num}_"):
                    matched_path = path
                    break
            if matched_path:
                cn = subtitles_cn[idx] if idx < len(subtitles_cn) else ""
                matched_panels.append({"prompt": prompt, "subtitle_cn": cn, "path": matched_path, "index": idx})
            else:
                cn = subtitles_cn[idx] if idx < len(subtitles_cn) else ""
                matched_panels.append({"prompt": prompt, "subtitle_cn": cn, "path": None, "index": idx})
                missing_indices.append(panel_num)

        result_sets[set_key] = {
            "name": set_name,
            "panels": matched_panels,
            "total_panels": len(panels),
            "found_panels": len(matched_panels) - len(missing_indices),
            "missing_panels": missing_indices,
        }

    return JSONResponse({
        "sets": result_sets,
        "img_root": str(img_root_path.resolve()),
    })


@app.post("/api/scan-dir")
async def scan_directory(req: Request):
    """扫描目录，返回图片文件列表"""
    body = await req.json()
    dir_path = body.get("dir_path", "").strip()
    if not dir_path:
        raise HTTPException(400, "请提供目录路径")
    p = Path(dir_path)
    if not p.exists():
        raise HTTPException(400, f"目录不存在: {dir_path}")
    if not p.is_dir():
        raise HTTPException(400, f"不是目录: {dir_path}")

    IMG_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    files = []
    for f in sorted(p.iterdir()):
        if f.is_file() and f.suffix.lower() in IMG_EXTS:
            files.append({"name": f.name, "path": str(f.resolve())})

    return JSONResponse({"files": files, "count": len(files), "dir": str(p.resolve())})


@app.get("/api/file-image")
async def serve_file_image(path: str):
    """返回本地图片文件"""
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "文件不存在")
    # 根据扩展名设置 media_type
    ext_map = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
        '.tiff': 'image/tiff', '.tif': 'image/tiff',
    }
    media_type = ext_map.get(p.suffix.lower(), 'image/png')
    return FileResponse(str(p), media_type=media_type)


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
    tts_enabled: bool = False,
    tts_style: str = "gentle_female",
    tts_segment_ids: list = None,
    voice_volume: float = 1.0,
    music_track: str = "",
    music_volume: float = 0.3,
):
    """
    Core composition logic. Supports TTS voiceover and background music.
    - small/medium: subtitles overlaid at bottom of image
    - large: vertical layout - image on top, subtitle area below
    When tts_enabled=True, each segment's voice audio is added to the timeline.
    When music_track is set, background music is mixed in.
    """
    if tts_segment_ids is None:
        tts_segment_ids = []
    import tempfile

    if len(durations) < len(image_paths):
        durations += [3.0] * (len(image_paths) - len(durations))

    is_large = layout_mode == "large"

    annotated_dir = Path(tempfile.mkdtemp(prefix="ann_"))
    annotated_paths = []

    for i, (img_path, text) in enumerate(zip(image_paths, texts)):
        img = Image.open(img_path).convert("RGBA")

        if text.strip():
            if is_large:
                annotated = _make_vertical_layout(img, text, font_size, text_color)
            else:
                annotated = _add_text_overlay(img, text, font_size=font_size, text_color=text_color, text_bg=text_bg)
        else:
            annotated = img

        out_path = annotated_dir / f"frame_{i:03d}.png"
        annotated.convert("RGB").save(out_path, "PNG")
        annotated_paths.append(str(out_path))

    clips = []
    for i, (ann_path, dur) in enumerate(zip(annotated_paths, durations)):
        clip = ImageClip(ann_path, duration=dur)
        if fade_duration > 0 and i > 0:
            clip = clip.with_effects([vfx.FadeIn(fade_duration)])
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")

    # ── 音频合成 ──
    audio_clips = []

    if tts_enabled and tts_segment_ids:
        time_offset = 0.0
        for i, seg_id in enumerate(tts_segment_ids):
            dur = durations[i] if i < len(durations) else 3.0
            tts_path = TTS_DIR / f"{seg_id}.mp3"
            if tts_path.exists():
                try:
                    voice_clip = AudioFileClip(str(tts_path))
                    voice_dur = voice_clip.duration
                    if voice_dur > dur:
                        # Voice longer than image - extend image duration
                        dur = voice_dur
                        # Note: we cannot retroactively change clip duration here;
                        # this is handled by pre-extending durations before calling _compose_video
                    voice_clip = voice_clip.with_effects([
                        afx.MultiplyVolume(voice_volume)
                    ]).with_start(time_offset)
                    audio_clips.append(voice_clip)
                except Exception as e:
                    print(f"[compose] TTS audio load failed {seg_id}: {e}")
            time_offset += dur

    if music_track:
        music_path = Path(music_track)
        if music_path.exists():
            try:
                music_clip = AudioFileClip(str(music_path))
                # Loop music to match video duration
                final_duration = final.duration if hasattr(final, 'duration') else sum(durations)
                from moviepy import afx as afx_mod
                music_clip = music_clip.with_effects([
                    afx_mod.MultiplyVolume(music_volume)
                ])
                if music_clip.duration < final_duration:
                    music_clip = music_clip.loop(duration=final_duration)
                else:
                    music_clip = music_clip.subclipped(0, final_duration)
                audio_clips.append(music_clip)
            except Exception as e:
                print(f"[compose] Music load failed: {e}")

    if audio_clips:
        mixed_audio = CompositeAudioClip(audio_clips)
        final = final.with_audio(mixed_audio)

    final.write_videofile(output_path, fps=fps, codec="libx264", audio_codec="aac", logger=None)
    final.close()


def _make_vertical_layout(
    img: Image.Image,
    text: str,
    font_size: int = 36,
    text_color: str = "#ffffff",
) -> Image.Image:
    """
    上下结构：图片在上，字幕区在下。
    - 统一画布宽度 = 图片宽度
    - 高度 = 图片高度 + 字幕区高度
    """
    from PIL import ImageDraw, ImageFont

    font = _load_font(font_size)
    draw_tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    img_w, img_h = img.size

    margin = int(img_w * 0.05)
    max_text_w = img_w - 2 * margin
    lines = _wrap_text(draw_tmp, text, font, max_text_w)
    line_h = font_size + 6
    text_pad = font_size

    text_area_h = len(lines) * line_h + text_pad * 2

    # 创建上下结构画布
    canvas_w = img_w
    canvas_h = img_h + text_area_h
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))

    # 图片放在上部
    canvas.paste(img, (0, 0), img if img.mode == "RGBA" else None)

    # 字幕区在下部：纯黑背景
    draw = ImageDraw.Draw(canvas)

    # 绘制文字，逐行居中
    text_y = img_h + text_pad
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (canvas_w - line_w) // 2
        draw.text((x, text_y), line, fill=text_color, font=font)
        text_y += line_h

    return canvas


def _add_text_overlay(
    img: Image.Image,
    text: str,
    font_size: int = 36,
    text_color: str = "#ffffff",
    text_bg: str = "semi",
) -> Image.Image:
    """在图片底部叠加字幕条"""
    from PIL import ImageDraw, ImageFont

    w, h = img.size

    # 尝试加载中文字体
    font = _load_font(font_size)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    margin = int(w * 0.05)
    max_text_width = w - 2 * margin

    # 换行处理
    lines = _wrap_text(draw, text, font, max_text_width)

    line_height = font_size + 6
    text_block_height = len(lines) * line_height
    bg_padding = font_size // 2

    # 背景条
    bg_top = h - text_block_height - bg_padding * 2 - margin
    bg_bottom = h - margin
    bg_left = 0
    bg_right = w

    if text_bg == "semi":
        bg_color = (0, 0, 0, 160)
    elif text_bg == "solid":
        bg_color = (0, 0, 0, 255)
    else:
        bg_color = None

    if bg_color:
        draw.rectangle(
            [bg_left, bg_top, bg_right, bg_bottom],
            fill=bg_color,
        )

    # 逐行绘制文字
    text_y = h - text_block_height - bg_padding - margin
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (w - line_w) // 2
        draw.text((x, text_y), line, fill=text_color, font=font)
        text_y += line_height

    result = Image.alpha_composite(img, overlay)
    return result


def _wrap_text(draw, text: str, font, max_width: int) -> list:
    """简单中文换行"""
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _load_font(font_size: int):
    """按优先级加载中文字体"""
    from PIL import ImageFont

    font_paths = [
        # Windows
        "C:/Windows/Fonts/msyh.ttc",       # 微软雅黑
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",     # 黑体
        "C:/Windows/Fonts/simsun.ttc",     # 宋体
        "C:/Windows/Fonts/STKAITI.TTF",    # 楷体
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, font_size)
            except Exception:
                continue
    # 兜底
    return ImageFont.load_default()


# ── 配置 ──
@app.get("/api/config")
async def get_config():
    """读取配置文件"""
    if CONFIG_FILE.exists():
        return JSONResponse(content=json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    return JSONResponse(content={})


@app.put("/api/config")
async def save_config(data: dict):
    """保存配置文件"""
    existing = {}
    if CONFIG_FILE.exists():
        existing = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    existing.update(data)
    CONFIG_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# TTS 语音功能
# ════════════════════════════════════════════════════════════

async def _generate_tts_audio(text: str, voice_shortname: str, segment_id: str) -> str:
    """Call edge-tts to generate audio, returns mp3 file path. Returns empty string on failure."""
    import edge_tts
    output_path = TTS_DIR / f"{segment_id}.mp3"
    if output_path.exists():
        return str(output_path)
    communicate = edge_tts.Communicate(text, voice_shortname)
    try:
        await communicate.save(str(output_path))
        return str(output_path)
    except Exception as e:
        print(f"[TTS] generate failed segment_id={segment_id}: {e}")
        return ""


@app.post("/api/tts/generate")
async def tts_generate(req: Request):
    body = await req.json()
    text = body.get("text", "").strip()
    style = body.get("style", "gentle_female")
    segment_id = body.get("segment_id", "").strip()
    if not text or not segment_id:
        raise HTTPException(400, "text and segment_id required")
    voice = TTS_VOICES.get(style, TTS_VOICES["gentle_female"])
    path = await _generate_tts_audio(text, voice, segment_id)
    if not path:
        raise HTTPException(500, "TTS generate failed")
    return JSONResponse({"segment_id": segment_id, "path": path, "size": os.path.getsize(path), "style": style})


@app.post("/api/tts/generate-all")
async def tts_generate_all(req: Request):
    body = await req.json()
    segments = body.get("segments", [])
    if not segments:
        raise HTTPException(400, "segments cannot be empty")
    total = len(segments)
    batch_id = uuid.uuid4().hex[:12]
    with _progress_lock:
        _batch_progress[batch_id] = {"total": total, "done": 0, "failed": 0}

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = []
        for i, seg in enumerate(segments):
            text = seg.get("text", "").strip()
            style = seg.get("style", "gentle_female")
            seg_id = seg.get("segment_id", f"seg_{i:03d}")
            voice = TTS_VOICES.get(style, TTS_VOICES["gentle_female"])
            try:
                path = loop.run_until_complete(_generate_tts_audio(text, voice, seg_id))
                if path:
                    results.append({"segment_id": seg_id, "path": path, "ok": True})
                    with _progress_lock:
                        _batch_progress[batch_id]["done"] += 1
                else:
                    results.append({"segment_id": seg_id, "path": "", "ok": False})
                    with _progress_lock:
                        _batch_progress[batch_id]["failed"] += 1
            except Exception as e:
                results.append({"segment_id": seg_id, "path": "", "ok": False, "error": str(e)})
                with _progress_lock:
                    _batch_progress[batch_id]["failed"] += 1
        loop.close()
        with _progress_lock:
            _batch_progress[batch_id]["status"] = "done"
            _batch_progress[batch_id]["results"] = results
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return JSONResponse({"batch_id": batch_id, "total": total})


@app.get("/api/tts/progress")
async def tts_progress(batch_id: str = ""):
    if not batch_id:
        raise HTTPException(400, "batch_id required")
    with _progress_lock:
        progress = _batch_progress.get(batch_id)
    if progress is None:
        raise HTTPException(404, "batch_id not found")
    return JSONResponse(progress)


@app.get("/api/tts/audio/{segment_id}")
async def tts_get_audio(segment_id: str):
    path = TTS_DIR / f"{segment_id}.mp3"
    if not path.exists():
        raise HTTPException(404, "audio file not found")
    return FileResponse(str(path), media_type="audio/mpeg")


@app.delete("/api/tts/audio/{segment_id}")
async def tts_delete_audio(segment_id: str):
    path = TTS_DIR / f"{segment_id}.mp3"
    if not path.exists():
        raise HTTPException(404, "audio file not found")
    os.remove(path)
    return {"ok": True}

# ── 启动 ──
if __name__ == "__main__":
    print(f"启动服务: http://127.0.0.1:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
