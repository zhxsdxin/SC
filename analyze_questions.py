# -*- coding: utf-8 -*-
"""12 考期 660 题的三个分析：重复题、计算题、关键词⇄答案关键词。

产出 JSON 数据文件（供 build_summary_pages.py 生成网页），也供人工抽样检查。

    python3 analyze_questions.py
"""
import json, os, re, html, collections, difflib, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
KAKO = os.path.join(BASE, 'kakomon')

EXAMS = ['01_aki', '02_aki', '03_aki', '03_haru', '04_aki', '04_haru',
         '05_aki', '05_haru', '06_aki', '06_haru', '07_aki', '07_haru']
EXAM_NAME = {
    '01_aki': '令和元年秋期', '02_aki': '令和2年秋期',
    '03_aki': '令和3年秋期', '03_haru': '令和3年春期',
    '04_aki': '令和4年秋期', '04_haru': '令和4年春期',
    '05_aki': '令和5年秋期', '05_haru': '令和5年春期',
    '06_aki': '令和6年秋期', '06_haru': '令和6年春期',
    '07_aki': '令和7年秋期', '07_haru': '令和7年春期',
}
PART_NAME = {'am1': '午前Ⅰ', 'am2': '午前Ⅱ'}


def load_all():
    qs = []
    for e in EXAMS:
        p = os.path.join(KAKO, e, 'questions_zh.json')
        d = json.load(open(p, encoding='utf-8'))
        for q in d:
            q['exam'] = e
            qs.append(q)
    return qs


def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s or '')


def canon(s):
    """归一化：去标签、去空白、全角英数转半角、统一引号。"""
    s = strip_tags(s).replace('&nbsp;', ' ')
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'[\s　]+', '', s)
    return s


# ---------------------------------------------------------------- 1. 重复题

def answer_key(q):
    """正确答案选项的归一化文本（用于判断是不是同一道题）。"""
    for o in q['options']:
        if o.get('correct'):
            return canon(o.get('text', ''))
    return ''


def dup_groups(qs):
    """精确重复（题干归一化相同）∪ 近似重复（相似度高且答案一致），union-find 合并。"""
    n = len(qs)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # 1) 精确重复
    exact = collections.defaultdict(list)
    for i, q in enumerate(qs):
        exact[canon(q['stem'])].append(i)
    exact_groups = [v for v in exact.values() if len(v) > 1]
    for g in exact_groups:
        for j in g[1:]:
            union(g[0], j)

    # 2) 近似重复：同 category 内两两比较
    bycat = collections.defaultdict(list)
    for i, q in enumerate(qs):
        bycat[q.get('category_zh', '')].append(i)
    near = []
    for idxs in bycat.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if find(i) == find(j):
                    continue
                si, sj = canon(qs[i]['stem']), canon(qs[j]['stem'])
                if not si or not sj:
                    continue
                r = difflib.SequenceMatcher(None, si, sj).ratio()
                if r < 0.86:
                    continue
                ai, aj = answer_key(qs[i]), answer_key(qs[j])
                if ai and aj and ai == aj:
                    near.append({'i': i, 'j': j, 'ratio': round(r, 3)})
                    union(i, j)
                elif not (ai and aj) and r >= 0.93:
                    near.append({'i': i, 'j': j, 'ratio': round(r, 3)})
                    union(i, j)

    clusters = collections.defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)
    groups = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda i: (EXAMS.index(qs[i]['exam']), qs[i]['part'], qs[i]['no']))
        st = canon(qs[members[0]]['stem'])
        sim = 1.0
        if len(members) > 1:
            sim = min(difflib.SequenceMatcher(None, st, canon(qs[m]['stem'])).ratio() for m in members[1:])
        same_ans = len({answer_key(qs[m]) for m in members}) == 1
        groups.append({
            'stem Canon': st,
            'members': [{'exam': qs[m]['exam'], 'id': qs[m]['id'], 'part': qs[m]['part'],
                         'no': qs[m]['no'], 'similarity': round(difflib.SequenceMatcher(
                             None, st, canon(qs[m]['stem'])).ratio(), 3)}
                        for m in members],
            'min_similarity': round(sim, 3),
            'same_answer': same_ans,
        })
    groups.sort(key=lambda g: (-len(g['members']), g['stem Canon'][:20]))
    return groups, len(exact_groups), len(near)


def origin_map(qs):
    """带 origin 标记的题（与 IPA 其他资格考试同题）。"""
    out = []
    for q in qs:
        o = strip_tags(q.get('origin', '')).strip()
        if not o:
            continue
        txt = re.sub(r'\s+', ' ', o).strip('・　 ')
        out.append({'exam': q['exam'], 'id': q['id'], 'part': q['part'], 'no': q['no'],
                    'topic_jp': strip_tags(q.get('topic', '')),
                    'origin': txt, 'origin_zh': re.sub(r'\s+', ' ', strip_tags(q.get('origin_zh', ''))).strip(),
                    'topic_zh': q.get('topic_zh', ''), 'category_zh': q.get('category_zh', '')})
    return out


# ---------------------------------------------------------------- 2. 计算题

CALC_KW = [
    (r'いくらか|いくつか|何[つら]|何回|何本|何台|何ビット|何バイト|何秒|何時間', 3),
    (r'求め(た|よ|る)|算出|導出|計算', 3),
    (r'平均|期待値|確率|標準偏差|分散|信頼区間', 3),
    (r'確率分布|ポアソン分布|正規分布|二項分布|指数分布', 2),
    (r'利用率|稼働率|稼働時間|停止時間|平均故障間隔|MTBF|MTTR|可用性', 3),
    (r'スループット|処理時間|実行時間|アクセス時間|遅延|伝送時間|帯域|ビットレート', 3),
    (r'換算| Err| %|％', 1),
    (r'式で表し|数式|フラグメント', 1),
]
CALC_MATH = [
    (r'<span class="frac"', 3),          # 分数结构
    (r'[0-9０-９]\s*[×÷＋－±*/^]\s*[0-9０-９]', 2),  # 算式
    (r'log|√|Σ|Σ|平均値|2の[0-9]乗|二進|十進|十六進', 2),
    (r'表のとおり|次の表|図のとおり', 1),
]
CALC_CATEGORY = [
    (r'離散数学|応用数学|確率|統計', 2),
    (r'基礎理論', 1),
    (r'計算機', 1),
    (r'ネットワーク.*(通信|プロトコル)', 1),
    (r'ハードウェア|コンピュータ構成', 1),
]


def calc_score(q):
    """计算题打分（>=6 判定为计算类，含各信号，便于人工复核）。"""
    stem = q['stem']
    explain = q.get('explain', '')
    opts = ' '.join(o.get('text', '') for o in q['options'])
    signals = []
    total = 0
    for pat, sc in CALC_KW:
        if re.search(pat, stem):
            total += sc
            signals.append(('题干关键词', pat, sc))
    for pat, sc in CALC_MATH:
        if re.search(pat, stem) or re.search(pat, explain):
            total += sc * 0.5 if pat != r'<span class="frac"' else sc
            signals.append(('算式/数学结构', pat, total and sc))
    for pat, sc in CALC_CATEGORY:
        if re.search(pat, q.get('category_zh', '')):
            total += sc
            signals.append(('分类', pat, sc))
    # 选项全是数值/式子 → 强信号
    otxt = [strip_tags(o.get('text', '')) for o in q['options'] if o.get('text', '').strip()]
    num_like = sum(1 for t in otxt if re.fullmatch(r'[\s0-9．.、,，%％×÷＋－±*/^()A-Za-z×秒]{1,24}', t.strip()))
    if otxt and num_like == len(otxt) and len(otxt) >= 3:
        total += 4
        signals.append(('选项形态', '四选项均为数值/算式', 4))
    # 解説里出现「～を計算」「＝算出」
    if re.search(r'[0-9０-９]+ *[×÷] *[0-9０-９]+ *[=＝]', explain):
        total += 2
        signals.append(('解説', '含算式等号', 2))
    return round(total, 1), signals


# ---------------------------------------------------------------- 3. 关键词

try:
    from fugashi import Tagger
    TAGGER = Tagger()
except Exception:
    TAGGER = None

STOP_NOUN = set('''こと もの とき ため ところ これ それ あれ どれ なに もの こと よう ほう 場合 状況 状態
説明 次 abcdefghijklmnopqrstuvwxyz 問題 問題文 選択肢 選択 以下 以上 関係 内容 手段 方法 方法論
利用 使用 実現 提供 目的 効果 意味 理由 特徴 構造 仕様 運用 対応 実施 結果 必要 検討 考え方
一つ 二つ 三つ 注意 禁令 記述 下記 上記 選択肢 回答 ア イ ウ エ オ'''.split())

NOUN_POS = {'名詞'}
SKIP_POS2 = {'非自立可能', '代名詞', '数詞', '助動詞語幹', '接尾', '副詞可能'}


def noun_chunks(text, max_n=4):
    """把连续名词合并为 N-gram 候选短语，返回 [(短语, 长度)]。"""
    text = strip_tags(text)
    if not TAGGER or not text.strip():
        return []
    words = []
    for w in TAGGER(text):
        f = w.feature
        if f.pos1 in NOUN_POS and f.pos2 not in SKIP_POS2 and len(w.surface) > 0:
            words.append(w.surface)
        else:
            words.append(None)
    # 切段
    segs, cur = [], []
    for w in words:
        if w is None:
            if len(cur) >= 1:
                segs.append(cur)
            cur = []
        else:
            cur.append(w)
    if cur:
        segs.append(cur)
    out = []
    for seg in segs:
        for i in range(len(seg)):
            for j in range(i + 1, min(len(seg), i + max_n) + 1):
                ph = ''.join(seg[i:j])
                if ph in STOP_NOUN or len(ph) < 2:
                    continue
                out.append(ph)
    return out


def has_kana_only(s):
    return bool(re.fullmatch(r'[ァ-ヴーｱ-ﾝ]+', s))


def has_katakana(s):
    return bool(re.search(r'[ァ-ヴｱ-ﾝ]', s))


def is_latin_junk(ph):
    """滤掉英文混写碎片（保留全大写缩写如 SOA / WAF / DNS）。"""
    if not re.search(r'[A-Za-z]', ph):
        return False
    return not re.fullmatch(r'[A-Z0-9\-]+', ph)


def pick_stem_kw(q):
    """题干关键词：优先カタカナ术语/长复合名词，剔除通用词，取 top。"""
    stem = strip_tags(q['stem'])
    cnt = collections.Counter(noun_chunks(stem, max_n=3))
    topic_jp = strip_tags(q.get('topic', ''))
    scored = []
    for ph, c in cnt.items():
        if ph in STOP_NOUN or len(ph) < 3:
            continue
        if re.fullmatch(r'[0-9\s、。，．,.%％]+', ph):
            continue
        if is_latin_junk(ph):
            continue
        score = 0
        if has_kana_only(ph):
            score += 3                       # 片假名术语（メモリインターリーブ等）
        elif has_katakana(ph):
            score += 2                       # 含片假名的复合词
        elif re.fullmatch(r'[A-Z0-9\-]+', ph):
            score += 2                       # 全大写缩写（SOA/WAF/ISP）
        score += min(len(ph), 8) * 0.6       # 越具体越好
        score += (c - 1) * 1.0               # 题干里重复出现
        if topic_jp and ph in topic_jp:
            score += 3                       # 出现在论点标题里
        if q.get('explain') and ph in strip_tags(q['explain']):
            score += 1.5                     # 解説里复述
        if has_kana_only(ph) and len(ph) <= 3:
            score -= 1.5                     # 过短的片假名词（如「メモリ」）
        scored.append((score, ph))
    scored.sort(reverse=True)
    out, seen_sub = [], []
    for sc, ph in scored:
        if any((ph in s or s in ph) and ph != s for s in seen_sub):
            continue
        out.append(ph)
        seen_sub.append(ph)
        if len(out) >= 3:
            break
    return out


def pick_answer_kw(q):
    """答案关键词：正确选项中出现、且未出现在任何错误选项中的词组（唯一性筛选）。

    返回 (结果列表, status)。每条含 kw / tier / ctx：
      tier1 = 严格唯一（任何错误选项都未出现）
      tier2 = 宽松（错误选项中出现次数 ≤ 半数的才是备选，仅在 tier1 为空时启用）
    """
    correct = None
    wrong_txt = []
    for o in q['options']:
        t = strip_tags(o.get('text', ''))
        if o.get('correct'):
            correct = o
        else:
            wrong_txt.append(t)
    if correct is None:
        return [], 'no-correct'
    ct = strip_tags(correct.get('text', '')).strip()
    if not ct:
        return [], 'image-option'
    explain = strip_tags(q.get('explain', ''))
    candidates = collections.Counter(noun_chunks(ct, max_n=4))

    def build(strict):
        scored = []
        for ph, c in candidates.items():
            if len(ph) < 2 or ph in STOP_NOUN:
                continue
            if re.fullmatch(r'[0-9\s、。，．,.%％×÷＋－±*/^()]+', ph):
                continue
            if is_latin_junk(ph):
                continue
            hit = sum(1 for t in wrong_txt if ph in t)
            if strict and hit:
                continue                     # 唯一性：错误选项里不能出现
            if not strict and hit > max(1, len(wrong_txt) // 2):
                continue                     # 宽松：多数错误选项都有 → 太泛
            score = min(len(ph), 10) * 0.8
            score += (c - 1) * 1.2
            score -= hit * 1.5               # 出现在错误选项里扣分
            if has_kana_only(ph):
                score += 2
            elif has_katakana(ph):
                score += 1.2
            elif re.fullmatch(r'[A-Z0-9\-]+', ph):
                score += 1.5
            if explain and ph in explain:    # 强相关：解説复述该词
                score += 2.5
            if has_kana_only(ph) and len(ph) <= 2:
                score -= 2
            scored.append((score, ph))
        scored.sort(reverse=True)
        out, seen = [], []
        for sc, ph in scored:
            if any((ph in s or s in ph) and ph != s for s in seen):
                continue
            out.append({'kw': ph, 'tier': 1 if strict else 2, 'ctx': context_of(ct, ph)})
            seen.append(ph)
            if len(out) >= 4:
                break
        return out

    res = build(strict=True)
    if res:
        return res, 'ok'
    res = build(strict=False)
    if res:
        return res, 'ok-soft'
    # 兜底：答案本身很短（公式/符号/单个术语），直接把整个答案当关键词
    plain = re.sub(r'\s+', ' ', strip_tags(ct)).strip()
    if 0 < len(plain) <= 26 and plain not in [re.sub(r'\s+', ' ', t).strip() for t in wrong_txt]:
        frag = re.sub(r'<img[^>]*>', '', correct.get('text', '')).strip()
        # 纯数值/式子答案 → 标 tier4（这类题靠算，不靠关键词识别）
        tier = 4 if re.fullmatch(r'[\d\s.,%＋−－×÷＝=()*/^A-Za-z]+', plain) else 3
        return [{'kw': plain, 'tier': tier, 'ctx': plain, 'html': frag}], 'ok-whole'
    return [], 'no-phrase'


def context_of(text, kw, pad=14):
    """答案关键词在正确选项中的上下文片段（便于回看语境）。"""
    i = text.find(kw)
    if i < 0:
        return ''
    s = max(0, i - pad)
    e = min(len(text), i + len(kw) + pad)
    frag = text[s:e].strip()
    if s > 0:
        frag = '…' + frag
    if e < len(text):
        frag = frag + '…'
    return frag


def main():
    qs = load_all()
    print('questions:', len(qs))

    groups, n_exact, n_near = dup_groups(qs)
    print('dup groups:', len(groups), '(exact groups %d, near pairs %d)' % (n_exact, n_near))
    org = origin_map(qs)
    print('origin-tagged:', len(org))

    calc = []
    for q in qs:
        sc, sig = calc_score(q)
        if sc >= 6:
            calc.append({'exam': q['exam'], 'id': q['id'], 'part': q['part'], 'no': q['no'],
                         'score': sc, 'signals': [s[0] + ':' + s[1] for s in sig]})
    print('calc questions:', len(calc))

    kw = []
    fail = collections.Counter()
    for q in qs:
        sks = pick_stem_kw(q)
        aks, status = pick_answer_kw(q)
        kw.append({'exam': q['exam'], 'id': q['id'], 'part': q['part'], 'no': q['no'],
                   'stem_kw': sks, 'ans_kw': aks, 'status': status})
        fail[status] += 1
    print('keyword rows:', len(kw), dict(fail))

    json.dump({'groups': groups, 'origin': org, 'calc': calc, 'kw': kw},
              open(os.path.join(BASE, 'analysis.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
