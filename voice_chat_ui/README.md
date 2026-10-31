# DeepTutor 语音对话简单 UI

一个纯浏览器前端：录音 → 调用 DeepTutor 语音接口 → 自动播放并显示文字回复。

## 启动

1. 启动 DeepTutor 后端：

```bash
cd ~/DeepTutor
deeptutor serve --port 8001
```

2. 启动这个 UI：

```bash
cd ~/DeepTutor/voice_chat_ui
python3 run.py
```

3. 浏览器打开：http://localhost:8080

## 认证

本地测试最简单的方式是把 `deeptutor/modules/manifests/server.json` 里 voice 路由的 `auth` 改为 `public`。

如果需要认证，可以设置环境变量让代理代发：

```bash
DEEPTUTOR_TOKEN="你的 DeepTutor token" python3 run.py
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPTUTOR_URL` | `http://localhost:8001` | DeepTutor 后端地址 |
| `VOICE_UI_PORT` | `8080` | UI 服务端口 |
| `DEEPTUTOR_TOKEN` | 空 | 可选的 Bearer token |
