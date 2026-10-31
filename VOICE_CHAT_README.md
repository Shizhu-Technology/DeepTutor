# DeepTutor 语音对话接入指南（开发版）

一句话：客户端上传一段语音，服务端返回语音回复，中间自动走 DeepTutor chat。

```
用户音频 → STT → 文字 → DeepTutor chat → 回复文字 → TTS → 回复音频
```

---

## 1. 一键安装

在 DeepTutor 项目根目录执行：

```bash
./setup_voice_chat.sh
```

脚本会完成：

1. 安装 Python 依赖（含 `dashscope>=2.0.0`）。
2. 检查并安装 `ffmpeg`（Linux apt / macOS brew）。
3. 写入 `data/user/settings/model_catalog.json`：
   - LLM：`MiniMax-M3`
   - TTS：`MiniMax speech-2.8-hd`，音色 `male-qn-qingse`
   - STT：`qwen-audio-3.1-asr-flash-streaming`（阿里云百炼）
4. 创建默认 persona `tutor`。
5. 启动 `deeptutor serve --port 8001`。

可选参数：

```bash
./setup_voice_chat.sh --no-start   # 只安装配置，不启动服务
./setup_voice_chat.sh --no-ffmpeg  # 跳过 ffmpeg 安装检查
```

> ⚠️ 生产环境建议把脚本里的硬编码 API Key 改为读取环境变量，并重新生成 Key。

---

## 2. 核心接口

### `POST /api/voice/chat`

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `audio` | File | 是 | 用户语音文件，支持 mp3 / wav / webm / m4a / ogg / flac / aac |
| `persona` | string | 否 | 系统提示词 persona 名称，默认 `tutor` |
| `session_id` | string | 否 | DeepTutor 会话 ID，不传则新建会话 |
| `language` | string | 否 | 语言提示，例如 `zh`、`en` |
| `output` | query | 否 | `json`（默认）或 `audio` |

### 响应 A：`output=json`（默认）

`application/json`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 会话 ID |
| `turn_id` | string | 当前 turn ID |
| `transcript` | string | 语音识别文本 |
| `reply` | string | DeepTutor 文字回复 |
| `audio_base64` | string | 回复音频 base64 |
| `audio_content_type` | string | 音频 MIME，例如 `audio/mpeg` |

### 响应 B：`output=audio`

直接返回 `audio/mpeg` 音频流，额外信息放在响应头：

| 响应头 | 说明 |
|---|---|
| `X-Session-Id` | 会话 ID |
| `X-Turn-Id` | 当前 turn ID |
| `X-Transcript` | transcript 的 base64 |
| `X-Reply` | reply 的 base64 |

---

## 3. 调用示例

### curl — JSON 返回

```bash
curl -X POST "http://localhost:8001/api/voice/chat" \
  -F "audio=@/path/to/user_voice.mp3" \
  -F "persona=tutor"
```

### curl — 直接返回音频文件

```bash
curl -X POST "http://localhost:8001/api/voice/chat?output=audio" \
  -F "audio=@/path/to/user_voice.mp3" \
  -F "persona=tutor" \
  --output reply.mp3
```

### Python — 直接播放音频

```python
import base64
import requests

url = "http://localhost:8001/api/voice/chat"
with open("user_voice.mp3", "rb") as f:
    files = {"audio": ("user_voice.mp3", f, "audio/mpeg")}
    data = {"persona": "tutor"}
    r = requests.post(url, files=files, data=data)
    r.raise_for_status()
    result = r.json()
    print("识别:", result["transcript"])
    print("回复:", result["reply"])
    audio_bytes = base64.b64decode(result["audio_base64"])
    with open("reply.mp3", "wb") as out:
        out.write(audio_bytes)
```

---

## 4. 认证说明

`server.json` 中本接口默认 `auth: "learning"`，即需要登录后的 DeepTutor session/cookie。

如果是外部系统匿名调用，建议：

1. 先调用登录接口获取 token；或
2. 临时把 `deeptutor/modules/manifests/server.json` 中该路由的 `auth` 改为 `public`（注意流量安全）。

---

## 5. 系统提示词 / Persona

默认 persona 文件：`data/user/workspace/personas/tutor/PERSONA.md`

内容示例：

```markdown
# tutor

你是一位耐心、专业且友好的 AI 助教。请用中文回答，尽量简洁清晰，并在合适的时候鼓励学生独立思考。
```

调用时传 `persona=tutor` 即可使用该提示词。可新增 persona 并传入对应名称。

---

## 6. 单独调试已有接口

| 接口 | 说明 |
|---|---|
| `POST /api/voice/stt` | 单独语音识别：`curl -F "file=@voice.mp3" http://localhost:8001/api/voice/stt` |
| `POST /api/voice/tts` | 单独语音合成：`curl -X POST http://localhost:8001/api/voice/tts -d '{"text":"你好"}' --output tts.mp3` |

---

## 7. 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| STT 报 ffmpeg 错误 | 系统没有 ffmpeg | 安装 ffmpeg，或在 Docker 中设置 `DEEPTUTOR_APT_PACKAGES=ffmpeg` |
| STT 报模型不支持 | 模型名错误 | 确认使用 `qwen-audio-3.1-asr-flash-streaming` |
| LLM 报配置错误 | `model_catalog.json` 缺少 LLM | 运行 `./setup_voice_chat.sh` 或手动配置 `services.llm` |
| 返回无音频 | TTS 配置错误或 MiniMax 余额不足 | 检查 `services.tts` 与 MiniMax 账户 |

---

## 8. 代码位置

- 路由入口：`deeptutor/api/routers/voice_chat.py`
- STT 适配器：`deeptutor/services/voice/adapters/dashscope_qwen.py`
- 路由注册：`deeptutor/modules/manifests/server.json`
- 配置生成：`setup_voice_chat.sh`
- 开发分支：`feature/voice-chat-bailian-asr`
