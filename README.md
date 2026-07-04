<div align="center">

# 🩺 AI Config Doctor

**A configuration doctor and guided setup tool for Codex and Claude Code third-party API providers.**

[简体中文](./README.zh-CN.md) · English

[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)](#quick-start)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)
[![Author](https://img.shields.io/badge/by-docode.cc-orange)](https://docode.cc)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Configuration checks** | Validates `base_url`, API keys, model fields, and common connection issues. |
| 🛠️ **Guided setup** | Walks users through API URL, key/token, and model configuration, then writes local config files automatically. |
| 📦 **Install guide** | Detects Node.js/npm and installs Codex CLI or Claude CLI when needed. |
| 🔁 **Session resume** | Scans local Codex / Claude Code sessions, shows summaries, and generates or runs resume commands. |
| 🎨 **Adaptive terminal theme** | Automatically adapts colors for light and dark terminal backgrounds. |

---

## 📸 Screenshot

> *(Terminal screenshot coming soon.)*

---

## 🚀 Quick Start

### Option 1: Download a prebuilt binary

Go to the [Releases](../../releases) page and download the file for your platform:

| Platform | File |
|---|---|
| macOS Apple Silicon | `ai-config-doctor-macos-arm64` |
| macOS Intel | `ai-config-doctor-macos-x64` |
| Windows x64 | `ai-config-doctor-windows-x64.exe` |
| Linux x64 | `ai-config-doctor-linux-x64` |

**macOS / Linux:**

```bash
chmod +x ai-config-doctor-macos-arm64
./ai-config-doctor-macos-arm64
```

**Windows:**

Double-click `ai-config-doctor-windows-x64.exe`.

---

### Option 2: Run from source

Requires Python 3.8+. No third-party Python dependencies are required.

```bash
git clone https://github.com/docodecc/AI-Config-Doctor.git
cd AI-Config-Doctor
python3 check_codex.py
```

---

## 📋 Main Menu

```text
Select an action. Press Enter to check Codex config by default.

  Configuration checks
    1  Check Codex config        Fixes 95% of connection issues
    2  Check Claude Code config  Fixes 95% of connection issues

  Install guide
    3  Install Codex Desktop
    4  Install Codex CLI
    5  Install Claude CLI

  Session resume
    6  Resume Codex session
    7  Resume Claude Code session

    0  Exit
```

---

## 🔎 What It Checks

### Codex (`~/.codex/`)

| File | Checks |
|---|---|
| `config.toml` | Exists, `base_url` format, non-local API URL, `model` field. |
| `auth.json` | Exists and contains a non-empty `OPENAI_API_KEY`. |

### Claude Code (`~/.claude/`)

| File | Checks |
|---|---|
| `settings.json` | `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`. |

---

## 🧭 Guided Configuration

After a config check, you can choose how much to update:

```text
  1  Update everything: API URL, Key/Token, and models
  2  Update URL only
  3  Update Key/Token only
  4  Fetch latest models and choose
  0  Back to main menu
```

Notes:

- Local API URLs such as `localhost`, `127.0.0.1`, `0.0.0.0`, and LAN IPs are rejected because they usually cannot work as third-party cloud API endpoints.
- Claude Code uses two model fields:
  - `ANTHROPIC_MODEL`: primary model, usually Sonnet/Opus or a stronger model.
  - `ANTHROPIC_SMALL_FAST_MODEL`: small/fast model, usually Haiku or a cheaper/faster model.
- When API URL and Key/Token are available, the tool can fetch model lists from OpenAI-compatible and Anthropic-compatible endpoints.

---

## 📦 Install Guide

Choose `3`, `4`, or `5` from the main menu.

The install guide will:

1. Detect whether the target tool is already installed.
2. Detect whether Node.js/npm are available.
3. If Node.js is missing, try to install it via the system package manager:
   - macOS: `brew install node`
   - Windows: `winget install OpenJS.NodeJS.LTS`
   - Linux: `apt-get`, `dnf`, `yum`, or `pacman` in detection order
4. Run `npm install -g <package-name>`.
5. Enter the configuration wizard immediately after installation.

### Does `npm install -g <package-name>` install the latest version?

Yes, if no version is specified, npm installs the package's `latest` dist-tag by default.

For example:

```bash
npm install -g @openai/codex
npm install -g @anthropic-ai/claude-code
```

These are equivalent to installing `@latest` in normal npm behavior:

```bash
npm install -g @openai/codex@latest
npm install -g @anthropic-ai/claude-code@latest
```

If you ever need a fixed version, use `package@version`, such as:

```bash
npm install -g @openai/codex@1.2.3
```

---

## 🔁 Session Resume

AI Config Doctor can scan local session history and generate resume commands.

- **Codex**: scans `~/.codex/sessions` and `~/.codex/archived_sessions`, then resumes with `codex resume <session_id>`.
- **Claude Code**: scans `~/.claude/projects`, then resumes with `claude --resume <session_id>`.

The tool shows the latest 20 sessions with timestamp, project path, and summary so you can identify the conversation you want to continue. After selecting a session, you can either run the resume command in the current terminal or copy it manually.

---

## 🗂️ Config File Examples

**`~/.codex/config.toml`**

```toml
model_provider = "custom"
model = "gpt-4.1"

[model_providers.custom]
name = "custom"
base_url = "https://your-api.com/v1"
wire_api = "responses"
requires_openai_auth = true
```

**`~/.codex/auth.json`**

```json
{
  "OPENAI_API_KEY": "sk-xxxxxxxxxxxxxxxx"
}
```

**`~/.claude/settings.json`**

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-ant-xxxxxxxxxxxxxxxx",
    "ANTHROPIC_BASE_URL": "https://your-api.com",
    "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_SMALL_FAST_MODEL": "claude-haiku-4-5"
  }
}
```

---

## 🎨 Terminal Theme

Colors adapt to light and dark terminal backgrounds automatically. You can also force a theme:

```bash
AI_CONFIG_DOCTOR_THEME=light python3 check_codex.py
AI_CONFIG_DOCTOR_THEME=dark  python3 check_codex.py
```

---

## 🔧 Build Locally

```bash
pip install pyinstaller
pyinstaller --onefile --name "ai-config-doctor" check_codex.py
```

The output will be in `dist/`.

> PyInstaller binaries should be built on the target platform. Build macOS binaries on macOS, Windows binaries on Windows, and Linux binaries on Linux.

---

## 🛠️ Technical Notes

- Python 3.8+, standard library only.
- Lightweight TOML parser for the subset needed by Codex config.
- Cross-platform ANSI colors, with Windows ANSI support enabled via `os.system("")`.
- Model fetching supports OpenAI-style Bearer auth and Anthropic-style `x-api-key` auth.
- Common model endpoint paths and provider subpaths are detected automatically.

---

## ⚖️ License and Disclaimer

This project is open-sourced under the [MIT License](./LICENSE).

Disclaimer:

- The software is provided "as is", without warranty of any kind.
- You are responsible for any consequences of using this tool, including misconfiguration, data loss, or account restrictions.
- The tool does not store or upload API keys or session data. It only reads and writes local configuration files.
- This project is not an official product of OpenAI, Anthropic, Codex, or Claude Code.

Attribution is appreciated:

```text
AI Config Doctor by docode.cc
```

---

## License

MIT © [docode.cc](https://docode.cc)

---

<div align="center">

**AI Config Doctor is built by [docode.cc](https://docode.cc).**

If you have questions or suggestions, please open an Issue or visit [docode.cc](https://docode.cc).

</div>
