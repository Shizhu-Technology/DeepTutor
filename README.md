# DeepTutor 语音对话（Fork）

这是 [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor) 的一个 fork，在原有 DeepTutor 能力基础上新增了**端到端语音对话**功能：

- 用户上传语音
- 自动语音识别（STT）转文字
- 输入 DeepTutor chat（可配置 persona 系统提示词）
- 文字回复 + 语音合成（TTS）自动播放

语音链路：

```
音频 → 阿里云百炼 qwen-audio-3.1-asr-flash-streaming
    → DeepTutor chat
    → MiniMax speech-2.8-hd TTS
    → 音频 + 文字回复
```

---

## 快速开始

### 1. 一键安装

```bash
cd ~/DeepTutor
./setup_voice_chat.sh
```

脚本会自动安装依赖、ffmpeg，并把 MiniMax / 百炼 API Key 写入运行时配置。

### 2. 启动后端

```bash
deeptutor serve --port 8001
```

### 3. 启动语音对话 UI

```bash
cd voice_chat_ui
python3 run.py
```

浏览器打开：http://localhost:8080

点击录音 → 说话 → 页面会先显示**语音转文字结果**，然后显示 **DeepTutor 文字回复**，最后自动播放语音。

---

## 主要文件

| 文件 | 说明 |
|---|---|
| `deeptutor/api/routers/voice_chat.py` | 语音对话 API：/api/voice/chat、/api/voice/chat/reply |
| `deeptutor/services/voice/adapters/dashscope_qwen.py` | 百炼 Qwen ASR 适配器 |
| `voice_chat_ui/index.html` | 浏览器录音/对话页面 |
| `voice_chat_ui/run.py` | UI 本地服务器 + 后端代理 |
| `setup_voice_chat.sh` | 一键安装脚本 |
| `VOICE_CHAT_README.md` | 更详细的设计与配置文档 |

---

## 打包成 Android APK

也提供了极简 Android App：只有一个录音按钮，按住说话，松开后自动播放 DeepTutor 语音回复，无需额外 UI 页面。

```bash
cd mobile
# 把 www/index.html 里的后端地址改成你电脑的 IP
npx cap sync android
npx cap open android
```

然后在 Android Studio 里 Build → Build APK。手机上只要电脑后端在跑即可使用，详见 `mobile/README.md`。

## 原项目

如果想查看 DeepTutor 原版代码与文档，请访问：

👉 **https://github.com/HKUDS/DeepTutor**

本 fork 的所有语音对话改动都在分支 `feature/voice-chat-bailian-asr`。
