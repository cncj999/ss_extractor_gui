# SS Node Extractor

This repository contains a Python GUI tool for extracting SS node lists, decoding the upstream encrypted payload, exporting valid nodes, and generating subscription formats for tools like Clash and V2RayN.

## Features

- Fetch server list from a configured API
- Decode AES-CBC encrypted payloads automatically
- Deduplicate and validate nodes
- Display nodes in a desktop-style GUI
- Copy nodes to clipboard
- Save raw `ss://` links as TXT
- Save Base64 subscription content
- Generate subscription URLs for V2Ray / V2RayN / Clash clients
- Automatically export files into an `exports/` directory
  - `ss_nodes.txt`
  - `subscription_base64.txt`
  - `clash_config.yaml`
  - `v2ray_config.json`
- Windows double-click launcher via `run_gui.bat`

## Quick start on Windows

1. Install Python 3.9+
2. Open a terminal in the project folder
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Launch the GUI:

```bash
python ss_extractor_gui.py
```

or simply double-click:

```bash
run_gui.bat
```

## Build to EXE

To package this app as a single Windows executable:

1. Install PyInstaller:

```bash
pip install pyinstaller
```

2. Run the build script:

```bash
build_exe.bat
```

3. The generated EXE will appear in the `dist/` folder.

## Config

- Copy `config.example.yaml` to `config.yaml` if needed
- Update the API URL, headers, or decryption key as required

## Export behavior

After a successful extraction, the app automatically creates a timestamped folder under `exports/` and saves the following files:

```text
exports/
  20261027_120000/
    ss_nodes.txt
    subscription_base64.txt
    clash_config.yaml
    v2ray_config.json
```

This makes it easy to import the result into software such as Clash or V2RayN.
