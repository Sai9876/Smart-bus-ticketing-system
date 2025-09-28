# services/qr.py
import qrcode, os, pathlib, time

def make_qr(payload_text: str, out_dir="qrs", name_hint: str = "ticket"):
    base = pathlib.Path(__file__).resolve().parent.parent  # project root (adjust if needed)
    qrs_dir = base / out_dir
    qrs_dir.mkdir(parents=True, exist_ok=True)

    # unique filename avoids stale caches
    fname = f"{name_hint}_{int(time.time())}.png"
    path = qrs_dir / fname

    img = qrcode.make(payload_text)
    img.save(path)
    return str(path)  # absolute path
