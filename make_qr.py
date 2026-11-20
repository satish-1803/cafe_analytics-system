"""python make_qr.py http://192.168.1.5:8000 12  -> qr/table_1.png ... table_12.png"""
import sys, os, qrcode
base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
os.makedirs("qr", exist_ok=True)
for t in range(1, n + 1):
    qrcode.make(f"{base}/t/{t}").save(f"qr/table_{t}.png")
print(f"Saved {n} QR codes in ./qr")
