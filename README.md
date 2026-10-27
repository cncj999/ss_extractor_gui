# SS Node Extractor

This repository contains a Python GUI tool to fetch and decode SS node lists, then export them as plain text, Base64 subscription, or open a Clash conversion page.

## Features

- Fetch server list from a configured API
- Decode AES-CBC encrypted payload
- Convert nodes into `ss://...` format
- Copy to clipboard
- Save as TXT and Base64
- Open a Clash conversion page directly
- Configurable via `config.yaml`

## Windows quick start

1. Install Python 3.9+ and make sure `python` is in PATH.
2. Open a command prompt in the project folder.
3. Run:

```bash
pip install -r requirements.txt
```

4. Double-click `run_gui.bat` to start the app.

## Manual start

```bash
python ss_extractor_gui.py
```

## Config

- Copy `config.example.yaml` to `config.yaml`
- Adjust API parameters and decryption key if needed

## Notes

This tool depends on the upstream API format. If the server changes its payload or encryption settings, update `config.yaml` and the decryption logic accordingly.
