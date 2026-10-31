# DeepTutor Voice Android APK

极简语音交互 App：**没有录音按钮，也没有聊天页面**。只需要选择一段音频文件，App 就会：

1. 把音频发给电脑上的 DeepTutor 后端
2. 获取识别文字 + DeepTutor 回复文字
3. 自动播放语音回复

## 运行原理

App 是一个本地单页应用，通过 WiFi 直接调用电脑后端：

```
手机选择音频 → http://<PC_IP>:8001/api/voice/chat/base64
              → 后端返回文字 + base64 音频
              → App 自动播放
```

电脑端只需要启动 DeepTutor 后端，不需要再单独启动 UI 服务器。

## 前置条件

- 手机和电脑在同一 WiFi。
- 电脑已启动 DeepTutor 后端：

```bash
cd ~/DeepTutor
deeptutor serve --port 8001
```

> 注意：本接口默认 `auth: learning`。如果手机上没有登录态，请临时把 `deeptutor/modules/manifests/server.json` 中 voice 路由的 `auth` 改为 `public`，或在公网部署时自行处理认证。

## 修改后端地址

打开 `www/index.html`，把输入框默认值：

```html
<input id="backendUrl" value="http://YOUR_PC_IP:8001" ...>
```

改成你电脑的内网 IP，例如 `http://192.168.31.123:8001`。

获取电脑 IP：

```bash
ifconfig | grep "inet "
```

> 也可以不修改源码，首次在 App 里手动输入后端地址。

改完后同步：

```bash
cd mobile
npm install
npx cap sync android
```

## 构建 APK

需要安装 Android Studio。

```bash
cd mobile
npx cap open android
```

在 Android Studio 中：

1. 等待 Gradle sync 完成。
2. 点击 **Build → Build Bundle(s) / APK(s) → Build APK(s)**。
3. APK 路径：`android/app/build/outputs/apk/debug/app-debug.apk`

安装到手机后，选择任意音频文件即可触发语音对话。

## 权限

`AndroidManifest.xml` 已包含：

- `INTERNET`
- `RECORD_AUDIO`（预留，当前版本不直接录音）
- `MODIFY_AUDIO_SETTINGS`
- `usesCleartextTraffic="true"`
