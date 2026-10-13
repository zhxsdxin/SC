#!/usr/bin/env python3
"""从 fetch_kakomon.py 下载的 sc-siken 过去问页面里抽出题目、选项、正解、解说、分类。

用法：
    python3 extract_questions.py                       # 处理默认考期 07_aki
    python3 extract_questions.py --exam 06_aki         # 换考期，其余不用动
    python3 extract_questions.py --exam 06_aki --check # 只做体检，不写文件

产出：
    kakomon/<exam>/questions_jp.json    结构化的日文原题（题干/选项/正解/解说/分类）
    kakomon/<exam>/img/…                题干与解说里用到的插图

正文 HTML 只保留少量安全标签（br/ul/ol/li/dl/dt/dd/strong/b/em/u/sub/sup/span.frac/img），
a、script、ins、div 这类外壳一律剥掉；img 的远程地址在抽取阶段就换成 img/ 下的本地文件名，
后面翻译、排版都直接用这个名字。
"""

import argparse
import hashlib
import html as html_mod
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SITE = "https://www.sc-siken.com"
EXAM = "07_aki"
OUT_ROOT = "kakomon"
IMG_SUBDIR = "img"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 正文里允许保留的标签（其余一律剥壳留内容）；span 已在分数预处理里消化掉
KEEP_TAGS = {"br", "ul", "ol", "li", "dl", "dt", "dd", "strong", "b", "em", "i",
             "u", "sub", "sup", "small", "h4", "p", "img"}
# 整块丢弃的标签（广告、脚本之类）
DROP_BLOCK_TAGS = ("script", "ins", "iframe", "style", "noscript", "form")

# ---------------------------------------------------------------- 抓图


def fetch_binary(url):
    req = Request(url, headers={"User-Agent": UA, "Referer": SITE + "/"})
    with urlopen(req, timeout=30) as resp:
        return resp.status, resp.read()


def collect_images(question, exam):
    """遍历题目对象里所有 img 的远程地址，返回 (url -> 本地文件名)。

    本地名优先取远程路径的文件名；重名时补一个短哈希前缀。
    """
    urls = []
    for key in ("stem", "explain", "origin", "option_image"):
        seg = question.get(key) or ""
        urls += re.findall(r'<img[^>]*src="([^"]+)"', seg)
    for opt in question.get("options", []):
        urls += re.findall(r'<img[^>]*src="([^"]+)"', opt.get("text", ""))

    mapping, used = {}, {}
    for u in dict.fromkeys(urls):                      # 去重且保持顺序
        base = os.path.basename(u.split("?")[0])
        if not base:
            continue
        if base in used:
            base = hashlib.sha1(u.encode()).hexdigest()[:6] + "_" + base
        used[base] = u
        mapping[u] = base
    return mapping


def download_images(mapping, out_dir):
    """把远程图下到本地 img/ 目录，返回 url -> 本地名 的最终映射。"""
    os.makedirs(out_dir, exist_ok=True)
    saved = {}
    for url, name in mapping.items():
        path = os.path.join(out_dir, name)
        if os.path.exists(path) and os.path.getsize(path) > 200:
            saved[url] = name
            continue
        # 相对路径（img/xx.png）挂在 sc-siken 下，绝对路径照原样取
        full = url if url.startswith("http") else f"{SITE}/kakomon/{EXAM}/{url.lstrip('./')}"
        try:
            status, body = fetch_binary(full)
        except (HTTPError, URLError, OSError) as e:
            print(f"    插图下载失败 {name}: {e}")
            continue
        if status != 200 or body[:4] not in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1",
                                             b"GIF8"):
            print(f"    插图内容异常 {name}（状态 {status}）")
            continue
        with open(path, "wb") as f:
            f.write(body)
        saved[url] = name
        time.sleep(0.15)
    return saved


# ---------------------------------------------------------------- 清洗

def strip_blocks(text):
    """删掉 script/ins/iframe 等整块内容。"""
    for tag in DROP_BLOCK_TAGS:
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", text, flags=re.S | re.I)
        text = re.sub(rf"<{tag}\b[^>]*/?>", "", text, flags=re.I)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text


def sanitize(text, img_map=None):
    """只留白名单标签，剥掉属性；img 换成本地文件名。"""
    text = strip_blocks(text)

    # 分数标签 <span class="frac"><span>分子</span>分母</span> 先转成占位符，
    # 避免被下面的通用剥壳弄坏嵌套；最后再还原成可排版的 HTML。
    # 变体：<span class="frac">分子<span></span>分母</span>（空 span 是站点的写法瑕疵）
    text = re.sub(
        r'<span class="frac">((?:(?!</?span>).)*?)<span>\s*</span>((?:(?!</?span>).)*?)</span>',
        lambda m: "\x01" + m.group(1) + "\x02" + m.group(2) + "\x03",
        text, flags=re.S)
    # 上划线（逻辑非）<span class="ol">X</span> 与行内代码 <span class="code">X</span>
    # 同样先转占位符保护起来
    text = re.sub(r'<span class="ol">((?:(?!</?span>).)*?)</span>',
                  lambda m: "\x04" + m.group(1) + "\x05", text, flags=re.S)
    text = re.sub(r'<span class="code">((?:(?!</?span>).)*?)</span>',
                  lambda m: "\x06" + m.group(1) + "\x07", text, flags=re.S)
    # 常规：<span class="frac"><span>分子</span>分母</span>
    text = re.sub(
        r'<span class="frac">\s*<span>((?:(?!</?span>).)*?)</span>((?:(?!</?span>).)*?)</span>',
        lambda m: "\x01" + m.group(1) + "\x02" + m.group(2) + "\x03",
        text, flags=re.S)

    def repl(m):
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        if tag not in KEEP_TAGS:
            return ""
        if tag == "img":
            if closing:
                return ""
            src = re.search(r'src="([^"]+)"', attrs)
            if not src:
                return ""
            url = src.group(1)
            name = img_map.get(url) if img_map else url   # 无映射时保留原地址
            return f'<img src="{name}" alt="">'
        if tag in ("ol", "ul"):
            if closing:
                return f"</{tag}>"
            keep = ""
            for a in ("type", "start"):
                m = re.search(rf'{a}="([^"]*)"', attrs)
                if m:
                    keep += f' {a}="{m.group(1)}"'
            return f"<{tag}{keep}>"
        if tag in ("br",):
            return f"<{tag}>"
        return f"</{tag}>" if closing else f"<{tag}>"

    text = re.sub(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^>]*?)?)\s*/?>", repl, text)
    text = (text.replace("\x01", '<span class="frac"><b>')
                .replace("\x02", "</b>")
                .replace("\x03", "</span>")
                .replace("\x04", '<span class="ol">')
                .replace("\x05", "</span>")
                .replace("\x06", "<code>")
                .replace("\x07", "</code>"))

    # 实体与零散符号
    text = (text.replace("&raquo;", "›").replace("&nbsp;", " ")
                .replace("&emsp;", "\u3000").replace("&lt;", "&lt;"))
    text = re.sub(r"\s*(?:<br>\s*){3,}", "<br><br>", text)   # 连续空行收一收
    return text.strip()


def text_of(seg):
    """取纯文本（用于比对、判断空段）。"""
    return html_mod.unescape(re.sub(r"<[^>]+>", "", seg)).strip()


def slice_between(s, start_pat, end_pats, start_from=0):
    """从 start_pat 之后开始，切到最早出现的 end_pats 之前。"""
    m = re.search(start_pat, s[start_from:])
    if not m:
        return None
    i = start_from + m.end()
    ends = [s.find(p, i) for p in end_pats]
    ends = [e for e in ends if e != -1]
    j = min(ends) if ends else len(s)
    return s[i:j]


# ---------------------------------------------------------------- 单页解析

def parse_page(path, exam, img_map):
    s = open(path, encoding="utf-8", errors="replace").read()
    fname = os.path.basename(path)
    stem_name = fname[:-5]                      # am1_1
    prefix, _, num = stem_name.partition("_")

    title = re.search(r"<title>(.*?)</title>", s, re.S)
    title = title.group(1) if title else ""
    h2 = re.search(r"<h2>(.*?)</h2>", s, re.S)
    h2 = text_of(h2.group(1)) if h2 else ""

    # 午前Ⅰ / 午前Ⅱ + 問号，从 h2 里读
    part_name = re.search(r"(午前[ⅠⅡ12]+)", h2)
    part_name = part_name.group(1) if part_name else ("午前Ⅰ" if prefix == "am1" else "午前Ⅱ")

    # 题干：id="mondai" 到选项区之前
    stem = slice_between(s, r'id="mondai">', ['<div class="ansbg"']) or ""
    stem = sanitize(stem, img_map)

    # 选项：selectList 里的 li，正解那个 button 带 id="t"。
    # 特例（如 am1_14）：一个 li 里放一张选项图 + 一排「アイウエ」按钮，选项内容就是那张图。
    opts_html = slice_between(s, r'<ul class="selectList[^"]*">', ["</ul>"]) or ""
    options = []
    option_image = ""
    for li in re.findall(r"<li>(.*?)</li>", opts_html, re.S):
        btns = list(re.finditer(r'<button class="selectBtn"([^>]*)>([^<]*)</button>', li))
        imgs = list(re.finditer(r'<img[^>]*src="([^"]+)"', li))
        if not btns:
            continue
        if len(btns) > 1:                       # 图即选项：图存到 option_image，按钮只留字母
            if imgs:
                option_image = " ".join(i.group(0) for i in re.finditer(r"<img\b[^>]*>", li))
            for b in btns:
                options.append({"label": b.group(2).strip(),
                                "text": "", "correct": 'id="t"' in b.group(1)})
            continue
        b = btns[0]
        label = b.group(2).strip()
        correct = 'id="t"' in b.group(1)
        txt = li[b.end():]
        txt = re.sub(r'<span id="select_[^"]*">', "", txt)
        txt = re.sub(r"</span>\s*$", "", txt)
        if imgs:                                 # 选项本身是图（如网络拓扑图）
            head = li[:b.start()]
            txt = head + txt
        options.append({"label": label, "text": sanitize(txt, img_map), "correct": correct})

    answer = re.search(r'id="answerChar">([^<]*)<', s)
    answer = answer.group(1).strip() if answer else ""

    category = re.search(r"<h3>分類 :</h3>\s*<div>(.*?)</div>", s, re.S)
    category = text_of(category.group(1)).replace("›", "›") if category else ""

    explain = slice_between(
        s, r'id="kaisetsu">',
        ['<div class="social-btn-list', '<div class="social', '<div class="ads', '<ul id="btmNav">', "</main>"]) or ""
    explain = sanitize(explain, img_map)

    # 出典（午前Ⅰ 常有：与应援情报某题同题）
    origin = re.search(r"<h4>出典</h4>\s*<ul[^>]*>(.*?)</ul>", s, re.S)
    origin = sanitize(origin.group(1), img_map) if origin else ""

    topic = re.sub(r"^.*?令和\d+年(春期|秋期)", "", title)
    topic = re.sub(r"^問\d+", "", topic)
    topic = re.sub(r"｜.*$", "", topic).strip()
    topic = re.sub(r"^[\s　]+", "", topic)
    # 标题偶尔和 h2 一样只是「問N」，兜底用题干首句
    if not topic or re.fullmatch(r"[0-9]*", topic):
        topic = text_of(stem)[:24]

    return {
        "id": stem_name,
        "exam": exam,
        "part": prefix,
        "part_name": part_name,
        "no": int(num or 0),
        "topic": topic,
        "category": category,
        "stem": stem,
        "options": options,
        "option_image": sanitize(option_image, img_map),
        "answer": answer,
        "explain": explain,
        "origin": origin,
        "source_url": f"{SITE}/kakomon/{exam}/{fname}",
    }


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="抽取 sc-siken 过去问题目数据")
    ap.add_argument("--exam", default=EXAM)
    ap.add_argument("--root", default=OUT_ROOT)
    ap.add_argument("--check", action="store_true", help="只体检，不写 json")
    args = ap.parse_args()

    src_dir = os.path.join(args.root, args.exam)
    if not os.path.isdir(src_dir):
        print(f"找不到目录 {src_dir}，先跑 fetch_kakomon.py")
        return 1

    files = sorted(
        (f for f in os.listdir(src_dir) if re.fullmatch(r"am[12]_\d+\.html", f)),
        key=lambda n: (n[:3], int(n[4:-5])))
    if not files:
        print(f"{src_dir} 里没有 am1_*/am2_* 页面")
        return 1
    print(f"考期 {args.exam}：{len(files)} 个页面")

    print("1) 解析页面")
    questions = []
    for f in files:
        q = parse_page(os.path.join(src_dir, f), args.exam, None)
        questions.append(q)

    print("2) 收集并下载插图")
    mapping = {}
    for q in questions:
        mapping.update(collect_images(q, args.exam))
    print(f"  共 {len(mapping)} 张内容插图")
    img_map = download_images(mapping, os.path.join(src_dir, IMG_SUBDIR))

    print("3) 用本地文件名重写 img 后重新解析")
    for i, f in enumerate(files):
        questions[i] = parse_page(os.path.join(src_dir, f), args.exam, img_map)

    print("4) 体检")
    problems = []
    for q in questions:
        issues = []
        if not q["stem"]:
            issues.append("题干空")
        if len(q["options"]) != 4:
            issues.append(f'选项 {len(q["options"])} 个')
        if sum(1 for o in q["options"] if o["correct"]) != 1:
            issues.append("正解标记异常")
        if q["answer"] and not any(o["label"] == q["answer"] for o in q["options"]):
            issues.append("正解字母对不上选项")
        if len(text_of(q["explain"])) < 120:
            issues.append("解说过短")
        if not q["category"]:
            issues.append("缺分类")
        if issues:
            problems.append((q["id"], issues))
    print(f"  正常 {len(questions) - len(problems)} / {len(questions)}")
    for pid, issues in problems:
        print(f"    注意 {pid}: {'，'.join(issues)}")

    total = sum(len(q["stem"]) + len(q["explain"]) for q in questions)
    print(f"5) 正文合计 {total} 字符（含标签）")
    for part in ("am1", "am2"):
        sub = [q for q in questions if q["part"] == part]
        print(f"    {part}: {len(sub)} 题，{sub[0]['no']}–{sub[-1]['no']}" if sub else f"    {part}: 无")

    if args.check:
        return 0

    out = os.path.join(src_dir, "questions_jp.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=1)
    print(f"6) 已写出 {os.path.abspath(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
