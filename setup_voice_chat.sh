#!/usr/bin/env bash
#
# DeepTutor 语音对话一键安装脚本
# 用法:
#   ./setup_voice_chat.sh                # 安装并启动服务
#   ./setup_voice_chat.sh --no-start     # 只安装配置，不启动服务
#   ./setup_voice_chat.sh --no-ffmpeg    # 跳过 ffmpeg 安装检查
#

set -euo pipefail

# 已硬编码的 API Key（如需替换，直接修改下面两行）
MINIMAX_KEY='sk-cp-uzM1wz0MLhFcQHS17kyC9VKq7CdqOFh-euRQx0vEp1tfShtYb3bB-RMTKteI4m7VZqL_PKl6H43ybWZYiJnAbh-zT18Kj4YlI05hpW302KUxUtLe6VKTHQ0'
DASHSCOPE_KEY='sk-ee8b75e423b345bf9d4ea059774280b5'

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$REPO_ROOT/data"
SETTINGS_DIR="$DATA_DIR/user/settings"
PERSONAS_DIR="$DATA_DIR/user/workspace/personas/tutor"

START_SERVER=1
INSTALL_FFMPEG=1

# 解析参数
for arg in "$@"; do
  case "$arg" in
    --no-start) START_SERVER=0 ;;
    --no-ffmpeg) INSTALL_FFMPEG=0 ;;
  esac
done

log() { echo "[voice-chat-setup] $*"; }

# -------------- 1. 基础检查 --------------
if [[ ! -f "$REPO_ROOT/pyproject.toml" ]]; then
  echo "请在 DeepTutor 项目根目录运行此脚本" >&2
  exit 1
fi

cd "$REPO_ROOT"

# -------------- 2. 安装 Python 依赖 --------------
log "安装 Python 依赖..."
python3 -m pip install -q --upgrade pip
python3 -m pip install -q -r requirements/full.txt
python3 -m pip install -q -e . --no-deps
python3 -m pip install -q "dashscope>=2.0.0"

# -------------- 3. 检查 / 安装 ffmpeg --------------
install_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    log "ffmpeg 已安装: $(command -v ffmpeg)"
    return 0
  fi

  if [[ "$INSTALL_FFMPEG" -eq 0 ]]; then
    log "跳过 ffmpeg 安装检查（--no-ffmpeg）"
    return 0
  fi

  log "未检测到 ffmpeg，尝试自动安装..."

  if [[ "$OSTYPE" == "linux-gnu"* ]] && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y ffmpeg
  elif [[ "$OSTYPE" == "darwin"* ]] && command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    log "无法自动安装 ffmpeg。请手动安装后重新运行。"
    log "Linux: sudo apt-get install ffmpeg"
    log "macOS: brew install ffmpeg"
    exit 1
  fi
}
install_ffmpeg

# -------------- 4. 写入模型配置 --------------
mkdir -p "$SETTINGS_DIR"
CATALOG_FILE="$SETTINGS_DIR/model_catalog.json"

if [[ -f "$CATALOG_FILE" ]]; then
  BACKUP="$CATALOG_FILE.backup.$(date +%s)"
  log "发现已有 model_catalog.json，备份到 $BACKUP"
  cp "$CATALOG_FILE" "$BACKUP"
fi

log "写入 model_catalog.json..."
export CATALOG_FILE MINIMAX_KEY DASHSCOPE_KEY
python3 - <<'PY'
import json, os
minimax_key = os.environ["MINIMAX_KEY"]
dashscope_key = os.environ["DASHSCOPE_KEY"]
catalog = {
  "version": 1,
  "connections": [],
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
          "api_key": minimax_key,
          "extra_headers": {},
          "models": [
            {"id": "llm-minimax-model", "name": "MiniMax-M3", "model": "MiniMax-M3"}
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
          "api_key": minimax_key,
          "extra_headers": {},
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
          "api_key": dashscope_key,
          "extra_headers": {},
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
path = os.environ["CATALOG_FILE"]
with open(path, "w", encoding="utf-8") as f:
    json.dump(catalog, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY

# -------------- 5. 默认 Persona --------------
log "创建默认 persona: tutor..."
mkdir -p "$PERSONAS_DIR"
cat > "$PERSONAS_DIR/PERSONA.md" <<'MD'
# tutor

你是一位耐心、专业且友好的 AI 助教。请用中文回答，尽量简洁清晰，并在合适的时候鼓励学生独立思考。
MD

# -------------- 6. 完成 / 启动 --------------
log "配置完成。"
log ""
log "测试接口:"
log "  curl -X POST http://localhost:8001/api/voice/chat \\"
log "    -F \"audio=@/path/to/your_voice.mp3\" \\"
log "    -F \"persona=tutor\""
log ""

if [[ "$START_SERVER" -eq 1 ]]; then
  log "正在启动 DeepTutor 服务..."
  log "按 Ctrl+C 停止"
  exec deeptutor serve --port 8001
else
  log "如需手动启动，请运行: deeptutor serve --port 8001"
fi
