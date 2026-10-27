# SS Node Extractor

This repository contains a Python GUI tool for extracting SS node lists, decoding the upstream encrypted payload, and exporting valid nodes for local use or subscription import.

## Features

- Fetches the server list from the configured API
- Decodes the AES-CBC payload automatically
- Filters and deduplicates nodes
- Lists valid nodes with title, IP, port, and method
- Copies nodes to clipboard
- Saves raw `ss://` links as TXT
- Saves Base64 subscription content
- Generates a subscription URL suitable for V2Ray / V2RayN / Clash clients
- Automatically exports a set of files into the `exports/` directory
  - `ss_nodes.txt`
  - `subscription_base64.txt`
  - `clash_config.yaml`
  - `v2ray_config.json`
- Supports a custom export directory selection

## Quick start on Windows

1. Install Python 3.9+
2. Open a terminal in the project folder
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Double-click `run_gui.bat` to launch the app.

## Manual launch

```bash
python ss_extractor_gui.py
```

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
