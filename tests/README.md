---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f4ff5be3e1f50ff475cd88e8c986c75f_651ec4317ffa11f18018525400826444
    ReservedCode1: Irtcl68LawrI2VCMQiBdjQQsA5G868zIWq9Ys6iVWkuCiCn2PnyM2YUv9cVz1PV+o72GLPfGKPADdh09n9BHHSCzGN7MZKVgXzET0QPfbtQUOoePdMCzYAbdMND2Kyx1hLtUFXslPHweRRpedg3gv+WANgE12OI3N92cs5Y3LhMKPPjQa1BlIUJLUkA=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f4ff5be3e1f50ff475cd88e8c986c75f_651ec4317ffa11f18018525400826444
    ReservedCode2: Irtcl68LawrI2VCMQiBdjQQsA5G868zIWq9Ys6iVWkuCiCn2PnyM2YUv9cVz1PV+o72GLPfGKPADdh09n9BHHSCzGN7MZKVgXzET0QPfbtQUOoePdMCzYAbdMND2Kyx1hLtUFXslPHweRRpedg3gv+WANgE12OI3N92cs5Y3LhMKPPjQa1BlIUJLUkA=
---

# TTS 自动化测试

## 安装依赖

```bash
pip install pytest edge-tts playwright -i https://pypi.tuna.tsinghua.edu.cn/simple
playwright install chromium
```

## 运行 API 测试

```bash
pytest tests/test_tts_api.py -v
```

API 测试自动启动 Flask test client，无需单独启动服务。

## 运行 UI 测试

先启动应用服务：

```bash
python video_maker_app.py
```

再运行 UI 测试：

```bash
pytest tests/test_tts_ui.py -v
```

## 运行全部测试

```bash
pytest tests/ -v
```
*（内容由AI生成，仅供参考）*
