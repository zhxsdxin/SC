# -*- coding: utf-8 -*-
"""生成「标准组织速记.html」：把 12 考期里的组织・标准・制度类题目按实体归类，
每个实体给一句作用概要 + 记忆钩子（谐音/联想）+ 正解里独有的关键词 + 易混提醒，
并挂上原题（日文原题与中文译文双份，默认显示中文）。

    python3 build_std_page.py

记忆文案来自 std_memo.json（人工整理），题面来自 kakomon/*/questions_zh.json。
"""
import json, os, re, html, importlib.util

BASE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('bsp', os.path.join(BASE, 'build_summary_pages.py'))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

B.DEFAULT_LANG = 'zh'          # 速记页默认中文（记忆钩子本身是中文）

aq = B.aq
EXAM_NAME, PART_NAME = B.EXAM_NAME, B.PART_NAME

# ----------------------------------------------------------------- 额外样式
EXTRA_CSS = """
.cat{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 22px;font-size:13.5px}
.mcard{position:relative}
.mcard .mname{font-size:19px;font-weight:700;margin:0 8px 6px 0;display:inline-block}
.mcard .owner{font-size:12.5px;color:var(--ink-3);margin:0 0 10px}
.mrow{display:flex;gap:10px;margin:8px 0 0;align-items:flex-start}
.mrow .lbl{flex:0 0 76px;font-size:12.5px;color:var(--ink-3);padding-top:3px;letter-spacing:.06em}
.mrow .val{flex:1 1 auto;min-width:0;font-size:14.5px;line-height:1.85}
.mrow.hook .val{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:9px 13px;color:#7c5a08}
.mrow.trap .val{background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:9px 13px;color:#a12d1d}
.kwbox2{display:flex;flex-wrap:wrap;gap:6px}
.mrow .val .full{color:var(--ink-2);font-size:13px;display:block;margin-top:2px}
.qbox{border-top:1px dashed var(--line);margin-top:12px;padding-top:10px}
.qbox .qitem{margin:0 0 14px}
.qbox .qpos{font-size:12.5px;color:var(--ink-3);margin:0 0 4px}
.qbox .stem{margin:4px 0 8px}
@media(max-width:640px){.mrow{flex-direction:column;gap:2px}.mrow .lbl{flex:none}}
"""


def hook_html(txt):
    """记忆钩子：保留换行，转义后再换行转 <br>。"""
    return html.escape(txt or '').replace('\n', '<br>')


def build(qs, out='标准速记.html'):
    B._IMG_USED.clear()
    data = json.load(open(os.path.join(BASE, 'std_memo.json'), encoding='utf-8'))
    M = B.qmap(qs)
    cats = data['cats']
    items = data['items']
    nq = len({tuple(x) for it in items for x in it['qs']})

    parts = [B.page_head(
        '标准・组织・制度速记', '标准速记.html',
        '12 考期里凡是问「某个组织是干什么的」「某份标准写了什么」「某份指南说了啥」的题，'
        '都归到这里：一句作用概要 + 一个记忆钩子 + 正解里独有的关键词。',
        '共 %d 个速记点 · 覆盖 %d 道题 · 默认显示中文，点顶部按钮可切到日文原题' % (len(items), nq))]

    parts.append('<div class="tools">'
                 '<input id="q" type="search" placeholder="搜索：名称 / 关键词 / 谐音 / 日语原文">'
                 '<select id="cat"><option value="">全部分类</option>%s</select>'
                 '<span class="chip ex" id="cnt">—</span></div>'
                 % ''.join('<option value="%s">%s</option>' % (c['id'], c['name']) for c in cats))
    parts.append('<p class="hint"><b>怎么背</b>：先看<b>作用概要</b>知道它是什么，再看<b>记忆钩子</b>把它钉住；'
                 '临场答题时只需在选项里找<b>正解关键词</b>——这些词只出现在正确选项里，'
                 '错误选项一次都没出现过。<b>易混提醒</b>是这套题最爱挖的坑。</p>')

    order = {c['id']: i for i, c in enumerate(cats)}
    groups = {}
    for it in items:
        groups.setdefault(it['cat'], []).append(it)

    for cid, name in [(c['id'], c['name']) for c in cats]:
        lst = groups.get(cid, [])
        if not lst:
            continue
        cnt = len({tuple(x) for it in lst for x in it['qs']})
        parts.append('<h2 class="sec" id="c-%s"><span class="n">%s</span>%s '
                     '<span class="chip pn">%d 个速记点 · %d 题</span></h2>' % (
                         cid, '一二三四五六七八九十'[order[cid]], html.escape(name), len(lst), cnt))
        for it in lst:
            hay = ' '.join([it['name'], it.get('full', ''), it.get('owner', ''), it['role'],
                            it['hook'], ' '.join(it['kw']), it.get('trap', ''),
                            ' '.join('%s %s' % (e, i) for e, i in it['qs']),
                            aq.EXAM_NAME.get(it['qs'][0][0], '')])
            for e, i in it['qs']:
                q = M.get((e, i))
                if q:
                    hay += ' ' + B.aq.strip_tags(q.get('stem_zh', ''))
            c = '<div class="card mcard" data-cat="%s" data-s="%s">' % (
                cid, html.escape(hay))
            c += '<span class="mname">%s</span><span class="chip pn">%s</span>' % (
                html.escape(it['name']), html.escape(name))
            if it.get('full'):
                c += '<p class="owner">%s　·　%s</p>' % (
                    html.escape(it['full']), html.escape(it.get('owner', '')))
            else:
                c += '<p class="owner">%s</p>' % html.escape(it.get('owner', ''))
            c += '<div class="mrow"><div class="lbl">作用概要</div><div class="val">%s</div></div>' % html.escape(it['role'])
            c += '<div class="mrow hook"><div class="lbl">🧠 记忆钩子</div><div class="val">%s</div></div>' % hook_html(it['hook'])
            c += ('<div class="mrow"><div class="lbl">🎯 正解关键词</div><div class="val">'
                  '<div class="kwbox2">%s</div></div></div>'
                  % ''.join('<span class="kwtag a">%s</span>' % html.escape(k) for k in it['kw']))
            if it.get('trap'):
                c += '<div class="mrow trap"><div class="lbl">⚠️ 易混提醒</div><div class="val">%s</div></div>' % html.escape(it['trap'])
            # 关联原题
            c += '<details><summary class="jp">関連問題を開く（%d 問）</summary>' \
                 '<summary class="zh">展开关联真题（%d 题）</summary><div class="qbox">' % (len(it['qs']), len(it['qs']))
            for e, i in it['qs']:
                q = M.get((e, i))
                if not q:
                    continue
                c += '<div class="qitem"><p class="qpos">%s %s ・問%d · %s　%s</p>' % (
                    B.q_link(q), PART_NAME[q['part']], q['no'],
                    html.escape(q.get('category_zh', '')), B.JUMP_CHIP)
                c += '<p class="topics">%s</p>' % B.topic_both(q)
                c += B.stem_both(q) + B.opt_both(q)
                c += '<p class="pos">正解：%s</p>%s%s</div>' % (
                    html.escape(q.get('answer', '')), B.explain_block(q), B.src_link(q))
            c += '</div></details></div>'
            parts.append(c)

    parts.append("""<script>
var fi=document.getElementById('q'),fc=document.getElementById('cat');
function apply(){
  var kw=(fi.value||'').trim().toLowerCase(), cat=fc.value, n=0;
  document.querySelectorAll('.mcard').forEach(function(c){
    var ok=(!cat||c.dataset.cat===cat) && (!kw||c.dataset.s.toLowerCase().indexOf(kw)>=0);
    c.style.display=ok?'':'none'; if(ok)n++;
  });
  document.querySelectorAll('h2.sec').forEach(function(h){
    var any=false,nx=h.nextElementSibling;
    while(nx&&nx.classList&&nx.classList.contains('mcard')){if(nx.style.display!=='none'){any=true;break}nx=nx.nextElementSibling}
    h.style.display=any?'':'none';
  });
  document.getElementById('cnt').textContent=n;
}
[fi,fc].forEach(function(e){e.addEventListener('input',apply)});
apply();
</script>""")
    parts.append(B.img_script())
    parts.append(B.page_foot())
    B.write_page(parts, out)


def main():
    import sys
    sys.modules.setdefault('bsp', B)
    B.CSS = B.CSS + EXTRA_CSS
    build(B.load_all())


if __name__ == '__main__':
    main()
