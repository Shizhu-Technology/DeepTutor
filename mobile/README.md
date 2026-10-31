# DeepTutor Voice Android APK

这是一个用 Capacitor 套壳的 Android App，打开后全屏加载电脑上的语音对话 UI。

## 原理

Android 手机 → 连接到同一 WiFi → 访问 PC 上的 `http://<PC_IP>:8080` → 使用语音对话 UI。

PC 上需要同时运行：

```bash
# 1. DeepTutor 后端
deeptutor serve --port 8001

# 2. UI 服务器（0.0.0.0 监听，方便手机访问）
cd voice_chat_ui
python3 run.py
```

## 修改后端地址

编辑 `mobile/capacitor.config.json`，把 `YOUR_PC_IP` 改成你电脑的内网 IP：

```json
"url": "http://192.168.31.123:8080"
```

获取本机 IP：

```bash
ifconfig | grep "inet "
```

改完后执行：

```bash
cd mobile
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
2. 点击菜单 **Build → Build Bundle(s) / APK(s) → Build APK(s)**。
3. 生成的 APK 路径：`mobile/android/app/build/outputs/apk/debug/app-debug.apk`

安装到手机即可使用。

## 权限

App 已申请：

- `INTERNET`
- `RECORD_AUDIO`
- `MODIFY_AUDIO_SETTINGS`

首次录音时需要在 App 内允许麦克风权限。

## 无需网络时的替代方案

如果手机和 PC 不在同一局域网，可以把 `capacitor.config.json` 里的 `url` 改成部署到公网的服务器地址。
