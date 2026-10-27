import base64
import binascii
import json
import logging
import os
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pyaes
import pyperclip
import requests
import tk
from tkinter import messagebox, ttk
import yaml


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.yaml"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


@dataclass
class Node:
    ip: str
    port: int
    password: str
    method: str
    title: str
    source: str = "unknown"

    @classmethod
    def from_dict(cls, item: dict, source: str = "unknown"):
        try:
            ip = str(item.get("ip", "")).strip()
            port = int(item.get("port", 0))
            password = str(item.get("password", "")).strip()
            method = str(item.get("method", "aes-256-cfb")).strip() or "aes-256-cfb"
            title = str(item.get("title", "")).strip() or ip or "node"

            if not ip or not password or port <= 0 or port > 65535:
                return None

            return cls(
                ip=ip,
                port=port,
                password=password,
                method=method,
                title=title,
                source=source,
            )
        except Exception:
            return None

    def to_ss_url(self) -> str:
        auth = f"{self.method}:{self.password}@{self.ip}:{self.port}"
        encoded = base64.b64encode(auth.encode("utf-8")).decode("utf-8")
        label = self.title or self.ip
        return f"ss://{encoded}#{quote(label)}"


class Config:
    @staticmethod
    def load():
        default = {
            "api": {
                "url": "http://api.skrapp.net/api/serverlist",
                "timeout": 10,
                "headers": {
                    "accept": "/",
                    "accept-language": "zh-Hans-CN;q=1, en-CN;q=0.9",
                    "appversion": "1.3.1",
                    "user-agent": "SkrKK/1.3.1 (iPhone; iOS 13.5; Scale/2.00)",
                    "content-type": "application/x-www-form-urlencoded",
                    "Cookie": "PHPSESSID=fnffo1ivhvt0ouo6ebqn86a0d4",
                },
                "payload": {
                    "data": "4265a9c353cd8624fd2bc7b5d75d2f18b1b5e66ccd37e2dfa628bcb8f73db2f14ba98bc6a1d8d0d1c7ff1ef0823b11264d0addaba2bd6a30bdefe06f4ba994ed",
                },
            },
            "decrypt": {
                "key": "65151f8d966bf596",
                "iv": "88ca0f0ea1ecf975",
            },
        }

        if not CONFIG_PATH.exists():
            # If config file does not exist, use default values but keep a template for future.
            return default

        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        except Exception as exc:
            logging.warning("Failed to read config.yaml: %s. Using built-in defaults.", exc)
            return default

        merged = default.copy()
        if isinstance(loaded, dict):
            merged.update(loaded)
            for key in ["api", "decrypt"]:
                if isinstance(loaded.get(key), dict):
                    merged[key] = {**default.get(key, {}), **loaded[key]}
        return merged


class SSExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SS Node Extractor")
        self.root.geometry("720x520")
        self.root.minsize(720, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = Config.load()
        self.nodes = []
        self.setup_ui()

    def setup_ui(self):
        title_frame = ttk.Frame(self.root)
        title_frame.pack(pady=(10, 5))

        ttk.Label(title_frame, text="SS Node Extractor", font=("Arial", 16, "bold")).pack()
        ttk.Label(title_frame, text="Version: 2.1").pack()
        ttk.Label(title_frame, text="维护者: 可自行更新").pack()

        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)

        self.extract_btn = ttk.Button(button_frame, text="提取节点", command=self.start_extraction)
        self.extract_btn.pack(side=tk.LEFT, padx=5)

        self.copy_btn = ttk.Button(button_frame, text="复制节点", command=self.copy_nodes, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=5)

        self.save_txt_btn = ttk.Button(button_frame, text="保���为TXT", command=self.save_txt, state=tk.DISABLED)
        self.save_txt_btn.pack(side=tk.LEFT, padx=5)

        self.save_base64_btn = ttk.Button(button_frame, text="保存为Base64", command=self.save_base64, state=tk.DISABLED)
        self.save_base64_btn.pack(side=tk.LEFT, padx=5)

        self.clash_btn = ttk.Button(button_frame, text="Clash转换", command=self.open_clash_page, state=tk.DISABLED)
        self.clash_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=20, pady=(5, 10))

        self.result_text = tk.Text(self.root, width=90, height=18, wrap=tk.NONE)
        self.result_text.pack(padx=20, pady=(0, 10), fill=tk.BOTH, expand=True)

    def _set_button_state(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.extract_btn.config(state=state)
        self.copy_btn.config(state=state if self.nodes else tk.DISABLED)
        self.save_txt_btn.config(state=state if self.nodes else tk.DISABLED)
        self.save_base64_btn.config(state=state if self.nodes else tk.DISABLED)
        self.clash_btn.config(state=state if self.nodes else tk.DISABLED)

    def start_extraction(self):
        self._set_button_state(False)
        self.result_text.delete(1.0, tk.END)
        self.progress.start()

        thread = threading.Thread(target=self._extract_worker, daemon=True)
        thread.start()

    def _extract_worker(self):
        try:
            raw = self.fetch_server_list()
            decrypt_cfg = self.config.get("decrypt", {})
            key = str(decrypt_cfg.get("key", "")).encode("utf-8")
            iv = str(decrypt_cfg.get("iv", "")).encode("utf-8")

            nodes = self.parse_server_response(raw, key, iv)
            self.root.after(0, lambda: self._on_loaded(nodes))
        except Exception as exc:
            logging.exception("Extraction failed")
            self.root.after(0, lambda: self.show_error(f"提取失败: {exc}"))

    def fetch_server_list(self):
        api_cfg = self.config.get("api", {})
        url = api_cfg.get("url")
        headers = api_cfg.get("headers", {})
        payload = api_cfg.get("payload", {})
        timeout = int(api_cfg.get("timeout", 10))

        response = requests.post(url, headers=headers, data=payload, timeout=timeout)
        response.raise_for_status()
        return response.text.strip()

    def parse_server_response(self, raw_text: str, key: bytes, iv: bytes):
        if not raw_text:
            raise ValueError("响应为空")

        try:
            encrypted_data = binascii.unhexlify(raw_text)
        except Exception as exc:
            raise ValueError(f"十六进制解码失败: {exc}") from exc

        if len(key) != 16:
            raise ValueError("AES Key 长度必须为 16 字节")
        if len(iv) != 16:
            raise ValueError("AES IV 长度必须为 16 字节")

        decryptor = pyaes.AESModeOfOperationCBC(key, iv=iv)
        decrypted = b"".join(
            decryptor.decrypt(encrypted_data[i:i + 16]) for i in range(0, len(encrypted_data), 16)
        )

        if not decrypted:
            raise ValueError("解密后内容为空")

        pad = decrypted[-1]
        if not 1 <= pad <= 16:
            raise ValueError("AES padding 异常")

        if decrypted[-pad:] != bytes([pad]) * pad:
            raise ValueError("AES padding 校验失败")

        decrypted = decrypted[:-pad]

        try:
            data = json.loads(decrypted.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"JSON 解析失败: {exc}") from exc

        items = data.get("data")
        if not isinstance(items, list):
            raise ValueError("返回数据中没有有效的 data 列表")

        good_nodes = []
        for item in items:
            if not isinstance(item, dict):
                continue
            node = Node.from_dict(item, source="server")
            if node:
                good_nodes.append(node)

        deduped = []
        seen = set()
        for node in good_nodes:
            key_value = (node.ip, node.port, node.password, node.title)
            if key_value in seen:
                continue
            deduped.append(node)
            seen.add(key_value)

        return deduped

    def _on_loaded(self, nodes):
        self.progress.stop()
        self.nodes = nodes
        self._set_button_state(True)
        self.result_text.delete(1.0, tk.END)
        for node in nodes:
            self.result_text.insert(tk.END, node.to_ss_url() + "\n")

        self.show_message(f"提取完成，共 {len(nodes)} 个有效节点")

    def copy_nodes(self):
        if not self.nodes:
            self.show_error("没有可复制的节点")
            return

        try:
            content = "\n".join(node.to_ss_url() for node in self.nodes)
            pyperclip.copy(content)
            self.show_message("节点已复制到剪贴板")
        except Exception as exc:
            self.show_error(f"复制失败: {exc}")

    def save_txt(self):
        if not self.nodes:
            self.show_error("没有可保存的节点")
            return

        try:
            content = "\n".join(node.to_ss_url() for node in self.nodes)
            filename = f"ss_nodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            self.show_message(f"TXT 已保存: {filename}")
        except Exception as exc:
            self.show_error(f"保存 TXT 失败: {exc}")

    def save_base64(self):
        if not self.nodes:
            self.show_error("没有可保存的节点")
            return

        try:
            content = "\n".join(node.to_ss_url() for node in self.nodes)
            encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            filename = f"subscription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(encoded)
            self.show_message(f"Base64 已保存: {filename}")
        except Exception as exc:
            self.show_error(f"保存 Base64 失败: {exc}")

    def open_clash_page(self):
        if not self.nodes:
            self.show_error("没有可转换的节点")
            return

        try:
            nodes_text = "|".join(node.to_ss_url() for node in self.nodes)
            encoded_nodes = quote(nodes_text)
            clash_url = (
                "https://suburl.v1.mk/"
                "#/sub?target=clash"
                f"&url={encoded_nodes}"
                "&insert=false"
                "&config=https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online_Full_NoAuto.ini"
                "&emoji=true"
                "&list=false"
                "&udp=false"
                "&tfo=false"
                "&expand=true"
                "&scv=false"
                "&fdn=false"
                "&new_name=true"
            )
            webbrowser.open(clash_url, new=2)
            self.show_message("已打开 Clash 转换页面")
        except Exception as exc:
            self.show_error(f"打开 Clash 页面失败: {exc}")

    def show_message(self, message):
        messagebox.showinfo("提示", message)

    def show_error(self, message):
        self.progress.stop()
        self._set_button_state(True)
        messagebox.showerror("错误", message)

    def on_close(self):
        self.root.destroy()


if __name__ == "__main__":
    try:
        import tkinter as tk
    except ImportError as exc:
        raise SystemExit(f"Tkinter is required to run this app: {exc}")

    root = tk.Tk()
    app = SSExtractorGUI(root)
    root.mainloop()
