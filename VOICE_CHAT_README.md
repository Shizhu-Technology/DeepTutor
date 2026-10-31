# DeepTutor 语音对话接入（开发速查）

数据流：
```
音频 → STT（百炼 qwen-audio-3.1-asr-flash-streaming）
    → DeepTutor chat（可配 persona）
    → TTS（MiniMax speech-2.8-hd）
    → 音频 / JSON
```

## 一键安装

```bash
cd ~/DeepTutor
./setup_voice_chat.sh          # 安装依赖、ffmpeg、写配置并启动服务
./setup_voice_chat.sh --no-start   # 只安装配置
```

> 脚本已内置 API Key；生产环境请改由环境变量注入并重新生成 Key。

服务启动后：`http://localhost:8001`

## 接口

```text
POST /api/voice/chat
Content-Type: multipart/form-data
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `audio` | 是 | mp3 / wav / webm / m4a / ogg / flac / aac |
| `persona` | 否 | 系统提示词 persona，默认 `tutor` |
| `session_id` | 否 | DeepTutor 会话 ID |
| `language` | 否 | `zh` / `en` |

## 返回 JSON（默认）

```bash
curl -X POST "http://localhost:8001/api/voice/chat" \
  -F "audio=@voice.mp3" \
  -F "persona=tutor"
```

```json
{
  "session_id": "ses_xxx",
  "turn_id": "turn_xxx",
  "transcript": "你好，能帮我讲傅里叶变换吗？",
  "reply": "当然可以！傅里叶变换是把时域信号……",
  "audio_base64": "SUQzBAAAAAA...",
  "audio_content_type": "audio/mpeg"
}
```

## 返回音频流

```bash
curl -X POST "http://localhost:8001/api/voice/chat?output=audio" \
  -F "audio=@voice.mp3" \
  --output reply.mp3
```

响应头：`X-Session-Id`、`X-Turn-Id`、`X-Transcript`、`X-Reply`。

## 认证

接口默认需要 DeepTutor 登录 session（`auth: learning`）。外部匿名调用请：

1. 先登录获取 token；或
2. 临时把 `deeptutor/modules/manifests/server.json` 中该路由的 `auth` 改为 `public`。

## Persona

默认文件：`data/user/workspace/personas/tutor/PERSONA.md`

改这里即可调整系统提示词；调用时传 `persona=tutor`。

## 常见问题

- **ffmpeg 报错**：安装 ffmpeg，Docker 中设置 `DEEPTUTOR_APT_PACKAGES=ffmpeg`。
- **STT 模型不支持**：确认使用 `qwen-audio-3.1-asr-flash-streaming`。
- **无音频返回**：检查 TTS 配置、MiniMax 余额、网络连通性。

## 相关文件

- 路由：`deeptutor/api/routers/voice_chat.py`
- STT 适配器：`deeptutor/services/voice/adapters/dashscope_qwen.py`
- 路由注册：`deeptutor/modules/manifests/server.json`
- 安装脚本：`setup_voice_chat.sh`
