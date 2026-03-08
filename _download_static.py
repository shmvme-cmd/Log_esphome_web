"""
Скачивает Bootstrap 5, Socket.IO и Google Fonts локально
в static/ для работы без интернета.
"""
import urllib.request
import os
import re

os.makedirs("static/fonts", exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def download(url, dest):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    print(f"  OK  {dest}  ({len(data):,} bytes)")


# ── Bootstrap 5.3.3 ──────────────────────────────────────────────────────────
print("Bootstrap CSS...")
download(
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    "static/css/bootstrap.min.css",
)
print("Bootstrap JS (bundle)...")
download(
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
    "static/js/bootstrap.bundle.min.js",
)

# ── Socket.IO 4.7.5 ──────────────────────────────────────────────────────────
print("Socket.IO client...")
download(
    "https://cdn.socket.io/4.7.5/socket.io.min.js",
    "static/js/socket.io.min.js",
)

# ── Google Fonts: Inter + JetBrains Mono ─────────────────────────────────────
print("Google Fonts CSS...")
fonts_url = (
    "https://fonts.googleapis.com/css2"
    "?family=Inter:wght@300;400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500"
    "&display=swap"
)
req = urllib.request.Request(fonts_url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=30) as r:
    fonts_css = r.read().decode("utf-8")

# Скачиваем каждый woff2-файл, подставляем локальный путь
font_urls = re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", fonts_css)
font_urls = list(dict.fromkeys(font_urls))          # убираем дубли, сохраняем порядок

for i, furl in enumerate(font_urls):
    suffix = furl.split("/")[-1].split("?")[0]      # имя файла без query
    fname  = f"f{i:03d}_{suffix}"
    fpath  = f"static/fonts/{fname}"
    print(f"  font {i+1}/{len(font_urls)}  {fname}")
    download(furl, fpath)
    fonts_css = fonts_css.replace(furl, f"../fonts/{fname}")

with open("static/css/fonts.css", "w", encoding="utf-8") as f:
    f.write(fonts_css)
print(f"  OK  static/css/fonts.css")

print("\nВсё скачано!")
