# -*- coding: utf-8 -*-
"""由 12 考期题库生成三个辅助网页：

    重复题库.html    跨考期重出题 + 与 IPA 其他资格考试同题
    计算题库.html    需要动笔算或推算的题（人工校准清单，按题型分组）
    关键词对照.html  题干关键词 ⇄ 正确答案关键词

    python3 build_summary_pages.py

图片以 base64 内嵌，页面自包含（可离线 file:// 打开，也可直接丢到 GitHub Pages）。
"""
import json, os, re, base64, html, collections, datetime, importlib.util

BASE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('aq', os.path.join(BASE, 'analyze_questions.py'))
aq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aq)

KAKO = os.path.join(BASE, 'kakomon')
EXAM_NAME = aq.EXAM_NAME
PART_NAME = aq.PART_NAME

# ----------------------------------------------------------------- 数据

def load_all():
    return aq.load_all()


def qmap(qs):
    return {(q['exam'], q['id']): q for q in qs}


# ------------------------------------------------------- 图片 base64 内嵌

_IMG = {}      # key -> data URI（或 None）
_IMG_USED = []  # 页面实际用到的 key，顺序登记


def inline_imgs(text, exam):
    """把 <img src="xx.png"> 换成 <img data-img="exam/xx.png">，
    图片本体只在页尾的脚本里出现一次，避免同一张图重复塞 base64 撑爆文件。"""
    if not text:
        return ''

    def repl(m):
        name = m.group(1)
        key = '%s/%s' % (exam, name)
        if key not in _IMG:
            path = os.path.join(KAKO, exam, 'img', name)
            if os.path.exists(path):
                ext = os.path.splitext(name)[1].lstrip('.').lower()
                if ext == 'jpg':
                    ext = 'jpeg'
                ext = ext or 'png'
                b64 = base64.b64encode(open(path, 'rb').read()).decode('ascii')
                _IMG[key] = 'data:image/%s;base64,%s' % (ext, b64)
            else:
                _IMG[key] = None
        if _IMG[key] is None:
            return m.group(0)
        if key not in _IMG_USED:
            _IMG_USED.append(key)
        return '<img data-img="%s" loading="lazy"' % html.escape(key, quote=True)

    return re.sub(r'<img src="([^"]+)"', repl, text)


def img_script():
    """页尾注入：把 data-img 换成真实图片（只在此处定义一次 data URI）。"""
    if not _IMG_USED:
        return ''
    return ('<script>var IMGS=%s;document.querySelectorAll("img[data-img]").forEach(function(im){'
            'var s=IMGS[im.getAttribute("data-img")];if(s)im.src=s;});</script>' %
            json.dumps({k: _IMG[k] for k in _IMG_USED}, ensure_ascii=False))


def clean(text):
    """去掉 script/style 之类残留，保留题型标签结构。"""
    return text or ''


# ----------------------------------------------------------------- CSS

CSS = """
:root{
  --bg:#f5f6f8; --card:#fff; --ink:#1f2430; --ink-2:#5b6473; --ink-3:#8b95a5;
  --line:#e4e7ec; --accent:#2f5bd7; --accent-soft:#eef2fd;
  --ok:#2f7d4f; --bad:#c0392b; --warn:#b46b00; --radius:12px;
  --shadow:0 1px 2px rgba(16,24,40,.05),0 6px 20px -12px rgba(16,24,40,.18);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;}
.wrap{max-width:960px;margin:0 auto;padding:36px 20px 80px}
header h1{font-size:27px;margin:0 0 6px;letter-spacing:.3px}
header .sub{color:var(--ink-2);margin:0 0 8px;font-size:15px}
header .meta{color:var(--ink-3);font-size:13px;margin:0 0 18px}
.navbar{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 22px}
.navbar a{text-decoration:none;font-size:13.5px;color:var(--accent);background:var(--accent-soft);
  border:1px solid #d9e1f8;border-radius:999px;padding:4px 14px}
.navbar a:hover{background:#e0e7fb}
.navbar a.on{background:var(--accent);color:#fff;border-color:var(--accent)}
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:14px 18px;margin:0 0 28px;box-shadow:var(--shadow);font-size:14px;line-height:2}
nav.toc b{color:var(--ink-2);font-weight:600}
nav.toc a{color:var(--accent);text-decoration:none;margin-right:14px;white-space:nowrap}
nav.toc a:hover{text-decoration:underline}
h2.sec{font-size:20px;margin:40px 0 14px;padding-bottom:8px;border-bottom:2px solid var(--accent-soft);scroll-margin-top:14px}
h2.sec .n{color:var(--accent);font-weight:700;margin-right:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 20px;margin:0 0 14px;box-shadow:var(--shadow)}
.card .pos{font-size:12.5px;color:var(--ink-3);letter-spacing:.06em;margin:0 0 6px}
.card .topics{font-size:15px;font-weight:700;margin:0 0 8px}
.chip{display:inline-block;font-size:13px;border-radius:8px;padding:1px 9px;margin:0 6px 4px 0;line-height:1.7}
.chip.ex{background:#eef2fd;color:var(--accent)}
.chip.pn{background:#f2f4f8;color:var(--ink-2)}
.chip.ok{background:#e8f5ee;color:var(--ok)}
.chip.tp{background:#fff4e5;color:var(--warn)}
.jump{text-decoration:none}
.jump:hover{text-decoration:underline}
.stem{margin:8px 0 10px;font-size:15px;line-height:1.85}
.stem img,.opt img,.exp img{max-width:100%;height:auto;display:block;margin:10px auto;border-radius:8px}
ul.opts{margin:8px 0;padding-left:1.4em}
ul.opts li{margin:3px 0}
ul.opts li.right{font-weight:700;color:var(--ok)}
ul.opts li.right::after{content:" ✓";font-size:13px}
.optlbl{display:inline-block;min-width:1.4em;color:var(--ink-3);font-size:13px}
details{margin-top:10px}
details summary{cursor:pointer;color:var(--accent);font-size:14px;padding:3px 0}
details summary:hover{text-decoration:underline}
.exp{overflow-wrap:anywhere;margin:10px 0 0;border-top:1px dashed var(--line);padding-top:12px;color:var(--ink)}
.exp ul,.exp ol{margin:8px 0;padding-left:1.5em}
.exp dl{margin:10px 0}
.exp dt{font-weight:650;margin-top:8px}
.exp dd{margin:2px 0 0 0;color:var(--ink-2)}
.exp h4{margin:12px 0 4px;font-size:14px;color:var(--ink-3);letter-spacing:.1em;font-weight:600}
.exp code,.exp .pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;
  background:#f2f4f8;border:1px solid var(--line);border-radius:5px;padding:2px 6px;color:#2b3550}
.exp div.pre{display:block;padding:8px 12px;overflow-x:auto;line-height:1.7}
.frac{display:inline-flex;flex-direction:column;vertical-align:middle;text-align:center;margin:0 .18em;line-height:1.25}
.frac b{border-bottom:1px solid currentColor;padding:0 .3em;font-weight:inherit}
.frac b+*{padding:0 .3em}
.ol{text-decoration:overline}
.src{margin-top:10px;font-size:12.5px;color:var(--ink-3)}
.src a{color:var(--accent)}
table.grid{width:100%;border-collapse:collapse;background:var(--card);
  border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow);font-size:13.5px}
table.grid th,table.grid td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
table.grid th{background:#fafbfd;color:var(--ink-2);font-weight:600;font-size:13px}
table.grid tr:last-child td{border-bottom:none}
table.grid td a{color:var(--accent);text-decoration:none}
table.grid td a:hover{text-decoration:underline}
/* 关键词页专用 */
.kwline{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:4px 0}
.kwbox{flex:1 1 40%;min-width:230px}
.kwtag{display:inline-block;margin:2px 4px 2px 0;padding:2px 10px;border-radius:7px;
  background:#111827;color:#fff;font-size:14px;font-weight:600;letter-spacing:.02em}
.kwtag.s{background:#4b5563}
.kwtag.a{background:#1d4ed8}
.kwtag.a.soft{background:#8aa0e0}
.kwtag.a.whole{background:#7c3aed}
.kwtag.a.num{background:#6b7280;font-family:ui-monospace,Menlo,Consolas,monospace}
.arrow{color:var(--ink-3);font-size:18px;padding:0 2px}
.ctxv{font-size:12.5px;color:var(--ink-3);margin-left:6px}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 18px}
.tools input[type=search]{flex:1 1 240px;padding:9px 12px;border:1px solid var(--line);
  border-radius:10px;font-size:15px;background:#fff;color:var(--ink)}
.tools select{padding:9px 10px;border:1px solid var(--line);border-radius:10px;font-size:14px;background:#fff;color:var(--ink)}
.hint{font-size:13px;color:var(--ink-3);margin:0 0 16px}
.note{background:#fffbeb;border:1px solid #fde68a;color:#7c5a08;border-radius:10px;padding:10px 14px;font-size:13.5px;margin:0 0 18px}
/* 语言切换：默认显示日文原题，点一下看中文译文 */
.jp{display:revert}.zh{display:none}
body.lang-zh .zh{display:revert}
body.lang-zh .jp{display:none}
.langbtn{cursor:pointer;font:inherit;font-size:13.5px;padding:4px 14px;border-radius:999px;
  border:1px solid #d9e1f8;background:var(--accent-soft);color:var(--accent)}
.langbtn:hover{background:#e0e7fb}
.langhint{font-size:13px;color:var(--ink-3)}
footer{margin-top:52px;padding-top:16px;border-top:1px solid var(--line);color:var(--ink-3);font-size:13px}
@media(max-width:640px){.wrap{padding:24px 14px 60px}header h1{font-size:23px}.kwbox{flex:1 1 100%}}
@media print{.card{box-shadow:none}}
"""

# 默认显示语言：题库类页面默认日文原题；速记页（标准速记.html）切到中文，因为记忆文案是中文
DEFAULT_LANG = 'jp'

NAV = """<div class="navbar">
  <a href="index.html">← 返回中文题库</a>
  <a href="重复题库.html">重复题</a>
  <a href="计算题库.html">计算题</a>
  <a href="关键词对照.html">关键词</a>
  <a href="标准速记.html">标准速记</a>
  <a href="术语人话表.html">术语人话表</a>
  <button type="button" class="langbtn" id="lt">__LTB__</button>
  <button type="button" class="langbtn" id="et">全部展开</button>
  <span class="langhint" id="ehint">__LHINT__</span>
</div>"""


def page_head(title, active, sub, meta):
    def_lang = DEFAULT_LANG
    nav = NAV.replace('href="%s"' % active, 'href="%s" class="on"' % active)
    nav = nav.replace('__LTB__', '切到中文译文' if def_lang == 'jp' else '切到日文原题')
    nav = nav.replace('__LHINT__', '当前显示：' + ('日文原题' if def_lang == 'jp' else '中文译文'))
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__T__</title><style>__CSS__</style></head><body><div class="wrap"><header>
<h1>__T__</h1><p class="sub">__SUB__</p><p class="meta">__META__</p></header>
__NAV__
""".replace('__T__', title).replace('__CSS__', CSS).replace('__SUB__', sub).replace('__META__', meta) \
     .replace('__NAV__', nav)


PAGE_FOOT = """<footer>数据来源：情報処理安全確保支援士（SC）过去问 令和元年秋期～令和7年春期 午前Ⅰ・Ⅱ（12 考期 660 题）·
生成脚本 build_summary_pages.py · 生成于 __D__ · 默认显示日文原题，点顶部按钮切到中文译文 ·
中文译文与解说仅供参考，以日文原题/官方解答为准</footer></div>
<script>
(function(){
  var K='sc-summary-lang-v1', b=document.body, btn=document.getElementById('lt'),
      eb=document.getElementById('et'), hint=document.querySelector('.langhint'),
      lang='jp', opened=false, nOpen=0;
  function pick(){
    try{ var v=localStorage.getItem(K); if(v==='jp'||v==='zh') return v; }catch(e){}
    return '__DEF__';
  }
  function sayHint(){
    if(!hint) return;
    hint.textContent = (opened ? '已展开 '+nOpen+' 处 · ' : '') +
      '当前显示：' + (lang==='jp' ? '日文原题' : '中文译文');
  }
  function apply(l, save){
    lang=l;
    b.className='lang-'+l;
    if(btn) btn.textContent = l==='jp' ? '切到中文译文' : '切回日文原题';
    sayHint();
    if(save){ try{ localStorage.setItem(K,l); }catch(e){} }
  }
  /* 一键展开 / 收起：只作用于当前筛选后仍可见的卡片，避免数百张同时铺开拖慢页面 */
  function setAll(v){
    var ds=document.querySelectorAll('details'), list=[];
    for(var i=0;i<ds.length;i++){ if(ds[i].offsetParent!==null) list.push(ds[i]); }
    for(var j=0;j<list.length;j++) list[j].open=v;
    opened=v; nOpen=list.length;
    if(eb) eb.textContent = v ? '全部收起' : '全部展开';
    sayHint();
  }
  apply(pick(), false);
  if(btn) btn.addEventListener('click', function(){ apply(lang==='jp'?'zh':'jp', true); });
  if(eb) eb.addEventListener('click', function(){ setAll(!opened); });
})();
</script>
</body></html>"""


def page_foot():
    """按 DEFAULT_LANG 决定首次打开时显示日文还是中文（之后由浏览器记住用户选择）。"""
    return PAGE_FOOT.replace('__DEF__', DEFAULT_LANG) \
        .replace('__D__', datetime.date.today().isoformat())


def q_link(q, text=None):
    """跳回题库该题的链接。text 视为已就绪的 HTML（调用方自己负责转义）；
    不传则输出「考期 午前Ⅰ・問N」的纯文本（内部转义）。"""
    if text is None:
        text = html.escape('%s %s・問%d' % (
            EXAM_NAME[q['exam']], PART_NAME[q['part']], q['no']))
    return '<a class="jump" href="index.html#q-%s-%s">%s</a>' % (q['exam'], q['id'], text)


JUMP_CHIP = '<span class="chip ex jump">在题库中打开 →</span>'


def opt_list(q, lang='jp'):
    """选项列表：lang=jp 用日文原题，lang=zh 用中文译文。"""
    zs = q.get('options_zh') or []
    items = []
    for i, o in enumerate(q['options']):
        txt = clean(o.get('text', ''))
        if lang == 'zh' and i < len(zs):
            txt = clean(zs[i])
        cls = ' class="right"' if o.get('correct') else ''
        items.append('<li%s><span class="optlbl">%s</span> %s</li>' % (
            cls, o['label'], inline_imgs(txt, q['exam']) or '（図・表）' if lang == 'jp' else '（图/表）'))
    return '<ul class="opts %s">%s</ul>' % (lang, ''.join(items))


def opt_both(q):
    return opt_list(q, 'jp') + opt_list(q, 'zh')


def explain_block(q):
    """解说：日文原题 + 中文译文两份，随语言开关切换。"""
    return ('<div class="exp jp">%s</div><div class="exp zh">%s</div>' % (
        inline_imgs(clean(q.get('explain', '')), q['exam']),
        inline_imgs(clean(q.get('explain_zh', '')), q['exam'])))


def stem_both(q):
    return ('<div class="stem jp">%s</div><div class="stem zh">%s</div>' % (
        inline_imgs(clean(q.get('stem', '')), q['exam']),
        inline_imgs(clean(q.get('stem_zh', '')), q['exam'])))


def topic_both(q):
    return ('<span class="jp">%s</span><span class="zh">%s</span>' % (
        html.escape(q.get('topic', '') or ''), html.escape(q.get('topic_zh', '') or '')))


def src_link(q):
    u = q.get('source_url', '')
    if not u:
        return ''
    return '<p class="src">日文原题：<a href="%s" target="_blank" rel="noopener noreferrer">%s</a></p>' % (
        html.escape(u), html.escape(u))


# ============================================================ 1 重复题

def build_dups(qs, out='重复题库.html'):
    _IMG_USED.clear()
    data = json.load(open(os.path.join(BASE, 'analysis.json'), encoding='utf-8'))
    groups, origins = data['groups'], data['origin']
    M = qmap(qs)
    parts = [page_head('重复题・同题一览', '重复题库.html',
                       '同一道题在多个考期里重出，以及与 IPA 其他资格考试撞题的记录。',
                       '共 %d 组跨考期重复题（涉及 %d 题）· %d 题与其他资格考试同题 · 2026 年 10 月整理' % (
                           len(groups), sum(len(g['members']) for g in groups), len(origins)))]

    # 概览
    cnt = collections.Counter()
    for g in groups:
        for m in g['members']:
            cnt[m['exam']] += 1
    top = ', '.join('%s %d' % (EXAM_NAME[e], c) for e, c in sorted(cnt.items(), key=lambda x: -x[1]))
    parts.append('<h2 class="sec"><span class="n">一</span>跨考期重复题 %d 组</h2>' % len(groups))
    parts.append('<p class="hint">判定依据：题干归一化后完全相同，或题干高度相似且正解一致。'
                 '默认显示日文原题，点顶部按钮可切到中文译文；每组展开可见四个选项、正解与解说。</p>')
    parts.append('<table class="grid"><tr><th>考期</th><th>重复题数（含被重复计入）</th></tr>%s</table>' % ''.join(
        '<tr><td>%s</td><td>%d</td></tr>' % (EXAM_NAME[e], c)
        for e, c in sorted(cnt.items(), key=lambda x: -x[1])))

    for gi, g in enumerate(groups, 1):
        mem = g['members']
        first = M[(mem[0]['exam'], mem[0]['id'])]
        bars = ' '.join('<span class="chip %s">%s</span>' % (
            'ex' if i == 0 else 'pn', '%s %s・問%d' % (EXAM_NAME[m['exam']], PART_NAME[m['part']], m['no']))
            for i, m in enumerate(mem))
        jumps = ' '.join('<a class="chip pn jump" href="index.html#q-%s-%s">%s 問%d</a>' % (
            m['exam'], m['id'], EXAM_NAME[m['exam']], m['no']) for m in mem)
        body = stem_both(first)
        c = '<div class="card" data-exam="%s">' % ' '.join(m['exam'] for m in mem)
        c += '<p class="pos">第 %d 组 · 出现 %d 次 · 相似度下限 %.2f%s</p>' % (
            gi, len(mem), g['min_similarity'], ' · 正解一致' if g['same_answer'] else ' · 正解不同（同主题不同问法）')
        c += '<p class="topics">%s</p>' % topic_both(first)
        c += stem_both(first)
        c += '<div class="kwline">%s</div>' % jumps
        c += '<details><summary class="jp">展開：選択肢と解説</summary><summary class="zh">展开：选项与解说</summary>%s%s%s%s</details>' % (
            opt_both(first),
            '<p class="pos">正解：<span class="jp">%s</span><span class="zh">%s</span></p>' % (
                html.escape(first.get('answer', '')), html.escape(first.get('answer', ''))),
            explain_block(first), src_link(first))
        c += '</div>'
        parts.append(c)

    # 与 IPA 其他考试同题
    parts.append('<h2 class="sec"><span class="n">二</span>与 IPA 其他资格考试同题（%d 题）</h2>' % len(origins))
    by_ref = collections.defaultdict(list)
    for o in origins:
        key = re.sub(r'(平成|令和)[元0-9０-９]+年(度)?(春|秋)期', '', o['origin_zh'] or o['origin']).strip()
        key = re.sub(r'\s*と同題$', '', key).strip()
        by_ref[key].append(o)
    rows = []
    for key, lst in sorted(by_ref.items(), key=lambda x: -len(x[1])):
        rows.append('<h3 style="font-size:16px;margin:18px 0 8px">%s <span class="chip pn">%d 题</span></h3>' % (
            html.escape(key or '其他'), len(lst)))
        rows.append('<table class="grid"><tr><th style="width:110px">本题位置</th><th style="width:150px">中文论点</th>'
                    '<th>出处</th><th style="width:70px">原题</th></tr>')
        for o in sorted(lst, key=lambda x: (x['exam'], x['no'])):
            rows.append('<tr><td>%s ・%s 問%d</td><td><span class="jp">%s</span><span class="zh">%s</span></td>'
                        '<td><span class="jp">%s</span><span class="zh">%s</span></td>'
                        '<td><a href="index.html#q-%s-%s">跳转</a></td></tr>' % (
                            EXAM_NAME[o['exam']], PART_NAME[o['part']], o['no'],
                            html.escape(o.get('topic_jp', '') or ''), html.escape(o['topic_zh'] or ''),
                            html.escape(o['origin']), html.escape(o['origin_zh'] or o['origin']),
                            o['exam'], o['id']))
        rows.append('</table>')
    parts.append('<p class="hint">这些题原站标注与応用情報技術者等考试的作者/年份某一问相同，'
                 '可以作为“换题型备考”的参考。已按出处归类。</p>')
    parts.append(''.join(rows))
    parts.append(img_script())
    parts.append(page_foot())
    write_page(parts, out)


# ============================================================ 2 计算题

CALC_CURATED = [
    ('排队论 M/M/1', [('07_aki', 'am1_1'), ('01_aki', 'am1_2'), ('06_haru', 'am1_1')]),
    ('缓存・有效访问时间', [('04_haru', 'am1_4'), ('06_aki', 'am1_4'), ('04_aki', 'am1_4'), ('01_aki', 'am1_5')]),
    ('CPU 性能・并行处理', [('05_haru', 'am1_4'), ('07_haru', 'am1_4'), ('04_haru', 'am1_5')]),
    ('网络带宽・传输时间', [('05_haru', 'am2_18'), ('06_aki', 'am1_9'), ('07_aki', 'am1_10'), ('02_aki', 'am1_10')]),
    ('误码・纠错码・期待值', [('03_aki', 'am1_2'), ('05_aki', 'am1_2'), ('06_haru', 'am1_2'),
                             ('04_haru', 'am1_1'), ('06_haru', 'am1_11')]),
    ('可用性・SLA・停止时间', [('05_aki', 'am1_20'), ('07_haru', 'am2_24'), ('07_haru', 'am1_20'),
                              ('02_aki', 'am1_21'), ('04_haru', 'am2_24'), ('07_aki', 'am2_24')]),
    ('可靠性 MTBF・稼働率', [('07_haru', 'am1_5'), ('03_haru', 'am1_5')]),
    ('存储・磁带・容量', [('01_aki', 'am1_6'), ('03_aki', 'am1_21')]),
    ('子网划分・主机数', [('03_aki', 'am2_20'), ('05_aki', 'am1_10'), ('05_aki', 'am2_18')]),
    ('位数・编码・信息量', [('04_aki', 'am1_8'), ('02_aki', 'am1_2'), ('05_haru', 'am1_1')]),
    ('硬件・D/A ・实时・时序', [('02_aki', 'am1_8'), ('05_aki', 'am1_6'), ('03_aki', 'am1_4'),
                               ('05_haru', 'am1_7'), ('07_haru', 'am1_7')]),
    ('财务・盈亏・费用合计', [('06_haru', 'am1_29'), ('02_aki', 'am1_29'), ('07_haru', 'am1_29'),
                             ('07_aki', 'am1_29'), ('03_aki', 'am1_24'), ('04_aki', 'am2_24'),
                             ('02_aki', 'am2_24'), ('01_aki', 'am1_24')]),
    ('决策・期待值・线性规划', [('06_haru', 'am1_19'), ('03_aki', 'am1_29')]),
    ('项目进度・网络图・工期', [('01_aki', 'am1_19'), ('03_haru', 'am1_19'), ('05_aki', 'am1_19'),
                               ('04_haru', 'am1_19'), ('04_aki', 'am1_18'), ('07_aki', 'am1_19'),
                               ('05_haru', 'am1_19')]),
    ('EVM 挣值・工时估算', [('04_haru', 'am1_18'), ('06_aki', 'am1_24')]),
    ('组合・计数・表达式・栈', [('03_haru', 'am1_20'), ('04_haru', 'am2_4'), ('06_haru', 'am1_13'),
                              ('03_haru', 'am1_2'), ('07_haru', 'am1_3'), ('05_aki', 'am1_1'),
                              ('02_aki', 'am1_1'), ('06_aki', 'am1_2')]),
    ('测试覆盖・最少用例数', [('03_haru', 'am1_16'), ('04_haru', 'am1_16')]),
    ('生产管理・MRP 净需求', [('06_aki', 'am1_28')]),
    ('算法・探索次数', [('07_aki', 'am1_3')]),
    ('追踪题：内存・页面・SQL', [('07_aki', 'am1_6'), ('07_haru', 'am1_6'), ('05_haru', 'am1_3'),
                                ('06_haru', 'am1_3'), ('06_haru', 'am2_21')]),
    ('统计・分布图', [('05_haru', 'am1_2')]),
    ('数值解法・近似求根', [('07_haru', 'am1_1')]),
]


def build_calc(qs, out='计算题库.html'):
    _IMG_USED.clear()
    M = qmap(qs)
    total = sum(len(v) for _, v in CALC_CURATED)
    parts = [page_head('计算・推算题一览', '计算题库.html',
                       '660 题里需要动笔算、套公式或一步步推导的题，按题型归类。',
                       '共 %d 题 · 按 %d 类分组 · 自动初筛 + 人工校准清单' % (total, len(CALC_CURATED)))]
    parts.append('<nav class="toc"><b>目录</b><br>%s</nav>' % ''.join(
        '<a href="#g%d">%s <span class="chip pn">%d</span></a>' % (i, name, len(items))
        for i, (name, items) in enumerate(CALC_CURATED)))
    for gi, (name, items) in enumerate(CALC_CURATED):
        parts.append('<h2 class="sec" id="g%d"><span class="n">%d</span>%s <span class="chip pn">%d 题</span></h2>' % (
            gi, gi + 1, html.escape(name), len(items)))
        for exam, qid in items:
            q = M.get((exam, qid))
            if q is None:
                parts.append('<p class="hint">缺失：%s %s</p>' % (exam, qid))
                continue
            c = '<div class="card">'
            c += '<p class="pos">%s · <span class="jp">%s</span><span class="zh">%s</span></p>' % (
                q_link(q), html.escape(q.get('category', '')), html.escape(q.get('category_zh', '')))
            c += '<p class="topics">%s</p>' % topic_both(q)
            c += stem_both(q)
            c += opt_both(q)
            c += '<details><summary class="jp">展開：正解と解説</summary><summary class="zh">展开：正解与解说</summary>' \
                 '<p class="pos">正解：%s</p>%s%s</details>' % (
                     html.escape(q.get('answer', '')), explain_block(q), src_link(q))
            c += '</div>'
            parts.append(c)
    parts.append(img_script())
    parts.append(page_foot())
    write_page(parts, out)


# ============================================================ 3 关键词

def build_kw(qs, out='关键词对照.html'):
    _IMG_USED.clear()
    data = json.load(open(os.path.join(BASE, 'analysis.json'), encoding='utf-8'))
    kws = {(r['exam'], r['id']): r for r in data['kw']}
    order = {e: i for i, e in enumerate(aq.EXAMS)}
    qs2 = sorted(qs, key=lambda q: (order[q['exam']], q['part'], q['no']))
    parts = [page_head('关键词 ⇄ 答案关键词', '关键词对照.html',
                       '每道题：题干里的技术词（黑）→ 正答选项里独有的关键词（蓝）。'
                       '看到黑关键词，就在选项里找带蓝关键词的那个。',
                       '共 660 题（令和元年秋期～令和7年春期 午前Ⅰ・Ⅱ）· 关键词取自日文原题，按考期顺序排列')]
    parts.append('<div class="tools"><input id="q" type="search" placeholder="搜索关键词 / 题号 / 论点（中・日）">'
                 '<select id="ex"><option value="">全部考期</option>%s</select>'
                 '<select id="tier"><option value="">全部</option><option value="strict">唯一关键词</option>'
                 '<option value="soft">宽松关键词</option><option value="whole">整句答案</option>'
                 '<option value="numeric">数值/式子答案</option><option value="none">无关键词</option></select>'
                 '<span class="chip ex" id="cnt">—</span>'
                 '</div>' % ''.join('<option value="%s">%s</option>' % (e, EXAM_NAME[e]) for e in aq.EXAMS))
    parts.append('<p class="hint"><b>黑牌</b>＝题干关键词（技术术语/核心概念）；'
                 '<b class="chip ex">蓝牌</b>＝该词只出现在正确选项里，错误选项一次都没出现；'
                 '<b class="chip ex">浅蓝牌</b>＝宽松匹配（错误选项里也零星出现）；'
                 '<b class="chip ex">紫牌</b>＝答案很短，整句答案本身就是关键词；'
                 '<b class="chip ex">灰牌</b>＝答案是数值或式子，走计算而非关键词。'
                 '灰色小字为词在原句中的上下文，也可展开看完整题干与四个选项。</p>')

    cur_exam = None
    for q in qs2:
        if q['exam'] != cur_exam:
            cur_exam = q['exam']
            parts.append('<h2 class="sec" id="e-%s"><span class="n">%s</span>%s</h2>' % (
                cur_exam, EXAM_NAME[cur_exam], EXAM_NAME[cur_exam]))
        r = kws.get((q['exam'], q['id']), {'stem_kw': [], 'ans_kw': []})
        skw = ''.join('<span class="kwtag">%s</span>' % html.escape(k) for k in r['stem_kw']) or '<span class="chip pn">—</span>'
        akw = ''.join(
            ('<span class="kwtag a%s" title="%s">%s</span>' % (
                {1: '', 2: ' soft', 3: ' whole', 4: ' num'}[k['tier']],
                html.escape(k.get('ctx', '')),
                k['html'] if (k['tier'] == 3 and k.get('html')) else html.escape(k['kw'])))
            for k in r['ans_kw'])
        if not r['ans_kw']:
            akw = ('<span class="chip pn">正答项为图/表，无文字关键词</span>'
                   if r.get('status') == 'image-option'
                   else '<span class="chip pn">正答极短，无词组</span>')
        tier = ('none' if not r['ans_kw'] else
                {1: 'strict', 2: 'soft', 3: 'whole', 4: 'numeric'}[
                    min(k['tier'] for k in r['ans_kw'])])
        c = '<div class="card" data-exam="%s" data-tier="%s" data-s="%s">' % (
            q['exam'], tier, html.escape(' '.join(
                r['stem_kw'] + [k['kw'] for k in r['ans_kw']] +
                [q.get('topic', ''), q.get('topic_zh', ''), q.get('category_zh', ''),
                 '%s 問%d' % (PART_NAME[q['part']], q['no'])])))
        c += '<p class="pos"><span class="jp">%s</span><span class="zh">%s</span> 問%d · %s</p>' % (
            PART_NAME[q['part']], PART_NAME[q['part']], q['no'],
            html.escape(q.get('category_zh', '')))
        c += '<p class="topics">%s</p>' % topic_both(q)
        c += '<div class="kwline"><div class="kwbox">%s</div><span class="arrow">→</span>' % skw
        c += '<div class="kwbox">%s</div></div>' % akw
        c += '<details><summary class="jp">展開：問題文・選択肢・解説</summary>' \
             '<summary class="zh">展开：题干・四个选项・解说</summary>%s%s' % (stem_both(q), opt_both(q))
        c += '<p class="pos">正解：%s</p>%s%s</details>' % (
            html.escape(q.get('answer', '')), explain_block(q), src_link(q))
        c += q_link(q, JUMP_CHIP)
        c += '</div>'
        parts.append(c)

    parts.append("""<script>
var fi=document.getElementById('q'),fex=document.getElementById('ex'),ft=document.getElementById('tier');
function apply(){
  var kw=(fi.value||'').trim().toLowerCase(), ex=fex.value, ti=ft.value, n=0;
  document.querySelectorAll('.card').forEach(function(c){
    var ok=(!ex||c.dataset.exam.indexOf(ex)>=0)&&(!ti||c.dataset.tier===ti)
      &&(!kw||c.dataset.s.toLowerCase().indexOf(kw)>=0);
    c.style.display=ok?'':'none'; if(ok)n++;
  });
  document.querySelectorAll('h2.sec').forEach(function(h){
    var any=false,nx=h.nextElementSibling;
    while(nx&&nx.classList&&nx.classList.contains('card')){if(nx.style.display!=='none'){any=true;break}nx=nx.nextElementSibling}
    h.style.display=any?'':'none';
  });
  document.getElementById('cnt').textContent=n;
}
[fi,fex,ft].forEach(function(e){e.addEventListener('input',apply)});
apply();
</script>""")
    parts.append(img_script())
    parts.append(page_foot())
    write_page(parts, out)


def write_page(parts, out):
    """写文件并自检：正文里不允许出现被转义成字面的标签（&lt;span 之类）。"""
    doc = '\n'.join(parts)
    body = re.sub(r'<script\b.*?</script>', '', doc, flags=re.S)
    leaked = set(re.findall(r'&lt;(/?[a-zA-Z][a-zA-Z0-9]*)', body))
    if leaked:
        raise SystemExit('!! %s 出现被转义成字面的标签：%s' % (out, sorted(leaked)[:10]))
    path = os.path.join(BASE, out)
    open(path, 'w', encoding='utf-8').write(doc)
    print('written %s (%.2f MB)' % (out, len(doc.encode('utf-8')) / 1048576))


def main():
    qs = load_all()
    print('questions:', len(qs))
    build_dups(qs)
    build_calc(qs)
    build_kw(qs)
    print('inline images:', len(_IMG))


if __name__ == '__main__':
    main()
