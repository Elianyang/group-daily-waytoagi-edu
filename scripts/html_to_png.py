#!/usr/bin/env python3
"""把群日报 HTML 转换成长图 PNG（用 Chrome headless + Pillow 自适应裁底）。

用法:
    python3 html_to_png.py --html /path/to/page.html --out /path/to/page.png
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from collections import Counter

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_chrome():
    for p in CHROME_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    cmd = shutil.which("google-chrome") or shutil.which("chromium")
    if cmd:
        return cmd
    sys.exit("没找到 Chrome / Chromium。请安装其一。")


def shoot(chrome, html_path, png_path, width, height):
    """用 Chrome headless 对 HTML 截图。"""
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-sandbox",
        "--virtual-time-budget=4000", "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--screenshot={png_path}",
        f"file://{os.path.abspath(html_path)}",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)





def _free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _http_json(url, timeout=2):
    import json, urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ws_frame(payload):
    """构造一个客户端到服务端 WebSocket 文本帧（payload < 65536）。"""
    import os, struct
    data = payload.encode("utf-8")
    mask = os.urandom(4)
    n = len(data)
    if n < 126:
        header = bytes([0x81, 0x80 | n])
    else:
        header = bytes([0x81, 0x80 | 126]) + struct.pack(">H", n)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return header + mask + masked


def _ws_recv(sock, timeout=3):
    """读取一个 WebSocket 文本帧，足够处理 CDP 返回的小 JSON。"""
    import json, socket, struct
    sock.settimeout(timeout)
    h = sock.recv(2)
    if len(h) < 2:
        raise RuntimeError("websocket closed")
    b1, b2 = h
    opcode = b1 & 0x0f
    masked = b2 & 0x80
    n = b2 & 0x7f
    if n == 126:
        n = struct.unpack(">H", sock.recv(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", sock.recv(8))[0]
    mask = sock.recv(4) if masked else b""
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            break
        data.extend(chunk)
    if masked:
        data = bytearray(b ^ mask[i % 4] for i, b in enumerate(data))
    if opcode == 8:
        raise RuntimeError("websocket close frame")
    return json.loads(data.decode("utf-8", errors="replace"))


def _cdp_eval(ws_url, expression):
    """用标准库最小 WebSocket 客户端执行 Runtime.evaluate。"""
    import base64, hashlib, json, socket, urllib.parse
    u = urllib.parse.urlparse(ws_url)
    host = u.hostname or "127.0.0.1"
    port = u.port or 80
    path = u.path + (("?" + u.query) if u.query else "")
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    req = (f"GET {path} HTTP/1.1\r\n"
           f"Host: {host}:{port}\r\n"
           f"Upgrade: websocket\r\n"
           f"Connection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\n"
           f"Sec-WebSocket-Version: 13\r\n\r\n")
    with socket.create_connection((host, port), timeout=3) as sock:
        sock.sendall(req.encode("ascii"))
        resp = sock.recv(4096)
        if b"101" not in resp.split(b"\r\n", 1)[0]:
            raise RuntimeError("websocket handshake failed")
        msg = {"id": 1, "method": "Runtime.evaluate", "params": {"expression": expression, "returnByValue": True}}
        sock.sendall(_ws_frame(json.dumps(msg)))
        while True:
            data = _ws_recv(sock)
            if data.get("id") == 1:
                return data["result"]["result"].get("value")


def _png_chunks(data):
    import struct
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    pos = 8
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+length]
        crc = data[pos+8+length:pos+12+length]
        yield ctype, payload, crc
        pos += 12 + length


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter_scanlines(raw, width, height, bpp, stride):
    rows = []
    pos = 0
    prev = bytearray(stride)
    for _ in range(height):
        ftype = raw[pos]
        pos += 1
        cur = bytearray(raw[pos:pos+stride])
        pos += stride
        if ftype == 1:  # Sub
            for i in range(bpp, stride):
                cur[i] = (cur[i] + cur[i-bpp]) & 255
        elif ftype == 2:  # Up
            for i in range(stride):
                cur[i] = (cur[i] + prev[i]) & 255
        elif ftype == 3:  # Average
            for i in range(stride):
                left = cur[i-bpp] if i >= bpp else 0
                up = prev[i]
                cur[i] = (cur[i] + ((left + up) // 2)) & 255
        elif ftype == 4:  # Paeth
            for i in range(stride):
                left = cur[i-bpp] if i >= bpp else 0
                up = prev[i]
                ul = prev[i-bpp] if i >= bpp else 0
                cur[i] = (cur[i] + _paeth(left, up, ul)) & 255
        elif ftype != 0:
            raise ValueError(f"unsupported PNG filter: {ftype}")
        rows.append(bytes(cur))
        prev = cur
    return rows


def _filter_none_rows(rows):
    return b"".join(b"\x00" + row for row in rows)


def _write_png(path, width, height, bit_depth, color_type, rows, extra_chunks):
    import struct, zlib
    def chunk(ctype, payload):
        return (struct.pack(">I", len(payload)) + ctype + payload +
                struct.pack(">I", zlib.crc32(ctype + payload) & 0xffffffff))
    out = [b"\x89PNG\r\n\x1a\n"]
    out.append(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)))
    for ctype, payload in extra_chunks:
        if ctype not in (b"IHDR", b"IDAT", b"IEND"):
            out.append(chunk(ctype, payload))
    out.append(chunk(b"IDAT", zlib.compress(_filter_none_rows(rows), level=9)))
    out.append(chunk(b"IEND", b""))
    Path(path).write_bytes(b"".join(out))


def _trim_bottom_pure_png(png_path, tol=10, pad=40):
    """纯 Python PNG 裁底：支持 Chrome 生成的 8-bit RGB/RGBA 非隔行 PNG。"""
    import struct, zlib
    data = Path(png_path).read_bytes()
    ihdr = None
    idat_parts = []
    extra_chunks = []
    for ctype, payload, _crc in _png_chunks(data):
        if ctype == b"IHDR":
            ihdr = payload
        elif ctype == b"IDAT":
            idat_parts.append(payload)
        elif ctype != b"IEND":
            extra_chunks.append((ctype, payload))
    if ihdr is None:
        raise ValueError("PNG missing IHDR")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", ihdr)
    channels_by_type = {0: 1, 2: 3, 4: 2, 6: 4}
    if bit_depth != 8 or color_type not in channels_by_type or interlace != 0:
        raise ValueError(f"unsupported PNG format: bit_depth={bit_depth}, color_type={color_type}, interlace={interlace}")
    channels = channels_by_type[color_type]
    bpp = channels
    stride = width * channels
    raw = zlib.decompress(b"".join(idat_parts))
    rows = _unfilter_scanlines(raw, width, height, bpp, stride)

    def rgb_at(row, x):
        i = x * channels
        if color_type == 0:
            v = row[i]
            return (v, v, v)
        return tuple(row[i:i+3])

    sample = []
    for y in range(height // 2, height, 50):
        row = rows[y]
        for x in range(0, width, 30):
            sample.append(rgb_at(row, x))
    bg = Counter(sample).most_common(1)[0][0]

    def is_bg(y):
        row = rows[y]
        return all(abs(rgb_at(row, x)[i] - bg[i]) <= tol
                   for x in range(0, width, 30) for i in range(3))

    last = height - 1
    for y in range(height - 1, -1, -1):
        if not is_bg(y):
            last = y
            break
    cropped_h = min(height, last + pad)
    _write_png(png_path, width, cropped_h, bit_depth, color_type, rows[:cropped_h], extra_chunks)
    return width, cropped_h, bg


def trim_bottom(png_path, tol=10, pad=40):
    """检测页面背景色 + 裁掉底部空白。优先 Pillow，失败时走纯 Python PNG 裁剪。"""
    try:
        from PIL import Image
        img = Image.open(png_path).convert("RGB")
        w, h = img.size
        pixels = img.load()

        sample = []
        for y in range(h // 2, h, 50):
            for x in range(0, w, 30):
                sample.append(pixels[x, y])
        bg = Counter(sample).most_common(1)[0][0]

        def is_bg(y):
            return all(abs(pixels[x, y][i] - bg[i]) <= tol
                       for x in range(0, w, 30) for i in range(3))

        last = h - 1
        for y in range(h - 1, -1, -1):
            if not is_bg(y):
                last = y
                break
        cropped_h = min(h, last + pad)
        img.crop((0, 0, w, cropped_h)).save(png_path, optimize=True)
        return w, cropped_h, bg
    except Exception as e:
        print(f"  Pillow 不可用，改用纯 Python PNG 裁剪：{type(e).__name__}: {e}", file=sys.stderr)
        return _trim_bottom_pure_png(png_path, tol=tol, pad=pad)

def measure_page_height(chrome, html_path, width, fallback_height):
    """启动临时 Chrome，用 CDP 读取真实 scrollHeight。

    v4 曾出现过早读取导致只得到 1200px 的问题；这里会等待 document.readyState、图片加载，
    并连续多次采样，直到高度稳定后才返回。
    """
    import tempfile, time
    port = _free_port()
    user_data = tempfile.mkdtemp(prefix="group_daily_chrome_")
    url = f"file://{os.path.abspath(html_path)}"
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw", "--disable-features=PaintHolding",
        f"--remote-debugging-port={port}", f"--user-data-dir={user_data}",
        f"--window-size={width},1600", url,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tabs = None
        for _ in range(60):
            try:
                tabs = _http_json(f"http://127.0.0.1:{port}/json")
                if tabs:
                    break
            except Exception:
                time.sleep(0.1)
        if not tabs:
            raise RuntimeError("CDP tabs not ready")

        abs_url = f"file://{os.path.abspath(html_path)}"
        tab = None
        for t in tabs:
            if t.get("type") == "page" and (t.get("url") == abs_url or t.get("url", "").endswith(Path(html_path).name)):
                tab = t
                break
        if tab is None:
            tab = next((t for t in tabs if t.get("type") == "page"), tabs[0])

        expr = """(() => {
          const c = document.querySelector('.container');
          const imgs = Array.from(document.images || []);
          const imageReady = imgs.length === 0 || imgs.every(img => img.complete && img.naturalWidth > 0);
          const heights = [
            document.documentElement ? document.documentElement.scrollHeight : 0,
            document.body ? document.body.scrollHeight : 0,
            document.documentElement ? document.documentElement.offsetHeight : 0,
            document.body ? document.body.offsetHeight : 0,
            c ? c.scrollHeight + c.offsetTop + 100 : 0,
            c ? c.getBoundingClientRect().bottom + window.scrollY + 100 : 0
          ];
          return {
            ready: document.readyState,
            imageReady,
            imgCount: imgs.length,
            h: Math.ceil(Math.max(...heights)),
            textLen: (document.body && document.body.innerText || '').length
          };
        })()"""

        best = 0
        stable = 0
        last = 0
        last_info = None
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                info = _cdp_eval(tab["webSocketDebuggerUrl"], expr)
                if isinstance(info, dict):
                    h = int(info.get("h") or 0)
                    best = max(best, h)
                    last_info = info
                    if info.get("ready") == "complete" and info.get("imageReady") and h == last and h > 1600:
                        stable += 1
                    else:
                        stable = 0
                    last = h
                    if stable >= 3:
                        break
            except Exception:
                pass
            time.sleep(0.25)

        if best <= 1200:
            # 保守兜底：按 HTML 复杂度估算，避免只截页首。
            text = Path(html_path).read_text(encoding="utf-8", errors="ignore")
            story_count = text.count('class="story"')
            detail_count = text.count('<details open>')
            best = max(best, 2200 + story_count * 760 + detail_count * 620 + text.count('class="hl"') * 90)

        measured = max(1200, min(best + 80, fallback_height))
        if last_info:
            print(f"  DOM height probe: {last_info}", file=sys.stderr)
        return measured
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        shutil.rmtree(user_data, ignore_errors=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--height", type=int, default=18000,
                    help="截图高度上限（实际会被自适应裁掉空白）")
    args = ap.parse_args()

    html_path = os.path.expanduser(args.html)
    png_path = os.path.expanduser(args.out)
    if not os.path.exists(html_path):
        sys.exit(f"HTML 不存在: {html_path}")
    os.makedirs(os.path.dirname(png_path), exist_ok=True)

    chrome = find_chrome()
    measured_height = measure_page_height(chrome, html_path, args.width, args.height)
    if measured_height != args.height:
        print(f"▶ 真实页面高度约 {measured_height}px（上限 {args.height}px）", file=sys.stderr)
    print(f"▶ 用 {chrome} 截图 {args.width}×{measured_height}...", file=sys.stderr)
    shoot(chrome, html_path, png_path, args.width, measured_height)

    print(f"▶ 自适应裁底...", file=sys.stderr)
    w, h, bg = trim_bottom(png_path)
    print(f"  bg = RGB{bg}", file=sys.stderr)
    print(f"  最终尺寸 {w}×{h}", file=sys.stderr)

    size_kb = os.path.getsize(png_path) / 1024
    print(f"✅ PNG 生成: {png_path} ({size_kb:.1f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
