import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

def get_base_dir() -> Path:
    """Mengambil base directory baik saat dijalankan sebagai script ataupun PyInstaller frozen exe."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.parent.resolve()

BASE_DIR = get_base_dir()
CONFIG_FILE = BASE_DIR / "bridge_config.json"
if getattr(sys, 'frozen', False) and not CONFIG_FILE.exists():
    internal_cfg = BASE_DIR / "_internal" / "bridge_config.json"
    if internal_cfg.exists():
        CONFIG_FILE = internal_cfg
LOG_DIR = BASE_DIR / "logs"

DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "host": "0.0.0.0",
        "port": 12212,
        "cors_origins": ["*"],
        "enable_tray": True,
        "sharing_mode": "continuous",
        "idle_release_seconds": 4.0,
        "pause_auto_resume_seconds": 600,
        "enable_scale_at_startup": False,
    },
    "printers": {
        "default_raw_printer": "",
        "default_doc_printer": "",
        "default_encoding": "cp437",
        "pools": {
            "receipt": "",
            "label": "",
            "asset_label": "",
            "barcode": "",
            "invoice": "",
            "kitchen": ""
        },
        "network_printers": [],
    },
    "scales": [
        {
            "name": "Timbangan Kasir 1",
            "port": "COM5" if sys.platform == "win32" else "/dev/ttyUSB0",
            "protocol": "mettler",
            "baud": 9600,
            "databits": 8,
            "parity": "N",
            "stopbits": 1,
            "poll_interval": 0.5,
            "autoconnect": False,
        },
        {
            "name": "Simulator Timbangan",
            "port": "SIM",
            "protocol": "mettler",
            "baud": 9600,
            "databits": 8,
            "parity": "N",
            "stopbits": 1,
            "poll_interval": 0.5,
            "autoconnect": True,
        },
    ],
}

class ConfigManager:
    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                # Deep merge with default config
                self.config = json.loads(json.dumps(DEFAULT_CONFIG))
                if "server" in user_cfg:
                    self.config["server"].update(user_cfg["server"])
                if "printers" in user_cfg:
                    self.config["printers"].update(user_cfg["printers"])
                if "scales" in user_cfg:
                    self.config["scales"] = user_cfg["scales"]
                return self.config
        except Exception as e:
            logging.error(f"[Config] Gagal memuat konfigurasi: {e}")
        
        self.config = json.loads(json.dumps(DEFAULT_CONFIG))
        self.save()
        return self.config

    def save(self, new_config: Dict[str, Any] = None) -> bool:
        if new_config:
            self.config = new_config
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"[Config] Gagal menyimpan konfigurasi: {e}")
            return False

    def get_server_config(self) -> Dict[str, Any]:
        return self.config.get("server", DEFAULT_CONFIG["server"])

    def get_printer_config(self) -> Dict[str, Any]:
        return self.config.get("printers", DEFAULT_CONFIG["printers"])

    def get_scales_config(self) -> List[Dict[str, Any]]:
        return self.config.get("scales", DEFAULT_CONFIG["scales"])

config_manager = ConfigManager()
