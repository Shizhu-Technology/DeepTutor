# Voice Chat 端到端方案

## 目标
客户端上传一段语音，服务端返回：识别文本、DeepTutor 回复文本、以及回复语音。

## 数据流
```text
音频 -> POST /api/voice/chat
  -> STT: DashScope qwen-audio-3.1-asr-flash-streaming
  -> DeepTutor chat ( capability=chat, persona=可选 )
  -> TTS: MiniMax speech-2.8-hd
  -> JSON { transcript, reply, audio_base64, audio_content_type, session_id, turn_id }
```

## 新增/修改代码
- `deeptutor/services/voice/adapters/dashscope_qwen.py` — Qwen streaming ASR 适配器
- `deeptutor/services/voice/adapters/__init__.py` — 注册新适配器
- `deeptutor/services/config/provider_runtime.py` — 添加 `dashscope_qwen` STT provider
- `deeptutor/api/routers/voice_chat.py` — `/api/voice/chat` 端点
- `deeptutor/modules/manifests/server.json` — 注册 voice_chat 路由
- `requirements/modules/providers.txt` — dashscope>=2.0.0

## 配置（data/user/settings/model_catalog.json）
已写入本地运行时的 model_catalog.json（gitignored），部署时需要把对应片段复制到服务器：
- LLM: binding=`openai`, base_url=`https://api.minimax.chat/v1`, model=`MiniMax-M3`
- TTS: binding=`minimax`, base_url=`https://api.minimax.chat/v1`, model=`speech-2.8-hd`, voice=`male-qn-qingse` 等
- STT: binding=`dashscope_qwen`, model=`qwen-audio-3.1-asr-flash-streaming`

## 系统提示词
通过 Persona 机制配置：
1. `POST /api/personas { name: "tutor", content: "系统提示词..." }`
2. 调用 voice chat 时 `persona=tutor`

## 依赖
- ffmpeg：STT 音频归一化需要（容器可设置 `DEEPTUTOR_APT_PACKAGES=ffmpeg`）
- dashscope>=2.0.0

## 部署运行
```bash
# 本地
deeptutor serve

# Docker
deeptutor docker compose up
```

## 测试
```bash
# STT
curl -F "file=@test.mp3" http://localhost:8001/api/voice/stt

# TTS
curl -X POST http://localhost:8001/api/voice/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"你好"}' --output out.mp3

# 端到端
curl -X POST http://localhost:8001/api/voice/chat \
  -F "audio=@test.mp3" -F "persona=tutor"
```
