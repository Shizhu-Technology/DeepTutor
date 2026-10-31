# DeepTutor 语音对话接入说明

一句话：客户端上传一段语音，服务端返回语音回复，中间走 DeepTutor 的 chat 能力。

```
音频 ──STT──> 文字 ──> DeepTutor chat ──> 回复文字 ──TTS──> 音频
```

---

## 1. 新增接口

### `POST /api/voice/chat`

#### 请求

multipart/form-data：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `audio` | File | 是 | 用户语音文件，支持 mp3 / wav / webm / m4a / ogg / flac / aac 等 |
| `persona` | string | 否 | DeepTutor persona 名称，用来注入系统提示词 |
| `session_id` | string | 否 | 会话 ID；不传则每次新建会话 |
| `language` | string | 否 | 语言提示，例如 `zh`、`en` |

#### 响应

`application/json`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 当前会话 ID |
| `turn_id` | string | 当前 turn ID |
| `transcript` | string | 语音识别结果 |
| `reply` | string | DeepTutor 文本回复 |
| `audio_base64` | string | 回复音频的 base64 编码 |
| `audio_content_type` | string | 音频 MIME 类型，如 `audio/mpeg` |

#### curl 示例

```bash
curl -X POST http://localhost:8001/api/voice/chat \
  -F "audio=@/path/to/user_voice.mp3" \
  -F "persona=tutor"
```

返回示例：

```json
{
  "session_id": "ses_xxx",
  "turn_id": "turn_xxx",
  "transcript": "你好，请问你能帮我讲一讲傅里叶变换吗？",
  "reply": "当然可以！傅里叶变换的核心思想是...",
  "audio_base64": "SUQzBAAAAAA...",
  "audio_content_type": "audio/mpeg"
}
```

客户端把 `audio_base64` 解码后播放即可。

---

## 2. 环境配置

### 2.1 依赖

安装代码后需要满足：

- `dashscope>=2.0.0`
- `ffmpeg`（STT 内部会把各种音频格式转成 16kHz WAV）

重新安装依赖：

```bash
cd /path/to/DeepTutor
python -m pip install -e .
# 或
python -m pip install -r requirements/full.txt
```

Docker 部署时，可在容器启动参数里加：

```bash
DEEPTUTOR_APT_PACKAGES=ffmpeg
```

### 2.2 模型目录配置

配置文件路径：`data/user/settings/model_catalog.json`

需要配置 3 个 provider：

```json
{
  "services": {
    "llm": {
      "active_profile_id": "llm-minimax",
      "active_model_id": "llm-minimax-model",
      "profiles": [
        {
          "id": "llm-minimax",
          "name": "MiniMax LLM",
          "binding": "openai",
          "base_url": "https://api.minimax.chat/v1",
          "api_key": "<你的 MiniMax Key>",
          "models": [
            { "id": "llm-minimax-model", "name": "MiniMax-M3", "model": "MiniMax-M3" }
          ]
        }
      ]
    },
    "tts": {
      "active_profile_id": "tts-minimax",
      "active_model_id": "tts-minimax-model",
      "profiles": [
        {
          "id": "tts-minimax",
          "name": "MiniMax TTS",
          "binding": "minimax",
          "base_url": "https://api.minimax.chat/v1",
          "api_key": "<你的 MiniMax Key>",
          "models": [
            {
              "id": "tts-minimax-model",
              "name": "MiniMax speech-2.8-hd",
              "model": "speech-2.8-hd",
              "voice": "male-qn-qingse",
              "response_format": "mp3"
            }
          ]
        }
      ]
    },
    "stt": {
      "active_profile_id": "stt-dashscope-qwen",
      "active_model_id": "stt-dashscope-qwen-model",
      "profiles": [
        {
          "id": "stt-dashscope-qwen",
          "name": "DashScope Qwen ASR Streaming",
          "binding": "dashscope_qwen",
          "base_url": "https://dashscope.aliyuncs.com/api/v1",
          "api_key": "<你的 DashScope Key>",
          "models": [
            {
              "id": "stt-dashscope-qwen-model",
              "name": "qwen-audio-3.1-asr-flash-streaming",
              "model": "qwen-audio-3.1-asr-flash-streaming"
            }
          ]
        }
      ]
    }
  }
}
```

> `model_catalog.json` 默认在 `data/user/settings/` 下，**不在 git 里**，部署时需要单独放到服务器对应位置，或由管理员在 DeepTutor Settings 页面手动配置。

---

## 3. 系统提示词

DeepTutor 用 **Persona** 来注入系统提示词。

### 创建 persona

```bash
curl -X POST http://localhost:8001/api/personas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "tutor",
    "description": "数学家教",
    "content": "你是一位耐心且专业的数学家教。请用中文回答，尽量简洁，鼓励学生思考。"
  }'
```

### 在语音对话中使用

调用 `/api/voice/chat` 时带上 `persona=tutor` 即可。

---

## 4. 启动服务

### 本地

```bash
cd /path/to/DeepTutor
deeptutor serve
```

### Docker

```bash
deeptutor docker compose up
```

服务启动后，接口在 `http://localhost:8001/api/voice/chat`。

---

## 5. 其他可用语音接口

除 `/api/voice/chat` 外，还保留了原来的独立接口，方便单独调试：

### STT

```bash
curl -F "file=@user_voice.mp3" http://localhost:8001/api/voice/stt
```

### TTS

```bash
curl -X POST http://localhost:8001/api/voice/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，我是 DeepTutor"}' \
  --output reply.mp3
```

---

## 6. 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| 调用 `/api/voice/stt` 报 ffmpeg 错误 | 系统缺少 ffmpeg | 安装 ffmpeg，或在 Docker 环境加 `DEEPTUTOR_APT_PACKAGES=ffmpeg` |
| STT 报 `Unsupported Qwen ASR model` | 模型名不是 streaming 版本 | 使用 `qwen-audio-3.1-asr-flash-streaming` |
| LLM 报配置错误 | `model_catalog.json` 没配 LLM | 检查 `services.llm` 配置 |
| 返回里没有音频，但 transcript 有值 | TTS 配置错误或 MiniMax key 余额不足 | 检查 `services.tts` 配置及 MiniMax 账户 |

---

## 7. 当前代码分支

功能在 `feature/voice-chat-bailian-asr`，合并到主分支后即可按上述方式使用。
