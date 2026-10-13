#!/usr/bin/env python3
"""批量下载 sc-siken.com 的过去问页面与午后 PDF（默认 07_aki）。

用法：
    python3 fetch_kakomon.py                      # 下载默认考期 07_aki：午前I/午前II 页面 + 午后 PDF
    python3 fetch_kakomon.py --exam 06_aki        # 换考期，其余不用动
    python3 fetch_kakomon.py --exam 06_aki --parts am1:30,am2:25,pm:4
    python3 fetch_kakomon.py --list-only          # 只列出会下载哪些文件
    python3 fetch_kakomon.py --force              # 已存在的文件也重新下载

下载两类东西：
    html  午前I  am1_1.html …  https://www.sc-siken.com/kakomon/<exam>/am1_1.html   （通常 30 题，试 31 失败收手）
    html  午前II am2_1.html …  https://www.sc-siken.com/kakomon/<exam>/am2_1.html   （通常 25 题，试 26 失败收手）
    pdf   午后   pm1.pdf   …   https://www.sc-siken.com/pdf/<exam>/pm1.pdf          （通常 4 个，试 pm5 失败收手）
前缀以 pm 开头的按 PDF 处理（走 /pdf/ 路径并校验文件头），其余按 html。

题号边界怎么确定：
    1) 先读目录页 https://www.sc-siken.com/kakomon/<exam>/ ，页面里直接列了上面的链接，
       能拿到就拿到，最准。
    2) 目录页拿不到时退回探测：从 1 开始连续请求，遇到第一个失败（404 或内容异常）就停止。

换考期只改 EXAM 变量（或 --exam 参数）即可，其余不用动。
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------- 配置区

SITE = "https://www.sc-siken.com"
EXAM = "07_aki"                        # 只改这里就能换考期，例如 "06_haru"
PARTS = [                              # (文件名前缀, 预期数量, 类型)；预期值只用于提示，边界靠目录页/探测
    ("am1", 30, "html"),
    ("am2", 25, "html"),
    ("pm", 4, "pdf"),
]
OUT_ROOT = "kakomon"                   # 输出根目录，实际保存到 <OUT_ROOT>/<EXAM>/
WORKERS = 4                            # 并发数
DELAY = 0.2                            # 每次请求之间的最小间隔（秒），别把人家站点打疼
TIMEOUT = 60                           # PDF 单个 1~2 MB，超时给宽一点
RETRIES = 3
MIN_HTML_BYTES = 5000                  # 小于这个体积视为异常页
MIN_PDF_BYTES = 10000

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# ---------------------------------------------------------------- 网络


def fetch(url):
    """取一个 URL，返回 (status, body)。404/410 直接返回，其余错误重试后抛异常。"""
    last_err = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(0.6 * 2 ** (attempt - 1) + random.random() * 0.4)
        try:
            req = Request(url, headers={
                "User-Agent": UA,
                "Referer": SITE + "/",
                "Accept": "text/html,application/pdf,application/xhtml+xml,*/*",
                "Accept-Language": "ja,en;q=0.8",
            })
            with urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status, resp.read()
        except HTTPError as e:
            if e.code in (400, 404, 410):
                return e.code, b""
            last_err = e
        except (URLError, TimeoutError, OSError) as e:
            last_err = e
        time.sleep(DELAY)
    raise RuntimeError(f"请求失败 {url} ({last_err})")


def part_url(exam, name, kind):
    return (f"{SITE}/pdf/{exam}/{name}" if kind == "pdf"
            else f"{SITE}/kakomon/{exam}/{name}")


def looks_valid(body, kind):
    if kind == "pdf":
        return len(body) >= MIN_PDF_BYTES and body[:5] == b"%PDF-"
    if not body or len(body) < MIN_HTML_BYTES:
        return False
    return b"</html>" in body[-2000:].lower()


# ---------------------------------------------------------------- 发现文件


def num_of(name):
    """取文件名里扩展名前的那个数字，比如 am1_13.html -> 13，pm2.pdf -> 2"""
    m = re.search(r'(\d+)\.[a-z]+$', name)
    return int(m.group(1)) if m else 0


def discover_from_index(exam, parts):
    """读目录页，提取每部分的文件名。拿不到返回 None。"""
    url = f"{SITE}/kakomon/{exam}/"
    try:
        status, body = fetch(url)
    except RuntimeError as e:
        print(f"  目录页不可用：{e}")
        return None
    if status != 200 or not looks_valid(body, "html"):
        print(f"  目录页返回 {status}，改用探测")
        return None

    html = body.decode("utf-8", "replace")
    found = {}
    for prefix, _, kind in parts:
        if kind == "pdf":
            pattern = rf'href="(?:[^"]*/)?pdf/{re.escape(exam)}/({re.escape(prefix)}\d+\.pdf)"'
            names = re.findall(pattern, html)
        else:
            pattern = rf'href="({re.escape(prefix)}_(\d+)\.html)"'
            names = [m[0] for m in re.findall(pattern, html)]
        if names:
            found[prefix] = sorted(set(names), key=num_of)
    return found or None


def probe_part(exam, prefix, expected, kind, hard_limit=200):
    """从 1 开始连续请求，遇到第一个失败就停止。"""
    names, n = [], 1
    ext = ".pdf" if kind == "pdf" else ".html"
    while n <= hard_limit:
        name = f"{prefix}{'_' if kind != 'pdf' else ''}{n}{ext}"
        try:
            status, body = fetch(part_url(exam, name, kind))
        except RuntimeError as e:
            print(f"    {name}: {e}，停止探测")
            break
        if status != 200 or not looks_valid(body, kind):
            print(f"    {name}: 状态 {status}／内容异常 -> 认定为末尾，停止（共 {len(names)} 个）")
            break
        names.append(name)
        n += 1
    if names and len(names) != expected:
        print(f"    提示：{prefix} 实际 {len(names)} 个，与预设 {expected} 不一致，已按实际为准")
    return names


# ---------------------------------------------------------------- 下载


def download(item, out_dir, force):
    name, url, kind = item
    path = os.path.join(out_dir, name)
    if not force and os.path.exists(path) and os.path.getsize(path) >= (
            MIN_PDF_BYTES if kind == "pdf" else MIN_HTML_BYTES):
        return name, "skip", os.path.getsize(path), ""
    try:
        status, body = fetch(url)
    except RuntimeError as e:
        return name, "fail", 0, str(e)
    if status != 200 or not looks_valid(body, kind):
        return name, "fail", 0, f"状态 {status}／内容异常"
    with open(path, "wb") as f:
        f.write(body)
    return name, "ok", len(body), hashlib.sha256(body).hexdigest()[:12]


# ---------------------------------------------------------------- 主流程


def parse_parts(text, default):
    if not text:
        return default
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        prefix, _, num = chunk.partition(":")
        prefix = prefix.strip()
        kind = "pdf" if prefix.startswith("pm") else "html"
        out.append((prefix, int(num) if num else 0, kind))
    return out


def main():
    global DELAY

    ap = argparse.ArgumentParser(description="批量下载 sc-siken 过去问页面与午后 PDF")
    ap.add_argument("--exam", default=EXAM, help=f"考期 ID，默认 {EXAM}")
    ap.add_argument("--parts", default=None, help="格式 am1:30,am2:25,pm:4（pm 前缀按 PDF 处理）")
    ap.add_argument("--out", default=OUT_ROOT, help=f"输出根目录，默认 {OUT_ROOT}")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--delay", type=float, default=DELAY)
    ap.add_argument("--force", action="store_true", help="已存在也重新下载")
    ap.add_argument("--list-only", action="store_true", help="只列出文件，不下载")
    ap.add_argument("--no-index", action="store_true", help="跳过目录页，强制用探测方式定边界")
    args = ap.parse_args()

    DELAY = args.delay
    parts = parse_parts(args.parts, PARTS)
    out_dir = os.path.join(args.out, args.exam)
    os.makedirs(out_dir, exist_ok=True)

    print(f"考期 {args.exam}｜部分 {', '.join(f'{p}({k})' for p, _, k in parts)}｜保存到 {out_dir}")

    print("1) 确定文件名范围")
    index_map = None if args.no_index else discover_from_index(args.exam, parts)
    plan = []
    for prefix, expected, kind in parts:
        if index_map and prefix in index_map:
            names = index_map[prefix]
            print(f"  {prefix}: 目录页给出 {len(names)} 个（{names[0]} … {names[-1]}）")
        else:
            print(f"  {prefix}: 目录页没有，开始探测")
            names = probe_part(args.exam, prefix, expected, kind)
        for name in names:
            plan.append((name, part_url(args.exam, name, kind), kind))

    if not plan:
        print("没找到任何文件，检查考期 ID 是否正确。")
        return 1
    if args.list_only:
        for name, url, kind in plan:
            print(f"  {name}\t{url}")
        print(f"共 {len(plan)} 个文件")
        return 0

    print(f"2) 下载 {len(plan)} 个文件（并发 {args.workers}）")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download, it, out_dir, args.force): it for it in plan}
        for i, fut in enumerate(as_completed(futures), 1):
            name, state, size, note = fut.result()
            results.append((name, state, size, note))
            flag = {"ok": "行", "skip": "跳过", "fail": "失败"}[state]
            print(f"  [{i}/{len(plan)}] {name} {flag} {size} B {note}")

    ok = [r for r in results if r[1] == "ok"]
    skip = [r for r in results if r[1] == "skip"]
    fail = [r for r in results if r[1] == "fail"]

    manifest = {
        "exam": args.exam,
        "site": SITE,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "parts": {p: [n[0] for n in plan if n[0].startswith(p)] for p, _, _ in parts},
        "files": [{"name": n, "url": u, "kind": k} for n, u, k in plan],
        "result": {"downloaded": len(ok), "skipped": len(skip), "failed": len(fail)},
    }
    with open(os.path.join(out_dir, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"3) 完成：新下载 {len(ok)}，跳过 {len(skip)}，失败 {len(fail)}，共 {len(plan)}")
    if fail:
        print("  失败清单：" + ", ".join(r[0] for r in fail))
    print(f"  文件在 {os.path.abspath(out_dir)}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
