#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Config Doctor
支持 Windows 10/11 和 macOS
"""

import sys
import os
import json
import platform
import re
import shutil
import subprocess
import webbrowser
from datetime import datetime
from urllib import error, request
from urllib.parse import urlparse
from pathlib import Path

CODEX_DESKTOP_URL = "https://codex.com"
NODE_DOWNLOAD_URL = "https://nodejs.org/zh-cn/download"
APP_NAME = "AI Config Doctor"
APP_SUBTITLE = "Codex / Claude Code 配置诊断与向导"

# ── 颜色支持 ──────────────────────────────────────────────
if sys.platform == "win32":
    os.system("")

BOLD   = "\033[1m"
RESET  = "\033[0m"

def _detect_light_terminal():
    forced = os.environ.get("AI_CONFIG_DOCTOR_THEME", "").strip().lower()
    if forced in ("light", "dark"):
        return forced == "light"
    colorfgbg = os.environ.get("COLORFGBG", "")
    if ";" in colorfgbg:
        try:
            bg = int(colorfgbg.split(";")[-1])
            return bg in range(7, 16) or bg == 15
        except ValueError:
            pass
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    return term_program in ("apple_terminal", "terminal.app")

LIGHT_THEME = _detect_light_terminal()

if LIGHT_THEME:
    WHITE  = "\033[38;5;16m"
    GREEN  = "\033[38;5;29m"
    RED    = "\033[38;5;160m"
    YELLOW = "\033[38;5;136m"
    CYAN   = "\033[38;5;31m"
    BLUE   = "\033[38;5;25m"
    SOFT   = "\033[38;5;24m"
    MUTED  = "\033[38;5;60m"
    DIM    = "\033[38;5;244m"
    BG_HEAD = "\033[48;5;153m"
    BG_PANEL = "\033[48;5;254m"
else:
    WHITE  = "\033[38;5;255m"
    GREEN  = "\033[38;5;114m"
    RED    = "\033[38;5;203m"
    YELLOW = "\033[38;5;220m"
    CYAN   = "\033[38;5;45m"
    BLUE   = "\033[38;5;75m"
    SOFT   = "\033[38;5;109m"
    MUTED  = "\033[38;5;245m"
    DIM    = "\033[38;5;240m"
    BG_HEAD = "\033[48;5;17m"
    BG_PANEL = "\033[48;5;236m"

BOX_OK   = "✅"
BOX_FAIL = "❌"
BOX_WARN = "⚠️ "

WIDTH = 64

def _pad(text=""):
    return text + " " * max(0, WIDTH - len(text))

def panel(text="", color=WHITE, bg=BG_PANEL):
    print(f"  {bg}{color}{_pad(text)}{RESET}")

# ── 步骤输出：先打描述，检查完在同行追加结果 ──────────────
def step(msg):
    sys.stdout.write(f"    {DIM}│{RESET} {MUTED}{msg:<26}{RESET} ")
    sys.stdout.flush()

def step_ok(detail=""):
    suffix = f"{DIM}· {detail}{RESET}" if detail else ""
    print(f"{BOX_OK} {suffix}")

def step_fail(reason=""):
    suffix = f"{DIM}· {RESET}{RED}{reason}{RESET}" if reason else ""
    print(f"{BOX_FAIL} {suffix}")

def step_warn(reason=""):
    suffix = f"{DIM}· {RESET}{YELLOW}{reason}{RESET}" if reason else ""
    print(f"{BOX_WARN} {suffix}")

def section(title):
    print()
    panel(f"  {title}", f"{BOLD}{CYAN}")
    print(f"    {DIM}{'─' * 48}{RESET}")

def header():
    print()
    panel("", WHITE, BG_HEAD)
    panel(f"  {APP_NAME}", f"{BOLD}{WHITE}", BG_HEAD)
    panel(f"  {APP_SUBTITLE}", MUTED, BG_HEAD)
    panel("", WHITE, BG_HEAD)

def footer():
    print(f"  {DIM}{'─' * WIDTH}{RESET}")
    print(f"  {MUTED}AI Config Doctor · docode.cc{RESET}")
    print(f"  {DIM}{'─' * WIDTH}{RESET}")
    print()


# ── TOML 简易解析 ──────────────────────────────────────────
def parse_toml_simple(text):
    result = {}
    current_section = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\[([^\]]+)\]$", line)
        if m:
            current_section = m.group(1).strip()
            result.setdefault(current_section, {})
            continue
        kv = re.match(r'^(\w+)\s*=\s*"([^"]*)"', line) or \
             re.match(r"^(\w+)\s*=\s*'([^']*)'", line)
        if kv:
            k, v = kv.group(1), kv.group(2)
            if current_section:
                result[current_section][k] = v
            else:
                result[k] = v
    return result


# ── 会话恢复辅助函数 ──────────────────────────────────────
def _read_head_tail_lines(path, head_count=10, tail_count=30):
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return [], []
    return lines[:head_count], lines[-tail_count:]

def _json_line(line):
    try:
        return json.loads(line)
    except Exception:
        return None

def _parse_ts(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value if value > 10_000_000_000 else value * 1000)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            return int(datetime.fromisoformat(text).timestamp() * 1000)
        except Exception:
            return None
    return None

def _format_ts(ms):
    if not ms:
        return "时间未知"
    try:
        return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "时间未知"

def _extract_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    if isinstance(value, dict):
        text = value.get("text") or value.get("content")
        return text if isinstance(text, str) else ""
    return ""

def _shorten(text, max_chars=80):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"

def _basename(path):
    try:
        return Path(path).name or path
    except Exception:
        return path

def _collect_jsonl_files(root):
    if not root.exists():
        return []
    return sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

def _title_from_project(project_dir):
    return _basename(project_dir) if project_dir else "未命名会话"

def _parse_codex_session(path):
    head, tail = _read_head_tail_lines(path)
    session_id = project_dir = title = None
    created_at = None

    for line in head:
        value = _json_line(line)
        if not isinstance(value, dict):
            continue
        created_at = created_at or _parse_ts(value.get("timestamp"))
        if value.get("type") == "session_meta":
            payload = value.get("payload") or {}
            source = payload.get("source")
            if isinstance(source, dict) and "subagent" in source:
                return None
            session_id = session_id or payload.get("id")
            project_dir = project_dir or payload.get("cwd")
            created_at = created_at or _parse_ts(payload.get("timestamp"))
        if not title and value.get("type") == "response_item":
            payload = value.get("payload") or {}
            if payload.get("type") == "message" and payload.get("role") == "user":
                title = _shorten(_extract_text(payload.get("content")), 60)

    last_active_at = None
    summary = None
    for line in reversed(tail):
        value = _json_line(line)
        if not isinstance(value, dict):
            continue
        last_active_at = last_active_at or _parse_ts(value.get("timestamp"))
        if not summary and value.get("type") == "response_item":
            payload = value.get("payload") or {}
            if payload.get("type") == "message":
                summary = _shorten(_extract_text(payload.get("content")), 100)

    session_id = session_id or path.stem
    if not session_id:
        return None
    return {
        "provider": "codex",
        "session_id": session_id,
        "title": title or _title_from_project(project_dir),
        "summary": summary or "暂无摘要",
        "project_dir": project_dir,
        "created_at": created_at,
        "last_active_at": last_active_at or created_at,
        "source_path": str(path),
        "resume_command": f"codex resume {session_id}",
    }

def _parse_claude_session(path):
    if path.name.startswith("agent-"):
        return None
    head, tail = _read_head_tail_lines(path)
    session_id = project_dir = title = None
    created_at = None

    for line in head:
        value = _json_line(line)
        if not isinstance(value, dict):
            continue
        session_id = session_id or value.get("sessionId")
        project_dir = project_dir or value.get("cwd")
        created_at = created_at or _parse_ts(value.get("timestamp"))
        if not title:
            role = value.get("type")
            message = value.get("message") or {}
            is_user = role == "user" or message.get("role") == "user"
            if is_user:
                text = _extract_text(message.get("content"))
                if text and "<local-command-caveat>" not in text and not text.strip().startswith("<command-name>"):
                    title = _shorten(text, 60)

    last_active_at = None
    summary = None
    custom_title = None
    for line in reversed(tail):
        value = _json_line(line)
        if not isinstance(value, dict):
            continue
        last_active_at = last_active_at or _parse_ts(value.get("timestamp"))
        if not custom_title and value.get("type") == "custom-title":
            custom_title = _shorten(value.get("customTitle"), 60)
        if not summary and not value.get("isMeta"):
            message = value.get("message") or {}
            text = _extract_text(message.get("content"))
            if text:
                summary = _shorten(text, 100)

    session_id = session_id or path.stem
    if not session_id:
        return None
    return {
        "provider": "claude",
        "session_id": session_id,
        "title": custom_title or title or _title_from_project(project_dir),
        "summary": summary or "暂无摘要",
        "project_dir": project_dir,
        "created_at": created_at,
        "last_active_at": last_active_at or created_at,
        "source_path": str(path),
        "resume_command": f"claude --resume {session_id}",
    }

def _scan_codex_sessions():
    codex_dir = Path.home() / ".codex"
    files = []
    for root in (codex_dir / "sessions", codex_dir / "archived_sessions"):
        files.extend(_collect_jsonl_files(root))
    sessions = [s for path in files if (s := _parse_codex_session(path))]
    return sorted(sessions, key=lambda x: x.get("last_active_at") or 0, reverse=True)

def _scan_claude_sessions():
    root = Path.home() / ".claude" / "projects"
    sessions = [s for path in _collect_jsonl_files(root) if (s := _parse_claude_session(path))]
    return sorted(sessions, key=lambda x: x.get("last_active_at") or 0, reverse=True)

def _print_session_list(sessions, limit=20):
    for index, session in enumerate(sessions[:limit], 1):
        print(f"\n    {BOLD}{CYAN}{index}{RESET}  [{_format_ts(session.get('last_active_at'))}] {_shorten(session.get('title'), 56)}")
        print(f"       {DIM}{session.get('project_dir') or '项目路径未知'}{RESET}")
        print(f"       {MUTED}摘要：{_shorten(session.get('summary'), 88)}{RESET}")

def _handle_resume_session(provider_name, sessions):
    if not sessions:
        print(f"\n    {YELLOW}没有找到可恢复的 {provider_name} 会话。{RESET}")
        print(f"    {MUTED}请先运行一次对应 CLI，并完成至少一轮对话。{RESET}\n")
        return

    limit = min(20, len(sessions))
    print(f"\n  {MUTED}已找到 {len(sessions)} 个会话，默认展示最近 {limit} 个。{RESET}")
    print(f"  {MUTED}请根据时间、项目路径和摘要选择你想恢复的对话。{RESET}")
    _print_session_list(sessions, limit)
    print(f"\n    {BOLD}{CYAN}0{RESET}  返回主菜单\n")

    choice = _ask("请选择要恢复的会话序号")
    if not choice or choice == "0":
        print(f"\n    {DIM}已返回主菜单。{RESET}\n")
        return
    if not choice.isdigit() or not (1 <= int(choice) <= limit):
        print(f"\n    {YELLOW}序号无效，已返回主菜单。{RESET}\n")
        return

    session = sessions[int(choice) - 1]
    command = session["resume_command"]
    print(f"\n  {BOLD}{WHITE}恢复指导{RESET}")
    print(f"    {MUTED}你选择的会话：{session.get('title')}{RESET}")
    print(f"    {MUTED}项目目录：{session.get('project_dir') or '未知'}{RESET}")
    print(f"    {MUTED}恢复命令：{RESET}{CYAN}{command}{RESET}")
    print(f"\n    {BOLD}{CYAN}1{RESET}  在当前终端执行恢复命令")
    print(f"    {BOLD}{CYAN}2{RESET}  只显示命令，稍后手动复制执行")
    print(f"    {BOLD}{CYAN}0{RESET}  返回主菜单\n")
    action = _ask("请选择恢复方式")
    if action == "1":
        cwd = session.get("project_dir") or None
        if cwd and not Path(cwd).exists():
            print(f"\n    {BOX_WARN} {YELLOW}项目目录已不存在：{cwd}{RESET}")
            print(f"    {MUTED}将在当前终端目录下执行恢复命令。{RESET}")
            cwd = None
        print(f"\n    {DIM}正在执行：{command}{RESET}\n")
        try:
            subprocess.run(command.split(), cwd=cwd)
        except FileNotFoundError:
            print(f"\n    {RED}命令不存在，请先安装对应 CLI。{RESET}")
            print(f"    {MUTED}你也可以手动执行：{command}{RESET}\n")
        except Exception as e:
            print(f"\n    {RED}执行失败：{e}{RESET}")
            print(f"    {MUTED}你也可以手动执行：{command}{RESET}\n")
    elif action == "2":
        print(f"\n    {CYAN}{command}{RESET}")
        if session.get("project_dir"):
            print(f"    {MUTED}建议先进入项目目录：cd {session['project_dir']}{RESET}\n")
    else:
        print(f"\n    {DIM}已返回主菜单。{RESET}\n")


# ── Codex 检查 ─────────────────────────────────────────────
def check_codex(errors):
    codex_dir = Path.home() / ".codex"

    section("Codex 配置")

    step("配置目录是否存在")
    if not codex_dir.exists():
        step_fail(f"目录不存在: {codex_dir}")
        errors.append("Codex 配置目录缺失，请先安装并运行一次 codex")
        return
    step_ok(str(codex_dir))

    # config.toml
    config_path = codex_dir / "config.toml"
    step("config.toml 是否存在")
    if not config_path.exists():
        step_fail("文件不存在")
        errors.append("缺少 ~/.codex/config.toml，请参考文档创建该文件")
    else:
        step_ok()
        try:
            data = parse_toml_simple(config_path.read_text(encoding="utf-8"))
            base_url, provider_section = None, None

            active = data.get("model_provider", "")
            if active:
                sec = f"model_providers.{active}"
                if isinstance(data.get(sec), dict):
                    base_url = data[sec].get("base_url")
                    provider_section = sec
            if not base_url:
                for k, v in data.items():
                    if k.startswith("model_providers.") and isinstance(v, dict) and v.get("base_url"):
                        base_url, provider_section = v["base_url"], k
                        break
            if not base_url:
                base_url = (data.get("provider") or {}).get("base_url") or data.get("base_url")
                if base_url:
                    provider_section = "provider"

            step("base_url 是否配置")
            _validate_base_url(base_url, errors, "Codex base_url")

            step("model 是否配置")
            model = data.get("model")
            if model:
                step_ok(model)
            else:
                step_warn("未设置（可选，建议填写）")

        except Exception as e:
            step_fail(f"文件读取出错: {e}")
            errors.append("config.toml 读取出错，请检查文件格式")

    # auth.json
    auth_path = codex_dir / "auth.json"
    step("auth.json 是否存在")
    if not auth_path.exists():
        step_fail("文件不存在")
        errors.append("缺少 ~/.codex/auth.json，请参考文档创建该文件")
    else:
        step_ok()
        try:
            auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
            api_key = auth_data.get("OPENAI_API_KEY", "").strip()
            step("OPENAI_API_KEY 是否设置")
            if not api_key:
                step_fail("值为空")
                errors.append("auth.json 中 OPENAI_API_KEY 未设置")
            elif len(api_key) < 10:
                step_fail(f"值过短（长度 {len(api_key)}），可能无效")
                errors.append("OPENAI_API_KEY 看起来不完整，请检查是否完整粘贴")
            else:
                masked = api_key[:6] + "****" + api_key[-4:]
                step_ok(f"{masked}（长度 {len(api_key)}）")
        except json.JSONDecodeError as e:
            step_fail(f"不是合法 JSON: {e}")
            errors.append("auth.json 格式错误，请检查内容")
        except Exception as e:
            step_fail(f"读取失败: {e}")
            errors.append("auth.json 读取出错")


# ── Claude 检查 ────────────────────────────────────────────
def check_claude(errors):
    claude_dir = Path.home() / ".claude"
    claude_settings = claude_dir / "settings.json"

    section("Claude Code 配置")

    step("配置目录是否存在")
    if not claude_dir.exists():
        step_fail(f"目录不存在: {claude_dir}")
        errors.append("未检测到 ~/.claude 目录，请先安装并运行一次 Claude Code")
        return
    step_ok(str(claude_dir))

    step("settings.json 是否存在")
    if not claude_settings.exists():
        step_fail("文件不存在")
        errors.append("缺少 ~/.claude/settings.json，请先运行一次 Claude Code 生成配置")
        return
    step_ok()

    try:
        settings = json.loads(claude_settings.read_text(encoding="utf-8"))
        env = settings.get("env") or {}

        step("ANTHROPIC_AUTH_TOKEN 是否设置")
        auth_token = env.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        if not auth_token:
            step_fail("值为空")
            errors.append("settings.json 的 env 中缺少 ANTHROPIC_AUTH_TOKEN，请添加你的 API Key")
        elif len(auth_token) < 10:
            step_fail(f"值过短（长度 {len(auth_token)}），可能无效")
            errors.append("ANTHROPIC_AUTH_TOKEN 看起来不完整，请检查是否完整粘贴")
        else:
            masked = auth_token[:6] + "****" + auth_token[-4:]
            step_ok(f"{masked}（长度 {len(auth_token)}）")

        step("ANTHROPIC_BASE_URL 是否设置")
        base_url = env.get("ANTHROPIC_BASE_URL", "").strip()
        _validate_base_url(base_url, errors, "ANTHROPIC_BASE_URL")

        step("ANTHROPIC_MODEL 是否设置")
        model = env.get("ANTHROPIC_MODEL", "").strip()
        if model:
            step_ok(model)
        else:
            step_warn("未设置（建议填写）")

        step("ANTHROPIC_SMALL_FAST_MODEL 是否设置")
        small_model = env.get("ANTHROPIC_SMALL_FAST_MODEL", "").strip()
        if small_model:
            step_ok(small_model)
        else:
            step_warn("未设置（建议填写）")

    except json.JSONDecodeError as e:
        step_fail(f"不是合法 JSON: {e}")
        errors.append("settings.json 格式错误，请检查内容")
    except Exception as e:
        step_fail(f"读取失败: {e}")
        errors.append("settings.json 读取出错")


# ── 安装引导辅助函数 ───────────────────────────────────────
def _get_version(cmd):
    try:
        r = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
        return (r.stdout + r.stderr).strip().splitlines()[0]
    except Exception:
        return ""

def _detect_npm():
    return shutil.which("npm") is not None

def _detect_codex_desktop():
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        return Path(local, "Programs", "Codex", "Codex.exe").exists()
    return Path("/Applications/Codex.app").exists()

def _detect_codex_cli():
    return shutil.which("codex") is not None

def _detect_claude_cli():
    return shutil.which("claude") is not None

def _install_nodejs_auto():
    """尝试通过系统包管理器自动安装 Node.js。返回 True 表示成功。"""
    system = platform.system().lower()

    def _run_cmd(cmd, label):
        print(f"\n  {CYAN}正在执行: {' '.join(cmd)}{RESET}\n")
        try:
            result = subprocess.run(cmd)
            if result.returncode == 0:
                print(f"\n  {GREEN}✅ {label} 执行成功。{RESET}")
                return True
            print(f"\n  {RED}❌ {label} 执行失败（返回码 {result.returncode}）。{RESET}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"\n  {RED}执行出错: {e}{RESET}")
        return False

    if system == "darwin":
        if shutil.which("brew"):
            print(f"  {DIM}检测到 Homebrew，将通过 brew 安装 Node.js...{RESET}")
            return _run_cmd(["brew", "install", "node"], "brew install node")
        print(f"  {YELLOW}未检测到 Homebrew，无法自动安装 Node.js。{RESET}")
        return False

    if system == "windows":
        if shutil.which("winget"):
            print(f"  {DIM}检测到 winget，将通过 winget 安装 Node.js LTS...{RESET}")
            return _run_cmd(
                ["winget", "install", "--id", "OpenJS.NodeJS.LTS",
                 "--accept-source-agreements", "--accept-package-agreements", "--silent"],
                "winget install Node.js LTS",
            )
        print(f"  {YELLOW}未检测到 winget，无法自动安装 Node.js。{RESET}")
        return False

    # Linux
    for mgr, cmd in [
        ("apt-get", ["sudo", "apt-get", "install", "-y", "nodejs", "npm"]),
        ("dnf",     ["sudo", "dnf",     "install", "-y", "nodejs"]),
        ("yum",     ["sudo", "yum",     "install", "-y", "nodejs"]),
        ("pacman",  ["sudo", "pacman",  "-S",  "--noconfirm", "nodejs", "npm"]),
    ]:
        if shutil.which(mgr):
            print(f"  {DIM}检测到 {mgr}，将通过 {mgr} 安装 Node.js...{RESET}")
            return _run_cmd(cmd, f"{mgr} install nodejs")
    print(f"  {YELLOW}未检测到受支持的包管理器，无法自动安装 Node.js。{RESET}")
    return False

def _run_npm_install(pkg):
    print(f"\n  {CYAN}正在执行: npm install -g {pkg}{RESET}\n")
    cmd = ["npm", "install", "-g", pkg]
    if sys.platform == "win32":
        cmd = ["cmd", "/c", "npm", "install", "-g", pkg]
    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except Exception as e:
        print(f"  {RED}执行失败: {e}{RESET}")
        return False

def _ask(prompt, example=""):
    if example:
        print(f"    {DIM}例：{example}{RESET}")
    try:
        return input(f"    {CYAN}›{RESET} {prompt}: ").strip()
    except EOFError:
        return ""

def _ask_yes_no(prompt, default="n"):
    suffix = "[Y/n]" if default.lower() == "y" else "[y/N]"
    try:
        answer = input(f"  {CYAN}›{RESET} {prompt}{suffix} ").strip().lower()
    except EOFError:
        answer = ""
    if not answer:
        return default.lower() == "y"
    return answer in ("y", "yes")

def _is_local_base_url(base_url):
    try:
        parsed = urlparse(base_url)
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True
    if host.startswith("127.") or host.startswith("10.") or host.startswith("192.168."):
        return True
    if re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", host):
        return True
    return False

def _validate_base_url(base_url, errors, label):
    if not base_url:
        step_fail("值为空")
        errors.append(f"{label} 未设置，请添加第三方 API 地址")
    elif not base_url.startswith("http"):
        step_warn(f"{base_url}  （格式可能有误）")
        errors.append(f"{label} 应以 http:// 或 https:// 开头")
    elif _is_local_base_url(base_url):
        step_fail(f"{base_url}  （不能使用本地地址）")
        errors.append(f"{label} 不能填写 localhost / 127.0.0.1 / 局域网等本地地址，请修改为第三方 API 公网地址")
    else:
        step_ok(base_url)

def _warn_if_local_base_url(base_url):
    if base_url and _is_local_base_url(base_url):
        print(f"    {BOX_FAIL} {RED}API 地址不能使用 localhost / 127.0.0.1 / 局域网等本地地址，请改为第三方 API 公网地址。{RESET}")

def _ask_base_url(prompt, example):
    while True:
        value = _ask(prompt, example)
        if not value or not _is_local_base_url(value):
            return value
        _warn_if_local_base_url(value)

def _read_json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}

def _get_codex_base_url(config_path):
    if not config_path.exists():
        return ""
    try:
        data = parse_toml_simple(config_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    active = data.get("model_provider", "")
    if active:
        provider = data.get(f"model_providers.{active}")
        if isinstance(provider, dict) and provider.get("base_url"):
            return provider["base_url"]
    for key, value in data.items():
        if key.startswith("model_providers.") and isinstance(value, dict) and value.get("base_url"):
            return value["base_url"]
    provider = data.get("provider")
    if isinstance(provider, dict) and provider.get("base_url"):
        return provider["base_url"]
    return data.get("base_url", "") if isinstance(data.get("base_url"), str) else ""

def _write_codex_config(config_path, base_url="", model=""):
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    text = existing

    if model:
        if re.search(r'(?m)^model\s*=\s*["\'].*?["\']', text):
            text = re.sub(r'(?m)^model\s*=\s*["\'].*?["\']', f'model = "{model}"', text, count=1)
        else:
            text = f'model = "{model}"\n' + text.lstrip()

    if base_url:
        if text and "[model_providers.custom]" in text:
            if re.search(r'(\[model_providers\.custom\][^\[]*base_url\s*=\s*")[^"]*(")', text, flags=re.DOTALL):
                text = re.sub(
                    r'(\[model_providers\.custom\][^\[]*base_url\s*=\s*")[^"]*(")',
                    rf'\g<1>{base_url}\g<2>',
                    text,
                    count=1,
                    flags=re.DOTALL,
                )
            else:
                text = re.sub(
                    r'(\[model_providers\.custom\]\n)',
                    rf'\g<1>base_url = "{base_url}"\n',
                    text,
                    count=1,
                )
        else:
            addition = (
                f'\nmodel_provider = "custom"\n\n'
                f'[model_providers.custom]\n'
                f'name = "custom"\n'
                f'base_url = "{base_url}"\n'
                f'wire_api = "responses"\n'
                f'requires_openai_auth = true\n'
            )
            text = text.rstrip() + addition

    config_path.write_text(text.lstrip(), encoding="utf-8")

def _build_models_url(base_url, style="openai"):
    clean = base_url.rstrip("/")
    if clean.endswith("/models"):
        return clean
    if style == "anthropic" and clean.endswith("/v1"):
        return f"{clean}/models"
    if style == "anthropic":
        return f"{clean}/v1/models"
    return f"{clean}/models"

KNOWN_COMPAT_SUFFIXES = (
    "/api/claudecode",
    "/api/anthropic",
    "/apps/anthropic",
    "/api/coding",
    "/claudecode",
    "/anthropic",
    "/step_plan",
    "/coding",
    "/claude",
)

def _ends_with_version_segment(url):
    last = url.rstrip("/").rsplit("/", 1)[-1]
    return len(last) > 1 and last.startswith("v") and last[1:].isdigit()

def _strip_compat_suffix(base_url):
    for suffix in KNOWN_COMPAT_SUFFIXES:
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return ""

def _candidate_model_urls(base_url, provider="openai"):
    clean = base_url.rstrip("/")
    candidates = []
    if clean.endswith("/models"):
        candidates.append(clean)
    else:
        if _ends_with_version_segment(clean):
            candidates.append(f"{clean}/models")
            if not clean.endswith("/v1"):
                candidates.append(f"{clean}/v1/models")
        else:
            candidates.append(f"{clean}/v1/models")

        stripped = _strip_compat_suffix(clean)
        if stripped and "://" in stripped:
            root = stripped.rstrip("/")
            candidates.append(f"{root}/v1/models")
            candidates.append(f"{root}/models")

        candidates.append(f"{clean}/models")
        candidates.append(f"{clean}/api/models")

    if provider == "anthropic":
        anthropic_url = _build_models_url(base_url, "anthropic")
        candidates.insert(0, anthropic_url)

    result = []
    for url in candidates:
        if url not in result:
            result.append(url)
    return result

def _extract_model_ids(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    models = []
    for item in data:
        if isinstance(item, dict):
            model_id = item.get("id") or item.get("name")
            if model_id and model_id not in models:
                models.append(str(model_id))
    return models

def _fetch_models(base_url, api_key, provider="openai"):
    if not base_url or not api_key:
        return [], "缺少 API 地址或 Key"

    attempts = []
    if provider == "anthropic":
        for url in _candidate_model_urls(base_url, "anthropic"):
            attempts.append(("openai", url))
            attempts.append(("anthropic", url))
    else:
        for url in _candidate_model_urls(base_url, "openai"):
            attempts.append(("openai", url))

    errors_seen = []
    for style, url in attempts:
        headers = {
            "Accept": "application/json",
            "User-Agent": "AI-Config-Doctor/1.0 Mozilla/5.0",
            "Cache-Control": "no-cache",
        }
        if style == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"
        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            models = _extract_model_ids(payload)
            if models:
                return models, ""
            errors_seen.append(f"{url} -> 接口返回中没有找到模型 ID")
        except error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")[:160]
            except Exception:
                body = ""
            last_error = f"{url} -> HTTP {e.code} {e.reason}"
            if e.code == 403:
                last_error += "。服务器拒绝访问模型列表，可能是该 Key 没有 models 权限、模型接口被服务商关闭，或模型列表路径不兼容。"
            elif e.code == 401:
                last_error += "。认证失败，请检查 Key/Token 是否正确。"
            if body:
                last_error += f" 返回: {body}"
            errors_seen.append(last_error)
        except Exception as e:
            errors_seen.append(f"{url} -> {e}")
    return [], "\n    ".join(errors_seen[-5:] or ["未知错误"])

def _choose_model(models, required=False, label=""):
    if not models:
        return ""
    print(f"\n  {BOLD}{WHITE}可用模型{RESET}")
    for i, model in enumerate(models, 1):
        print(f"    {BOLD}{CYAN}{i}{RESET}  {model}")
    print()
    while True:
        prompt = "请选择模型序号" if required else "请选择模型序号（直接回车跳过）"
        if label:
            prompt = f"{label} - {prompt}"
        choice = _ask(prompt)
        if not choice:
            if required:
                print(f"    {YELLOW}首次安装配置必须选择模型。{RESET}")
                continue
            return ""
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1]
        print(f"    {YELLOW}请输入 1-{len(models)} 之间的数字。{RESET}")

def _prompt_model(base_url, api_key, provider="openai", required=False):
    if not required and not _ask_yes_no("是否获取模型列表并选择？", "y"):
        manual = _ask("手动填写模型名（可跳过）", "gpt-4.1 / claude-sonnet-4-5")
        return manual
    print(f"\n    {DIM}正在获取模型列表...{RESET}")
    models, reason = _fetch_models(base_url, api_key, provider)
    if models:
        return _choose_model(models, required)
    print(f"    {BOX_WARN} {YELLOW}未能自动获取模型列表。{RESET}")
    print(f"    {MUTED}{reason}{RESET}")
    print(f"    {MUTED}你可以手动填写模型名，或稍后在服务商后台确认模型列表接口权限。{RESET}")
    while True:
        manual = _ask("手动填写模型名" if required else "手动填写模型名（可跳过）", "gpt-4.1 / claude-sonnet-4-5")
        if manual or not required:
            return manual
        print(f"    {YELLOW}首次安装配置必须填写模型名。{RESET}")

def _prompt_claude_models(base_url, token, required=False):
    print(f"\n  {BOLD}{WHITE}Claude 模型配置说明{RESET}")
    print(f"    {MUTED}需要分别配置两个模型：主模型用于主要对话/代码任务，快速模型用于轻量任务。{RESET}")
    print(f"    {MUTED}如果不确定，主模型选择 Sonnet/Opus，快速模型选择 Haiku 或较快较便宜的模型。{RESET}")
    if not required and not _ask_yes_no("是否获取模型列表并选择？", "y"):
        main_model = _ask("手动填写主模型（ANTHROPIC_MODEL，可跳过）", "claude-sonnet-4-5")
        small_model = _ask("手动填写快速模型（ANTHROPIC_SMALL_FAST_MODEL，可跳过）", "claude-haiku-4-5")
        return main_model, small_model

    print(f"\n    {DIM}正在获取模型列表...{RESET}")
    models, reason = _fetch_models(base_url, token, "anthropic")
    if models:
        main_model = _choose_model(models, required, "选择主模型（ANTHROPIC_MODEL）")
        small_model = _choose_model(models, required, "选择快速模型（ANTHROPIC_SMALL_FAST_MODEL）")
        return main_model, small_model

    print(f"    {BOX_WARN} {YELLOW}未能自动获取模型列表。{RESET}")
    print(f"    {MUTED}{reason}{RESET}")
    print(f"    {MUTED}你可以手动填写模型名，或稍后在服务商后台确认模型列表接口权限。{RESET}")
    while True:
        main_model = _ask("手动填写主模型（ANTHROPIC_MODEL）" if required else "手动填写主模型（ANTHROPIC_MODEL，可跳过）", "claude-sonnet-4-5")
        small_model = _ask("手动填写快速模型（ANTHROPIC_SMALL_FAST_MODEL）" if required else "手动填写快速模型（ANTHROPIC_SMALL_FAST_MODEL，可跳过）", "claude-haiku-4-5")
        if (main_model and small_model) or not required:
            return main_model, small_model
        print(f"    {YELLOW}首次安装配置必须填写主模型和快速模型。{RESET}")

def _ask_required(prompt, example, warning):
    while True:
        value = _ask(prompt, example)
        if value:
            return value
        print(f"    {YELLOW}{warning}{RESET}")

def _choose_or_type_model(models, label, example, required=False):
    if models:
        picked = _choose_model(models, required=False, label=label)
        if picked:
            return picked
    prompt = f"手动填写{label}" if required else f"手动填写{label}（可跳过）"
    if required:
        return _ask_required(prompt, example, f"必须填写{label}。")
    return _ask(prompt, example)


# ── Codex 配置向导 ────────────────────────────────────────
def setup_codex(edit_mode="all", require_model=False):
    section("配置 Codex")
    codex_dir = Path.home() / ".codex"
    if not codex_dir.exists():
        if _ask_yes_no("未找到 ~/.codex 目录，是否现在创建？", "y"):
            codex_dir.mkdir(parents=True, exist_ok=True)
            print(f"\n    {BOX_OK} 已创建 {codex_dir}")
        else:
            print(f"\n    {YELLOW}已取消配置。{RESET}\n")
            return

    print(f"\n  {DIM}按步骤填写，直接回车跳过该项（保持现有值不变）。{RESET}\n")

    config_path = codex_dir / "config.toml"
    auth_path = codex_dir / "auth.json"
    existing_base_url = _get_codex_base_url(config_path)
    existing_api_key = _read_json_file(auth_path).get("OPENAI_API_KEY", "").strip()

    base_url = _ask_base_url("API 地址（base_url）", existing_base_url or "https://api.example.com/v1") if edit_mode in ("all", "url") else ""
    api_key  = _ask("API Key（OPENAI_API_KEY）", "sk-xxxxxxxxxxxx") if edit_mode in ("all", "key") else ""
    final_base_url = base_url or existing_base_url
    final_api_key = api_key or existing_api_key
    model = ""
    changed_credentials = bool(base_url or api_key)
    if (changed_credentials or edit_mode == "model") and final_base_url and final_api_key:
        model = _prompt_model(final_base_url, final_api_key, "openai", require_model)

    if not base_url and not api_key and not model:
        print(f"\n    {DIM}未输入任何内容，已取消。{RESET}\n")
        return

    # config.toml
    if base_url or model:
        _write_codex_config(config_path, base_url, model)
    if base_url:
        print(f"\n    {BOX_OK} config.toml 已写入 base_url")
    if model:
        print(f"    {BOX_OK} config.toml 已写入 model（{model}）")

    # auth.json
    if api_key:
        auth_data = _read_json_file(auth_path)
        auth_data["OPENAI_API_KEY"] = api_key
        auth_path.write_text(json.dumps(auth_data, indent=2, ensure_ascii=False), encoding="utf-8")
        masked = api_key[:6] + "****" + api_key[-4:] if len(api_key) > 10 else "****"
        print(f"    {BOX_OK} auth.json 已写入 API Key（{masked}）")

    print(f"\n    {GREEN}配置完成！建议重新运行「检查 Codex 配置」验证。{RESET}\n")


# ── Claude 配置向导 ───────────────────────────────────────
def setup_claude(edit_mode="all", require_model=False):
    section("配置 Claude Code")
    claude_dir = Path.home() / ".claude"
    if not claude_dir.exists():
        if _ask_yes_no("未找到 ~/.claude 目录，是否现在创建？", "y"):
            claude_dir.mkdir(parents=True, exist_ok=True)
            print(f"\n    {BOX_OK} 已创建 {claude_dir}")
        else:
            print(f"\n    {YELLOW}已取消配置。{RESET}\n")
            return

    print(f"\n  {DIM}按步骤填写，直接回车跳过该项（保持现有值不变）。{RESET}\n")

    settings_path = claude_dir / "settings.json"
    settings = _read_json_file(settings_path)
    env = settings.setdefault("env", {})
    existing_base_url = env.get("ANTHROPIC_BASE_URL", "").strip()
    existing_token = env.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    existing_model = env.get("ANTHROPIC_MODEL", "").strip()
    existing_small_model = env.get("ANTHROPIC_SMALL_FAST_MODEL", "").strip()

    base_url = _ask_base_url("1/4 API 地址（ANTHROPIC_BASE_URL）", existing_base_url or "https://api.example.com") if edit_mode in ("all", "url") else ""
    token = _ask("2/4 API Token（ANTHROPIC_AUTH_TOKEN）", "sk-ant-xxxxxxxxxxxx") if edit_mode in ("all", "key") else ""
    final_base_url = base_url or existing_base_url
    final_token = token or existing_token
    model = ""
    small_model = ""
    changed_credentials = bool(base_url or token)

    if edit_mode == "all" and final_base_url and final_token:
        models = []
        print(f"\n  {BOLD}{WHITE}Claude 4 项配置提醒{RESET}")
        print(f"    {MUTED}第 3/4 项是主模型 ANTHROPIC_MODEL；第 4/4 项是快速模型 ANTHROPIC_SMALL_FAST_MODEL。{RESET}")
        print(f"    {MUTED}两项可以选择不同模型，也可以在服务商只提供少量模型时填写同一个模型。{RESET}")
        if _ask_yes_no("是否先获取模型列表用于第 3/4、4/4 项选择？", "y"):
            print(f"\n    {DIM}正在获取模型列表...{RESET}")
            models, reason = _fetch_models(final_base_url, final_token, "anthropic")
            if not models:
                print(f"    {BOX_WARN} {YELLOW}未能自动获取模型列表。{RESET}")
                print(f"    {MUTED}{reason}{RESET}")
        model = _choose_or_type_model(models, "3/4 主模型（ANTHROPIC_MODEL）", existing_model or "claude-sonnet-4-5", require_model)
        small_model = _choose_or_type_model(models, "4/4 快速模型（ANTHROPIC_SMALL_FAST_MODEL）", existing_small_model or "claude-haiku-4-5", require_model)
    elif (changed_credentials or edit_mode == "model") and final_base_url and final_token:
        model, small_model = _prompt_claude_models(final_base_url, final_token, require_model)

    if not base_url and not token and not model and not small_model:
        print(f"\n    {DIM}未输入任何内容，已取消。{RESET}\n")
        return

    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    if token:
        env["ANTHROPIC_AUTH_TOKEN"] = token
    if model:
        env["ANTHROPIC_MODEL"] = model
    if small_model:
        env["ANTHROPIC_SMALL_FAST_MODEL"] = small_model

    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    if base_url:
        print(f"\n    {BOX_OK} ANTHROPIC_BASE_URL 已写入")
    if token:
        masked = token[:6] + "****" + token[-4:] if len(token) > 10 else "****"
        print(f"    {BOX_OK} ANTHROPIC_AUTH_TOKEN 已写入（{masked}）")
    if model:
        print(f"    {BOX_OK} ANTHROPIC_MODEL 已写入（{model}）")
    if small_model:
        print(f"    {BOX_OK} ANTHROPIC_SMALL_FAST_MODEL 已写入（{small_model}）")

    print(f"\n    {GREEN}配置完成！建议重新运行「检查 Claude Code 配置」验证。{RESET}\n")


# ── Codex Desktop 引导 ────────────────────────────────────
def guide_codex_desktop():
    section("安装 Codex Desktop")

    step("检测 Codex Desktop 是否已安装")
    if _detect_codex_desktop():
        step_ok("已安装")
        if _ask_yes_no("是否现在配置第三方 API 地址、Key 和模型？", "y"):
            setup_codex("all", require_model=True)
        print()
        return
    step_fail("未检测到")

    print(f"\n  {YELLOW}Codex Desktop 是图形界面应用，需要手动下载安装包。{RESET}")
    print(f"  下载地址: {CYAN}{CODEX_DESKTOP_URL}{RESET}\n")
    try:
        confirm = input("  是否立即打开下载页？[y/N] ").strip().lower()
    except EOFError:
        confirm = "n"
    if confirm == "y":
        webbrowser.open(CODEX_DESKTOP_URL)
        print(f"\n  {GREEN}已在浏览器中打开下载页。{RESET}")
        print("  下载完成后按提示安装。")
    else:
        print(f"  请手动访问 {CODEX_DESKTOP_URL} 下载安装。")
    if _ask_yes_no("是否现在先写入第三方 API 地址、Key 和模型？", "y"):
        setup_codex("all", require_model=True)
    print()


# ── Codex CLI 引导 ────────────────────────────────────────
def guide_codex_cli():
    section("安装 Codex CLI")

    step("检测 Codex CLI 是否已安装")
    if _detect_codex_cli():
        ver = _get_version("codex")
        step_ok(f"已安装  {ver}".strip())
        print()
        return
    step_fail("未检测到")

    step("检测 Node.js / npm 是否可用")
    if not _detect_npm():
        step_fail("未找到 npm")
        print(f"\n  {YELLOW}安装 Codex CLI 需要先安装 Node.js。{RESET}")
        print(f"  {DIM}将尝试通过系统包管理器自动安装，需要一次性确认。{RESET}")
        if not _ask_yes_no("是否现在自动安装 Node.js？", "y"):
            print(f"  {DIM}已取消。Node.js 下载地址: {NODE_DOWNLOAD_URL}{RESET}\n")
            return
        node_ok = _install_nodejs_auto()
        if not node_ok or not _detect_npm():
            print(f"\n  {RED}❌ 自动安装 Node.js 失败。{RESET}")
            print(f"  {MUTED}请手动安装后重新运行本工具。下载地址: {CYAN}{NODE_DOWNLOAD_URL}{RESET}")
            if _ask_yes_no("是否立即打开 Node.js 下载页？", "y"):
                webbrowser.open(NODE_DOWNLOAD_URL)
            print()
            return
        print(f"\n  {GREEN}✅ Node.js 安装成功！{RESET}")
    else:
        step_ok("npm 可用")

    print()
    try:
        confirm = input("  确认安装 Codex CLI？（npm install -g @openai/codex）[y/N] ").strip().lower()
    except EOFError:
        confirm = "n"
    if confirm != "y":
        print("  已取消。")
        print()
        return

    ok_flag = _run_npm_install("@openai/codex")
    if ok_flag:
        print(f"\n  {GREEN}✅ Codex CLI 安装成功！{RESET}")
        ver = _get_version("codex")
        if ver:
            print(f"  版本: {ver}")
        print()
        try:
            go = input(f"  {CYAN}›{RESET} 是否现在配置 API 地址、Key 和模型？[y/N] ").strip().lower()
        except EOFError:
            go = "n"
        if go == "y":
            setup_codex("all", require_model=True)
    else:
        print(f"\n  {RED}❌ 安装失败，请检查网络或手动执行：npm install -g @openai/codex{RESET}")
    print()


# ── Claude CLI 引导 ───────────────────────────────────────
def guide_claude_cli():
    section("安装 Claude CLI")

    step("检测 Claude CLI 是否已安装")
    if _detect_claude_cli():
        ver = _get_version("claude")
        step_ok(f"已安装  {ver}".strip())
        print()
        return
    step_fail("未检测到")

    step("检测 Node.js / npm 是否可用")
    if not _detect_npm():
        step_fail("未找到 npm")
        print(f"\n  {YELLOW}安装 Claude CLI 需要先安装 Node.js。{RESET}")
        print(f"  {DIM}将尝试通过系统包管理器自动安装，需要一次性确认。{RESET}")
        if not _ask_yes_no("是否现在自动安装 Node.js？", "y"):
            print(f"  {DIM}已取消。Node.js 下载地址: {NODE_DOWNLOAD_URL}{RESET}\n")
            return
        node_ok = _install_nodejs_auto()
        if not node_ok or not _detect_npm():
            print(f"\n  {RED}❌ 自动安装 Node.js 失败。{RESET}")
            print(f"  {MUTED}请手动安装后重新运行本工具。下载地址: {CYAN}{NODE_DOWNLOAD_URL}{RESET}")
            if _ask_yes_no("是否立即打开 Node.js 下载页？", "y"):
                webbrowser.open(NODE_DOWNLOAD_URL)
            print()
            return
        print(f"\n  {GREEN}✅ Node.js 安装成功！{RESET}")
    else:
        step_ok("npm 可用")

    print()
    try:
        confirm = input("  确认安装 Claude CLI？（npm install -g @anthropic-ai/claude-code）[y/N] ").strip().lower()
    except EOFError:
        confirm = "n"
    if confirm != "y":
        print("  已取消。")
        print()
        return

    ok_flag = _run_npm_install("@anthropic-ai/claude-code")
    if ok_flag:
        print(f"\n  {GREEN}✅ Claude CLI 安装成功！{RESET}")
        ver = _get_version("claude")
        if ver:
            print(f"  版本: {ver}")
        print()
        try:
            go = input(f"  {CYAN}›{RESET} 是否现在配置 API 地址、Token 和模型？[y/N] ").strip().lower()
        except EOFError:
            go = "n"
        if go == "y":
            setup_claude("all", require_model=True)
    else:
        print(f"\n  {RED}❌ 安装失败，请检查网络或手动执行：npm install -g @anthropic-ai/claude-code{RESET}")
    print()


# ── 会话恢复入口 ──────────────────────────────────────────
def resume_codex_session():
    section("恢复 Codex 会话")
    print(f"\n    {DIM}正在扫描 ~/.codex/sessions 和 ~/.codex/archived_sessions...{RESET}")
    _handle_resume_session("Codex", _scan_codex_sessions())

def resume_claude_session():
    section("恢复 Claude Code 会话")
    print(f"\n    {DIM}正在扫描 ~/.claude/projects...{RESET}")
    _handle_resume_session("Claude Code", _scan_claude_sessions())


def show_menu():
    print()
    panel("  请选择操作", f"{BOLD}{WHITE}")
    print()
    print(f"  {BLUE}配置检查{RESET}")
    print(f"    {BOLD}{CYAN}1{RESET}  检查 Codex 配置       {MUTED}可解决 95% 的连接问题{RESET}")
    print(f"    {BOLD}{CYAN}2{RESET}  检查 Claude Code 配置 {MUTED}可解决 95% 的连接问题{RESET}")
    print(f"\n  {BLUE}安装引导{RESET}")
    print(f"    {BOLD}{CYAN}3{RESET}  安装 Codex Desktop  {DIM}图形界面 App{RESET}")
    print(f"    {BOLD}{CYAN}4{RESET}  安装 Codex CLI      {DIM}命令行{RESET}")
    print(f"    {BOLD}{CYAN}5{RESET}  安装 Claude CLI     {DIM}命令行{RESET}")

    print(f"\n  {BLUE}会话恢复{RESET}")
    print(f"    {BOLD}{CYAN}6{RESET}  恢复 Codex 会话       {DIM}可浏览最近 20 条对话记录{RESET}")
    print(f"    {BOLD}{CYAN}7{RESET}  恢复 Claude Code 会话 {DIM}可浏览最近 20 条对话记录{RESET}")
    print(f"\n    {BOLD}{CYAN}0{RESET}  退出")
    print()
    try:
        choice = input(f"  {MUTED}直接回车默认检查 Codex 配置，输入 0 退出{RESET}\n  {CYAN}›{RESET} ").strip()
    except EOFError:
        choice = "0"
    return choice if choice in ("0", "1", "2", "3", "4", "5", "6", "7") else "1"


def _summary(errors):
    print()
    panel("  检查结果", f"{BOLD}{WHITE}")
    print(f"    {DIM}{'─' * 40}{RESET}")
    if not errors:
        print(f"    {BOX_OK} {SOFT}全部配置正常，可以运行 codex / claude 试试。{RESET}")
    else:
        print(f"    {BOX_FAIL} {RED}{BOLD}发现 {len(errors)} 个问题，请逐项修复：{RESET}")
        for i, e in enumerate(errors, 1):
            print(f"\n    {DIM}{i}.{RESET} {YELLOW}{e}{RESET}")
    print()


def _prompt_after_check(errors, setup_func, target_name):
    panel(f"  {target_name} 配置操作", f"{BOLD}{WHITE}")
    print(f"  {MUTED}直接回车或输入 0 返回主菜单{RESET}\n")
    if errors:
        print(f"  {YELLOW}检测到配置问题，请选择修复范围：{RESET}")
    else:
        print(f"  {SOFT}配置正常。如需修改，请选择修改范围：{RESET}")
    print(f"    {BOLD}{CYAN}1{RESET}  全部更改  {DIM}API 地址、Key/Token 和模型{RESET}")
    print(f"    {BOLD}{CYAN}2{RESET}  只更改 URL")
    print(f"    {BOLD}{CYAN}3{RESET}  只更改 Key/Token")
    print(f"    {BOLD}{CYAN}4{RESET}  获取最新模型并选择")
    print(f"    {BOLD}{CYAN}0{RESET}  返回主菜单")
    print()
    if errors:
        default_hint = "建议选择 1 完整修复"
    else:
        default_hint = "如不修改可直接回车"
    choice = _ask(f"请选择操作（{default_hint}）")
    if choice == "1":
        setup_func("all")
    elif choice == "2":
        setup_func("url")
    elif choice == "3":
        setup_func("key")
    elif choice == "4":
        setup_func("model")
    else:
        print(f"\n    {DIM}已返回主菜单。{RESET}\n")


def _clear_screen():
    print("\033[2J\033[H", end="", flush=True)

def _pause():
    try:
        input(f"\n  {DIM}按回车键返回主菜单...{RESET}")
    except EOFError:
        pass

def main():
    while True:
        _clear_screen()
        header()
        print(f"  {DIM}系统: {platform.system()} {platform.release()}{RESET}")
        choice = show_menu()

        if choice == "0":
            break

        errors = []
        codex_errors: list = []
        claude_errors: list = []

        if choice == "1":
            check_codex(codex_errors)
            errors = codex_errors
            _summary(errors)
            _prompt_after_check(errors, setup_codex, "Codex")
        elif choice == "2":
            check_claude(claude_errors)
            errors = claude_errors
            _summary(errors)
            _prompt_after_check(errors, setup_claude, "Claude Code")
        elif choice == "3":
            guide_codex_desktop()
        elif choice == "4":
            guide_codex_cli()
        elif choice == "5":
            guide_claude_cli()
        elif choice == "6":
            resume_codex_session()
        elif choice == "7":
            resume_claude_session()

        _pause()

    _clear_screen()
    footer()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消")
        footer()
    finally:
        if sys.platform == "win32":
            input("按 Enter 键退出...")
