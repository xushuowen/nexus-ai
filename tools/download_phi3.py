"""下載 LLaVA-Phi-3-mini GGUF 模型到 nexus/models/ 資料夾（不需要帳號）。"""

import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

BASE_URL = "https://huggingface.co/xtuner/llava-phi-3-mini-gguf/resolve/main"

FILES = [
    {
        "name": "llava-phi-3-mini-int4.gguf",
        "url": f"{BASE_URL}/llava-phi-3-mini-int4.gguf",
        "size_hint": "~2.2 GB",
    },
    {
        "name": "llava-phi-3-mini-mmproj-f16.gguf",
        "url": f"{BASE_URL}/llava-phi-3-mini-mmproj-f16.gguf",
        "size_hint": "~579 MB",
    },
]


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(".tmp")

    def progress(block, block_size, total):
        downloaded = min(block * block_size, total)
        if total > 0:
            pct = downloaded / total * 100
            mb = downloaded / 1024 / 1024
            total_mb = total / 1024 / 1024
            print(f"\r  {pct:5.1f}%  {mb:.0f} / {total_mb:.0f} MB", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, tmp, reporthook=progress)
        tmp.rename(dest)
        print(f"\r  完成：{dest.name}                              ")
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"下載失敗：{e}")


def main():
    print("=" * 50)
    print("LLaVA-Phi-3-mini GGUF 下載器（免帳號）")
    print("=" * 50)
    print(f"儲存位置：{MODELS_DIR}\n")

    for f in FILES:
        dest = MODELS_DIR / f["name"]
        if dest.exists():
            size_mb = dest.stat().st_size / 1024 / 1024
            print(f"已存在：{f['name']} ({size_mb:.0f} MB)，跳過")
            continue
        print(f"下載 {f['name']}  ({f['size_hint']})")
        download(f["url"], dest)

    print("\n全部下載完成！Nexus 將自動使用本地模型。")


if __name__ == "__main__":
    main()
