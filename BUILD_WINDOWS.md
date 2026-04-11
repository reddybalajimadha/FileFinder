# Building FileFinder as a Windows Application

This guide shows how to build a standalone Windows `.exe` for FileFinder.

## Prerequisites

Install Python 3.9+ on Windows, then:

```powershell
# Install core dependencies
pip install -r requirements.txt

# Install the desktop and build tools
pip install pywebview pyinstaller
```

## Run in development mode

Before building, test that the app runs:

```powershell
# Launch the desktop app
python -m filefinder.web

# Or auto-index a specific folder on startup
python -m filefinder.web "C:\Users\YourName\Documents"
```

A native Windows window will open showing the FileFinder UI.

## Build the `.exe`

From the project root:

```powershell
pyinstaller filefinder.spec
```

This creates a `dist\FileFinder\` folder containing `FileFinder.exe` and
all its dependencies. You can:

1. Run `dist\FileFinder\FileFinder.exe` directly
2. Distribute the whole `dist\FileFinder\` folder as a portable app
3. Create an installer using tools like **Inno Setup** or **NSIS**

## Optional: Add an application icon

1. Create a 256x256 `.ico` file (use a tool like https://convertico.com)
2. Save it as `assets/icon.ico`
3. Uncomment the `icon="assets/icon.ico"` line in `filefinder.spec`
4. Rebuild with `pyinstaller filefinder.spec`

## Reducing the .exe size

The default spec **excludes** PyTorch and sentence-transformers to keep
the binary small (~50MB vs ~2GB with ML deps). If you want the AI
semantic search feature bundled into the `.exe`, remove these from the
`excludes` list in `filefinder.spec`:

```python
excludes=[
    # "torch",
    # "transformers",
    # "sentence_transformers",
],
```

Users will still be able to install them separately with pip.

## Creating a Windows installer

For a professional `.msi` or `.exe` installer:

### Using Inno Setup (recommended, free)
1. Download from https://jrsoftware.org/isinfo.php
2. Create an `.iss` script pointing at `dist\FileFinder\`
3. Compile with Inno Setup Compiler

### Using WiX Toolset (for `.msi`)
1. Install WiX: https://wixtoolset.org/
2. Create a `.wxs` file referencing the bundled files
3. Run `candle` and `light` to produce the `.msi`

## Troubleshooting

**"ModuleNotFoundError" at runtime:**
Add the missing module to `hidden_imports` in `filefinder.spec`.

**PyWebView fails to show the window:**
On Windows, PyWebView needs either the Edge WebView2 runtime (usually
pre-installed on Windows 10/11) or CEF:
```powershell
pip install pywebview[cef]
```

**"Failed to access" errors when indexing:**
FileFinder skips files the user doesn't have permission to read. This
is normal and expected behavior. Run as the current user, not admin.
