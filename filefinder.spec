# PyInstaller spec for building FileFinder as a Windows .exe
# Build with: pyinstaller filefinder.spec

# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect static files (HTML, CSS, JS) so they're bundled into the exe
static_files = [
    ("filefinder/web/static/index.html", "filefinder/web/static"),
    ("filefinder/web/static/style.css", "filefinder/web/static"),
    ("filefinder/web/static/app.js", "filefinder/web/static"),
]

# Hidden imports that PyInstaller may miss
hidden_imports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "webview",
    "webview.platforms.winforms",
    "sqlite3",
    "pdfplumber",
    "docx",
]

a = Analysis(
    ["filefinder/web/__main__.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=static_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy ML deps if you want a smaller .exe
        # Remove these if you want --semantic search in the bundled app
        "torch",
        "transformers",
        "sentence_transformers",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FileFinder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # False = no console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # Uncomment and provide an icon file
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FileFinder",
)
