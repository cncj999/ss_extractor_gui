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
import tkinter as tk
import yaml
from tkinter import filedialog, messagebox, ttk


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
DEFAULT_EXPORT_DIR = ROOT_DIR / "exports"

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

    def to_clash_proxy(self) -> dict:
        return {
            "name": self.title,
            "type": "ss",
            "server": self.ip,
            "port": self.port,
            "cipher": self.method,
            "password": self.password,
            "udp": True,
        }

    def to_v2ray_outbound(self) -> dict:
        return {
            "tag": self.title,
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": self.ip,
                    "port": self.port,
                    "method": self.method,
                    "password": self.password,
                    "ota": False,
                }]
            },
            "streamSettings": {},
        }


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
            return default

        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        except Exception as exc:
            logging.warning("Read config.yaml failed: %s, using defaults.", exc)
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
        self.root.geometry("1100x700")
        self.root.minsize(980, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = Config.load()
        self.nodes = []
        self.subscription_url = ""
        self.export_files = {}
        self.export_dir = DEFAULT_EXPORT_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

        self.status_var = tk.StringVar(value="就绪")
        self.summary_var = tk.StringVar(value="总节点数：0\n有效节点数：0\n导出目录：exports")
        self.export_paths_var = tk.StringVar(value="最近导出：暂无")
        self.subscription_var = tk.StringVar(value="订阅链接：尚未生成")

        self.setup_ui()

    def setup_ui(self):
        self.root.configure(bg="#f3f5f9")

        toolbar = ttk.Frame(self.root, padding=(18, 10))
        toolbar.pack(fill=tk.X)

        self.extract_btn = ttk.Button(toolbar, text="提取节点", command=self.start_extraction)
        self.extract_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.copy_btn = ttk.Button(toolbar, text="复制节点", command=self.copy_nodes, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=8)

        self.save_txt_btn = ttk.Button(toolbar, text="保存TXT", command=self.save_txt, state=tk.DISABLED)
        self.save_txt_btn.pack(side=tk.LEFT, padx=8)

        self.save_base64_btn = ttk.Button(toolbar, text="保存Base64", command=self.save_base64, state=tk.DISABLED)
        self.save_base64_btn.pack(side=tk.LEFT, padx=8)

        self.generate_url_btn = ttk.Button(toolbar, text="生成订阅链接", command=self.generate_subscription_link, state=tk.DISABLED)
        self.generate_url_btn.pack(side=tk.LEFT, padx=8)

        self.copy_url_btn = ttk.Button(toolbar, text="复制订阅链接", command=self.copy_subscription_link, state=tk.DISABLED)
        self.copy_url_btn.pack(side=tk.LEFT, padx=8)

        self.export_dir_btn = ttk.Button(toolbar, text="导出目录", command=self.choose_export_dir)
        self.export_dir_btn.pack(side=tk.LEFT, padx=8)

        self.open_dir_btn = ttk.Button(toolbar, text="打开目录", command=self.open_export_dir)
        self.open_dir_btn.pack(side=tk.LEFT, padx=8)

        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 12))

        left_panel = ttk.Frame(main)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left_panel, text="节点列表", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 6))

        columns = ("title", "ip", "port", "method")
        self.tree = ttk.Treeview(left_panel, columns=columns, show="headings", height=22)
        self.tree.heading("title", text="名称")
        self.tree.heading("ip", text="IP")
        self.tree.heading("port", text="端口")
        self.tree.heading("method", text="方法")
        self.tree.column("title", width=220, anchor=tk.W)
        self.tree.column("ip", width=180, anchor=tk.W)
        self.tree.column("port", width=80, anchor=tk.CENTER)
        self.tree.column("method", width=120, anchor=tk.W)

        y_scroll = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(left_panel, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        right_panel = ttk.Frame(main, padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))

        stat_card = ttk.LabelFrame(right_panel, text="统计", padding=10)
        stat_card.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(stat_card, textvariable=self.summary_var, justify=tk.LEFT, anchor=tk.W).pack(anchor=tk.W)

        subscribe_card = ttk.LabelFrame(right_panel, text="订阅", padding=10)
        subscribe_card.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(subscribe_card, textvariable=self.subscription_var, justify=tk.LEFT, wraplength=300, anchor=tk.W).pack(anchor=tk.W)

        export_card = ttk.LabelFrame(right_panel, text="导出信息", padding=10)
        export_card.pack(fill=tk.BOTH, expand=True)
        ttk.Label(export_card, textvariable=self.export_paths_var, justify=tk.LEFT, wraplength=300, anchor=tk.W).pack(anchor=tk.W)

        status_bar = ttk.Frame(self.root, padding=(18, 8))
        status_bar.pack(fill=tk.X)
        ttk.Label(status_bar, textvariable=self.status_var, foreground="#2c7a2c").pack(anchor=tk.W)

    def _set_button_state(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.extract_btn.config(state=state)
        self.copy_btn.config(state=tk.NORMAL if enabled and self.nodes else tk.DISABLED)
        self.save_txt_btn.config(state=tk.NORMAL if enabled and self.nodes else tk.DISABLED)
        self.save_base64_btn.config(state=tk.NORMAL if enabled and self.nodes else tk.DISABLED)
        self.generate_url_btn.config(state=tk.NORMAL if enabled and self.nodes else tk.DISABLED)
        self.copy_url_btn.config(state=tk.NORMAL if enabled and self.subscription_url else tk.DISABLED)

    def update_summary(self):
        total = len(self.nodes)
        valid = total
        export_dir_text = str(self.export_dir)
        self.summary_var.set(f"总节点数：{total}\n有效节点数：{valid}\n导出目录：{export_dir_text}")

    def start_extraction(self):
        self._set_button_state(False)
        self.subscription_url = ""
        self.subscription_var.set("订阅链接：尚未生成")
        self.export_paths_var.set("最近导出：暂无")
        self.status_var.set("正在提取节点...")
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=18, pady=(0, 8))
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
        if hasattr(self, "progress"):
            self.progress.stop()
            self.progress.pack_forget()

        self.nodes = nodes
        self.subscription_url = ""
        self.export_files = {}
        self.subscription_var.set("订阅链接：尚未生成")
        self.export_paths_var.set("最近导出：暂无")
        self._set_button_state(True)
        self._refresh_tree()
        self.update_summary()
        self.auto_export_all()

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for node in self.nodes:
            self.tree.insert("", tk.END, values=(node.title, node.ip, node.port, node.method))

    def get_base64_subscription(self):
        if not self.nodes:
            raise ValueError("没有可用节点")
        content = "\n".join(node.to_ss_url() for node in self.nodes)
        return base64.b64encode(content.encode("utf-8")).decode("utf-8")

    def build_subscription_link(self, target="v2ray"):
        if not self.nodes:
            raise ValueError("没有可用节点")

        payload = self.get_base64_subscription()
        encoded = quote(payload)
        if target == "clash":
            url = (
                "https://suburl.v1.mk/"
                "#/sub?target=clash"
                f"&url={encoded}"
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
        else:
            url = (
                "https://suburl.v1.mk/"
                "#/sub?target=v2ray"
                f"&url={encoded}"
                "&insert=false"
                "&emoji=true"
                "&list=false"
                "&udp=false"
                "&tfo=false"
                "&expand=true"
                "&scv=false"
                "&fdn=false"
                "&new_name=true"
            )
        return url

    def choose_export_dir(self):
        chosen = filedialog.askdirectory(title="选��导出目录", initialdir=str(self.export_dir))
        if chosen:
            self.export_dir = Path(chosen)
            self.export_dir.mkdir(parents=True, exist_ok=True)
            self.update_summary()
            self.status_var.set(f"导出目录已更新: {self.export_dir}")

    def open_export_dir(self):
        if not self.export_dir.exists():
            self.export_dir.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(self.export_dir))
            else:
                webbrowser.open(str(self.export_dir))
        except Exception as exc:
            self.show_error(f"打开导出目录失败: {exc}")

    def auto_export_all(self):
        if not self.nodes:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = self.export_dir / timestamp
        folder.mkdir(parents=True, exist_ok=True)

        txt_content = "\n".join(node.to_ss_url() for node in self.nodes)
        base64_content = self.get_base64_subscription()

        clash_data = {"proxies": [node.to_clash_proxy() for node in self.nodes], "rules": ["MATCH,DIRECT"]}
        v2ray_data = {"log": {"loglevel": "warning"}, "outbounds": [node.to_v2ray_outbound() for node in self.nodes]}

        self.export_files = {
            "txt": self._write_export(folder, "ss_nodes", txt_content, "txt"),
            "base64": self._write_export(folder, "subscription_base64", base64_content, "txt"),
            "clash": self._write_export(folder, "clash_config", yaml.safe_dump(clash_data, sort_keys=False, allow_unicode=True), "yaml"),
            "v2ray": self._write_export(folder, "v2ray_config", json.dumps(v2ray_data, ensure_ascii=False, indent=2), "json"),
        }

        recent = "\n".join(f"{name}: {path}" for name, path in self.export_files.items())
        self.export_paths_var.set(f"最近导出：\n{recent}")
        self.status_var.set(f"已自动导出 {len(self.export_files)} 个文件到 {folder}")

    def _write_export(self, folder: Path, name: str, content: str, suffix: str) -> str:
        path = folder / f"{name}.{suffix}"
        with path.open("w", encoding="utf-8") as fp:
            fp.write(content)
        return str(path)

    def generate_subscription_link(self):
        if not self.nodes:
            self.show_error("没有可生成的节点")
            return
        try:
            self.subscription_url = self.build_subscription_link(target="v2ray")
            self.subscription_var.set(f"订阅链接：{self.subscription_url}")
            self.copy_url_btn.config(state=tk.NORMAL)
            self.status_var.set("订阅链接已生成，可直接复制到客户端")
        except Exception as exc:
            self.show_error(f"生成订阅链接失败: {exc}")

    def copy_subscription_link(self):
        if not self.subscription_url:
            self.show_error("尚未生成订阅链接")
            return
        try:
            pyperclip.copy(self.subscription_url)
            self.status_var.set("订阅链接已复制到剪贴板")
        except Exception as exc:
            self.show_error(f"复制订阅链接失败: {exc}")

    def copy_nodes(self):
        if not self.nodes:
            self.show_error("没有可复制的节点")
            return

        try:
            content = "\n".join(node.to_ss_url() for node in self.nodes)
            pyperclip.copy(content)
            self.status_var.set("节点已复制到剪贴板")
        except Exception as exc:
            self.show_error(f"复制失败: {exc}")

    def save_txt(self):
        if not self.nodes:
            self.show_error("没有可保存的节点")
            return

        try:
            content = "\n".join(node.to_ss_url() for node in self.nodes)
            filename = f"ss_nodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            path = self.export_dir / filename
            path.write_text(content, encoding="utf-8")
            self.export_paths_var.set(f"最近导出：{path}")
            self.status_var.set(f"TXT 已保存: {path}")
        except Exception as exc:
            self.show_error(f"保存 TXT 失败: {exc}")

    def save_base64(self):
        if not self.nodes:
            self.show_error("没有可保存的节点")
            return

        try:
            encoded = self.get_base64_subscription()
            filename = f"subscription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            path = self.export_dir / filename
            path.write_text(encoded, encoding="utf-8")
            self.export_paths_var.set(f"最近导出：{path}")
            self.status_var.set(f"Base64 已保存: {path}")
        except Exception as exc:
            self.show_error(f"保存 Base64 失败: {exc}")

    def show_error(self, message):
        if hasattr(self, "progress"):
            try:
                self.progress.stop()
            except Exception:
                pass
        self._set_button_state(True)
        self.status_var.set("发生错误")
        messagebox.showerror("错误", message)

    def on_close(self):
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    SSExtractorGUI(root)
    root.mainloop()
