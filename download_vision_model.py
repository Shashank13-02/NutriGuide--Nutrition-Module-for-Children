"""Download pinned official SmolVLM files for fully local meal-photo inference."""
import hashlib
import json
import time
import uuid
import shutil
from pathlib import Path
import requests

REPO = "HuggingFaceTB/SmolVLM-500M-Instruct"
REVISION = "a7da5b986cb59b408707209984f360a5f4ad7e47"
DEST = Path(__file__).parent / "models" / "smolvlm_500m"

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    response = requests.get(f"https://huggingface.co/api/models/{REPO}/revision/{REVISION}", params={"blobs": "true"}, timeout=30)
    response.raise_for_status()
    files = response.json()["siblings"]
    for entry in files:
        name = entry["rfilename"]
        if "/" in name or not (name.endswith(".json") or name in {"merges.txt", "vocab.json", "model.safetensors"}):
            continue
        target = DEST / name
        expected = entry.get("lfs", {}).get("sha256")
        if target.exists() and target.stat().st_size == entry.get("size"):
            if not expected or hashlib.file_digest(target.open("rb"), "sha256").hexdigest() == expected:
                print(f"Verified {name}", flush=True)
                continue
        temporary = target.with_suffix(target.suffix + "." + uuid.uuid4().hex + ".download")
        if name == "model.safetensors":
            total = entry["size"]
            partials = [p for p in DEST.glob("model.safetensors*.download") if 0 < p.stat().st_size < total]
            if partials:
                previous = max(partials, key=lambda p: p.stat().st_size)
                shutil.copyfile(previous, temporary)
            else:
                temporary.touch()
            while temporary.stat().st_size < total:
                start = temporary.stat().st_size
                end = min(start + 16 * 1024 * 1024 - 1, total - 1)
                for attempt in range(5):
                    try:
                        with requests.get(f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}", params={"download": "true", "chunk": f"{start}-{attempt}-{time.time_ns()}"}, headers={"Range": f"bytes={start}-{end}"}, stream=True, timeout=(20, 20)) as download:
                            download.raise_for_status()
                            if download.status_code != 206 or not download.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/"):
                                raise ValueError("The download server did not honor the requested byte range")
                            with temporary.open("ab") as output:
                                for chunk in download.iter_content(1024 * 1024):
                                    output.write(chunk)
                        if temporary.stat().st_size != end + 1:
                            raise ValueError("Incomplete download chunk")
                        print(f"Weights: {end + 1:,}/{total:,} bytes", flush=True)
                        break
                    except (requests.RequestException, ValueError):
                        with temporary.open("r+b") as output:
                            output.truncate(start)
                        if attempt == 4:
                            raise
                else:
                    raise RuntimeError("Chunk download failed")
            with temporary.open("rb") as content:
                if expected and hashlib.file_digest(content, "sha256").hexdigest() != expected:
                    raise ValueError("Weight checksum mismatch")
            temporary.replace(target)
            print("Verified official weights SHA-256.", flush=True)
            continue
        digest = hashlib.sha256()
        size = 0
        with requests.get(f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}", params={"download": "true", "t": str(int(time.time()))}, stream=True, timeout=(30, 60)) as download:
            download.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in download.iter_content(4 * 1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        if expected and digest.hexdigest() != expected:
            raise ValueError(f"Checksum mismatch: {name}")
        if entry.get("size") and size != entry["size"]:
            raise ValueError(f"Size mismatch: {name}")
        temporary.replace(target)
        print(f"Downloaded {name}: {size:,} bytes", flush=True)
    (DEST / "download_manifest.json").write_text(json.dumps({"repository": REPO, "revision": REVISION}, indent=2))
    print("Official model is available locally.", flush=True)

if __name__ == "__main__":
    main()
