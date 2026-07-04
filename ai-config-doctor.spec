# -*- mode: python ; coding: utf-8 -*-

import sys


if sys.platform == 'darwin':
    app_icon = 'assets/icons/ai-config-doctor.icns'
elif sys.platform.startswith('win'):
    app_icon = 'assets/icons/ai-config-doctor.ico'
else:
    app_icon = None


a = Analysis(
    ['check_codex.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ai-config-doctor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)
