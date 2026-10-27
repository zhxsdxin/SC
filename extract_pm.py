#!/usr/bin/env python3
"""从 pm 解説 HTML（sc-siken 午后答案页）抽取结构化数据 → kakomon/<exam>/pm_jp.json

午后题目本身只在 PDF 里（/pdf/<exam>/pmN.pdf），HTML 頁是答案+解説页：
    <h3>出題趣旨</h3><div>…</div>
    <h3>設問1</h3><div class="pm_answer">模範解答</div><div class="ansbg">解説</div> …

用法：
    python3 extract_pm.py --exam 06_haru
    python3 extract_pm.py --exam 05_aki,06_aki,06_haru
"""

import argparse
import json
import os
import re
import sys

ROOT = "kakomon"
SITE = "https://www.sc-siken.com"
TAG_RE = re.compile(r'<div\b[^>]*>|</div>', re.I)


def find_div(html, open_start):
    """open_start 指向某个 <div ...> 的起始位置；深度匹配到它的 </div>。

    返回 (inner_html, 结束下标)。找不到闭合标签就返回到末尾。
    """
    m = re.match(r'<div\b[^>]*>', html[open_start:])
    if not m:
        return None, open_start
    inner_start = open_start + m.end()
    depth, i = 1, inner_start
    while i < len(html):
        t = TAG_RE.search(html, i)
        if not t:
            break
        if t.group(0).lower().startswith('</'):
            depth -= 1
            if depth == 0:
                return html[inner_start:t.start()], t.end()
        else:
            depth += 1
        i = t.end()
    return html[inner_start:], len(html)


def div_after(html, marker, from_idx=0):
    """找 marker 之后的第一个 <div>，返回其 inner HTML（没有则 None）。"""
    i = html.find(marker, from_idx)
    if i < 0:
        return None
    j = html.find('<div', i + len(marker))
    if j < 0:
        return None
    inner, _ = find_div(html, j)
    return inner


def div_with_class(html, class_name):
    """找 <div class="...class_name...">（类名精确匹配），返回其 inner HTML。"""
    for m in re.finditer(r'<div\b[^>]*\bclass="([^"]*)"[^>]*>', html):
        if class_name in m.group(1).split():
            inner, _ = find_div(html, m.start())
            return inner
    return None


def extract_page(path, exam, no):
    html = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'<main id="mainCol">(.*?)</main>', html, re.S)
    if not m:
        raise RuntimeError(f"{path}: 找不到 <main>")
    main = m.group(1)

    h2 = re.search(r'<h2>(.*?)</h2>', main, re.S)
    title = re.sub(r'<[^>]+>', '', h2.group(1)).strip() if h2 else ''

    pdf = re.search(r'href="(//www\.sc-siken\.com/pdf/[^"]+\.pdf)"', main)
    pdf_url = 'https:' + pdf.group(1) if pdf else f"{SITE}/pdf/{exam}/pm{no}.pdf"

    goal = div_after(main, '>出題趣旨</h3>') or ''

    # 設問N：按 <h3 ...>設問N</h3> 切块，块内第一个 div 是 pm_answer（模範解答），
    # class="ansbg" 的 div 是解説（广告块 ads_wrap 在 ansbg 之后，深度匹配天然排除）
    setumon = []
    for blk in re.split(r'(?=<h3\b)', main):
        hm = re.match(r'<h3[^>]*>\s*(設問\d+)\s*</h3>', blk)
        if not hm:
            continue
        ans = div_after(blk, '</h3>')
        bg = div_with_class(blk, 'ansbg')
        setumon.append({
            'no': hm.group(1),
            'answer': (ans or '').strip(),
            'explain': (bg or '').strip(),
        })

    return {
        'id': f'pm{no}',
        'no': no,
        'title': title,
        'pdf_url': pdf_url,
        'source_url': f"{SITE}/kakomon/{exam}/pm{no}.html",
        'goal': goal.strip(),
        'setumon': setumon,
    }


def main():
    ap = argparse.ArgumentParser(description="抽取午后 HTML 的答案/解説")
    ap.add_argument('--exam', required=True, help='考期 ID，多个用逗号分隔')
    ap.add_argument('--root', default=ROOT)
    args = ap.parse_args()

    for ex in [e.strip() for e in args.exam.split(',') if e.strip()]:
        d = os.path.join(args.root, ex)
        pages = sorted(
            (f for f in os.listdir(d) if re.fullmatch(r'pm\d+\.html', f)),
            key=lambda f: int(re.search(r'\d+', f).group()))
        if not pages:
            print(f"{ex}: 没有 pm HTML（该考期源站可能只有 IPA 官方 PDF）")
            continue
        out = []
        for f in pages:
            no = int(re.search(r'\d+', f).group())
            item = extract_page(os.path.join(d, f), ex, no)
            n_s = len(item['setumon'])
            bad = [s['no'] for s in item['setumon'] if not s['answer'] or not s['explain']]
            goal_len = len(re.sub(r'<[^>]+>', '', item['goal']))
            print(f"  {ex}/{f}: 設問 {n_s} 个，趣旨正文 {goal_len} 字符"
                  + (f"，空块 {bad}" if bad else ""))
            out.append(item)
        path = os.path.join(d, 'pm_jp.json')
        json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"{ex}: {len(out)} 页 -> {path}")


if __name__ == '__main__':
    sys.exit(main())
