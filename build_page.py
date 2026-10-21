#!/usr/bin/env python3
"""把 questions_zh.json 生成一个干净的单页中文题库（图片内嵌，离线可用）。

用法：
    python3 build_page.py                              # 默认把 EXAM 里列的考期合并成一页
    python3 build_page.py --exam 07_haru               # 只出一个考期
    python3 build_page.py --exam 07_aki,07_haru        # 指定几个考期合并
    python3 build_page.py --out index.html             # 指定输出名（发布用）

产出：工作区根目录下的 <题库标题>.html，单文件、无外部依赖，双击即可看。
"""

import argparse
import base64
import json
import os
import re
import sys

EXAM = "05_aki,05_haru,06_aki,06_haru,07_aki,07_haru"  # 可传多个考期，逗号分隔，合并成一页
ROOT = "kakomon"
PART_CN = {"am1": "午前Ⅰ", "am2": "午前Ⅱ"}

EXAM_NAME = {                     # 考期 ID → 时期名（页面显示、筛选用）
    "05_aki": "令和5年秋期",
    "05_haru": "令和5年春期",
    "06_aki": "令和6年秋期",
    "06_haru": "令和6年春期",
    "07_aki": "令和7年秋期",
    "07_haru": "令和7年春期",
}

TITLE = {
    "05_aki": "情報処理安全確保支援士 令和5年秋期 午前Ⅰ・午前Ⅱ 中文题库",
    "05_haru": "情報処理安全確保支援士 令和5年春期 午前Ⅰ・午前Ⅱ 中文题库",
    "06_aki": "情報処理安全確保支援士 令和6年秋期 午前Ⅰ・午前Ⅱ 中文题库",
    "06_haru": "情報処理安全確保支援士 令和6年春期 午前Ⅰ・午前Ⅱ 中文题库",
    "07_aki": "情報処理安全確保支援士 令和7年秋期 午前Ⅰ・午前Ⅱ 中文题库",
    "07_haru": "情報処理安全確保支援士 令和7年春期 午前Ⅰ・午前Ⅱ 中文题库",
}

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --bg:#f5f6f8; --card:#fff; --ink:#1f2430; --ink-2:#5b6473; --ink-3:#8b95a5;
  --line:#e4e7ec; --accent:#2f5bd7; --accent-soft:#eef2fd;
  --ok:#2f7d4f; --bad:#c8372d; --ok-soft:#eaf5ee; --bad-soft:#fdeceb;
  --radius:12px; --shadow:0 1px 2px rgba(16,24,40,.05),0 6px 20px -12px rgba(16,24,40,.18);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
.topbar{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line)}
.topbar-in{max-width:1180px;margin:0 auto;padding:16px 22px 14px;
  display:flex;flex-wrap:wrap;gap:14px 18px;align-items:flex-end;justify-content:space-between}
.brand h1{margin:0;font-size:19px;letter-spacing:.2px;font-weight:650}
.brand .sub{margin:4px 0 0;color:var(--ink-3);font-size:13px}
.tools{display:flex;flex-wrap:nowrap;gap:10px;align-items:center}
.tools input[type=search],.tools select{font:inherit;font-size:14px;padding:8px 11px;border:1px solid var(--line);
  border-radius:9px;background:#fff;color:var(--ink);min-width:120px;outline:none}
.tools input[type=search]{min-width:0;flex:0 1 200px}
.tools select#cat{max-width:150px}
.tools input[type=search]:focus,.tools select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.sw{display:inline-flex;align-items:center;gap:8px;font-size:14px;color:var(--ink-2);white-space:nowrap;
  background:#fff;border:1px solid var(--line);border-radius:9px;padding:8px 12px;cursor:pointer;user-select:none}
.sw input{margin:0;accent-color:var(--accent);width:15px;height:15px}
.score{font-size:13px;color:var(--ink-2);background:#fff;border:1px solid var(--line);
  border-radius:9px;padding:8px 12px;white-space:nowrap;flex:0 0 auto}
.score b{color:var(--accent);font-weight:650}
.layout{max-width:1180px;margin:0 auto;padding:22px;display:grid;
  grid-template-columns:262px minmax(0,1fr);gap:22px;align-items:start}
aside{position:sticky;top:104px;max-height:calc(100vh - 128px);overflow:auto;
  background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 10px 16px}
aside h3{margin:6px 8px 8px;font-size:12px;letter-spacing:.14em;color:var(--ink-3);font-weight:600}
aside h3+a,aside h3+ol{margin-top:0}
aside .tocgroup{margin:0 0 14px}
aside .tocpart{margin:8px 8px 3px;font-size:12.5px;color:var(--ink-2);font-weight:600}
aside ol{list-style:none;margin:0 0 10px;padding:0}
aside li a{display:block;padding:6px 9px;border-radius:8px;color:var(--ink-2);font-size:14px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
aside li a:hover{background:#f2f4f8;color:var(--ink)}
aside li a.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
aside li a.done::after{content:"✓";float:right;color:var(--ok);font-weight:700}
aside li a.wrong::after{content:"✗";float:right;color:var(--bad);font-weight:700}
aside li a.todo::after{content:"○";float:right;color:var(--ink-3);font-weight:700;opacity:.5}
aside .hint{margin:10px 8px 0;color:var(--ink-3);font-size:12px;line-height:1.7}
main{display:flex;flex-direction:column;gap:20px;min-width:0}
.q{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:20px 24px 18px;scroll-margin-top:110px}
.q.hide{display:none}
.qhead{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin-bottom:12px}
.badge{display:inline-block;font-size:12px;font-weight:650;color:var(--accent);background:var(--accent-soft);
  border-radius:999px;padding:3px 10px;white-space:nowrap;text-decoration:none;transition:.14s}
.badge:hover{background:var(--accent);color:#fff}
.qhead h2{margin:0;font-size:16.5px;font-weight:650;line-height:1.5;flex:1 1 240px;min-width:180px}
.tag{font-size:12px;color:var(--ink-3);white-space:nowrap}
.tag.exam{color:var(--ink-2);background:#f2f4f8;border-radius:999px;padding:2px 9px}
.single-exam .tag.exam{display:none}
.stem{color:var(--ink);overflow-wrap:anywhere}
.stem ul,.stem ol{margin:8px 0;padding-left:1.5em}
.stem li{margin:3px 0}
/* 勾「显示日文原题」时：题干与选项就地换成日文原题，并隐藏每题论点（topic）便于自测 */
.lang-zh{display:block}
.lang-jp{display:none}
body.jp .lang-zh{display:none}
body.jp .lang-jp{display:block}
body.jp .topic{display:none}
body.jp .toc-topic{display:none}
.jpbody{font-family:"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic",
  "Meiryo","Noto Sans JP",-apple-system,sans-serif}
.none{color:var(--ink-3)}
.opts{list-style:none;margin:14px 0 0;padding:0;display:flex;flex-direction:column;gap:8px}
.opt{display:flex;gap:11px;align-items:flex-start;padding:10px 13px;border:1px solid var(--line);
  border-radius:10px;cursor:pointer;transition:.14s;background:#fcfcfd}
.opt:hover{border-color:#c9d2e6;background:#f8faff}
.opt .lbl{flex:0 0 26px;height:26px;border-radius:8px;background:#f0f2f6;color:var(--ink-2);
  display:grid;place-items:center;font-size:14px;font-weight:600;margin-top:1px}
.opt .txt{flex:1;min-width:0;overflow-wrap:anywhere}
.opt.sel{border-color:var(--accent);background:#f5f8ff}
.opt.sel .lbl{background:var(--accent);color:#fff}
.opt.right{border-color:var(--ok);background:var(--ok-soft)}
.opt.right .lbl{background:var(--ok);color:#fff}
.opt.wrong{border-color:var(--bad);background:var(--bad-soft)}
.opt.wrong .lbl{background:var(--bad);color:#fff}
.opt .mark{font-weight:700;font-size:14px}
.opt.right .mark{color:var(--ok)}
.opt.wrong .mark{color:var(--bad)}
.optimg{margin:4px 0 2px}
.acts{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:14px}
.btn{font:inherit;font-size:13.5px;padding:7px 14px;border-radius:9px;border:1px solid var(--line);
  background:#fff;color:var(--ink-2);cursor:pointer}
.btn:hover{border-color:var(--accent);color:var(--accent);background:#f8faff}
details.jp{margin-left:auto}
details.jp summary{font-size:13px;color:var(--ink-3);cursor:pointer;list-style:none;padding:7px 12px;
  border:1px dashed var(--line);border-radius:9px}
details.jp summary::-webkit-details-marker{display:none}
details.jp[open] summary{border-style:solid;color:var(--accent);border-color:#cdd8f2}
.jpbody{margin-top:12px;padding:14px 16px;background:#fafbfc;border:1px solid var(--line);
  border-radius:10px;color:var(--ink-2);font-size:14.5px;line-height:1.8}
.jpbody .jplabel{font-size:12px;letter-spacing:.12em;color:var(--ink-3);margin:0 0 6px}
.jpbody .jplabel:not(:first-child){margin-top:14px}
.ans{margin-top:16px;border-top:1px dashed var(--line);padding-top:14px}
.ans .head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.ans .k{font-size:12px;color:var(--ink-3);letter-spacing:.1em}
.pill{font-weight:700;color:#fff;background:var(--ok);border-radius:8px;padding:2px 12px;font-size:14px}
.res{font-size:13.5px;font-weight:600}
.res.ok{color:var(--ok)}
.res.bad{color:var(--bad)}
.exp{overflow-wrap:anywhere}
.exp ul,.exp ol{margin:8px 0;padding-left:1.5em}
.exp dl{margin:10px 0}
.exp dt{font-weight:650;margin-top:8px;color:var(--ink)}
.exp dd{margin:2px 0 0 0;color:var(--ink-2)}
.exp h4{margin:12px 0 4px;font-size:14px;color:var(--ink-3);letter-spacing:.1em;font-weight:600}
.exp code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13.5px;
  background:#f2f4f8;border:1px solid var(--line);border-radius:5px;padding:1px 5px;color:#2b3550}
.exp img,.stem img,.opt img,.optimg img{max-width:100%;height:auto;display:block;margin:10px auto;
  border-radius:8px}
.frac{display:inline-flex;flex-direction:column;vertical-align:middle;text-align:center;
  margin:0 .18em;line-height:1.25}
.frac b{border-bottom:1px solid currentColor;padding:0 .3em;font-weight:inherit}
.frac b+*{padding:0 .3em}
.ol,.exp .ol{text-decoration:overline}
.src{margin-top:12px;font-size:12.5px;color:var(--ink-3)}
.empty{padding:36px;text-align:center;color:var(--ink-3);background:var(--card);
  border:1px dashed var(--line);border-radius:var(--radius);display:none}
footer{max-width:1180px;margin:0 auto;padding:8px 22px 46px;color:var(--ink-3);font-size:12.5px;line-height:1.9}
.totop{position:fixed;right:24px;bottom:26px;width:42px;height:42px;border-radius:50%;border:1px solid var(--line);
  background:#fff;color:var(--ink-2);cursor:pointer;box-shadow:var(--shadow);display:none;font-size:17px}
@media(max-width:980px){
  .layout{grid-template-columns:1fr;padding:16px}
  aside{position:static;max-height:none;order:2}
  main{order:1}
  .tools{flex-wrap:wrap}
  .tools input[type=search]{min-width:0;flex:1 1 100%}
}
@media print{
  .topbar,aside,.totop{display:none}
  .layout{display:block;padding:0}
  .q{box-shadow:none;border:none;page-break-inside:avoid}
}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-in">
    <div class="brand">
      <h1>__H1__</h1>
    </div>
    <div class="tools">
      <input id="q" type="search" placeholder="搜索题号 / 关键词（中・日）">
      <select id="exam" aria-label="按考期筛选"></select>
      <select id="part" aria-label="正确率统计范围"></select>
      <select id="cat" aria-label="按分类筛选"></select>
      <label class="sw"><input type="checkbox" id="showAll">显示全部答案</label>
      <label class="sw" title="题干与选项就地切换为日文原题，并隐藏每题论点（便于自测）"><input type="checkbox" id="showJp">显示日文原题（隐藏论点）</label>
      <span class="score" id="score">已答 <b>0</b>/__TOTAL__</span>
    </div>
  </div>
</header>

<div class="layout">
  <aside>
    <nav id="toc"></nav>
    <p class="hint">点选项即判分，答对为绿色、答错为红色，答案自动记录在本机。顶部可切换考期，并选择午前Ⅰ/Ⅱ/全部来统计正确率；切换「显示全部答案」可一次性核对整页，切换「显示日文原题」可把题干与选项换成日文原题，并隐藏每题论点以便自测。</p>
  </aside>
  <main id="list"></main>
</div>

<div class="empty" id="empty">没有匹配的题目，换个关键词或清空筛选试试。</div>

<footer>
  <p>__FOOT__</p>
</footer>
<button class="totop" id="totop" aria-label="回到顶部">↑</button>

<script id="imgs" type="application/json">__IMAGES__</script>
<script id="qexams" type="application/json">__EXAMS__</script>
<script id="qdata" type="application/json">__DATA__</script>
<script>
(function () {
  const DATA = JSON.parse(document.getElementById('qdata').textContent);
  const IMGS = JSON.parse(document.getElementById('imgs').textContent);
  const EXAMS = JSON.parse(document.getElementById('qexams').textContent);
  const KEY = 'sc-' + EXAMS.map(e => e.id).join('+') + '-progress-v1';
  const PART_NAME = { am1: '午前Ⅰ', am2: '午前Ⅱ' };
  const state = loadState();
  const list = document.getElementById('list');
  const empty = document.getElementById('empty');
  const scoreEl = document.getElementById('score');
  const showAll = document.getElementById('showAll');
  const showJp = document.getElementById('showJp');
  const qInput = document.getElementById('q');
  const examSel = document.getElementById('exam');
  const catSel = document.getElementById('cat');
  const partSel = document.getElementById('part');
  const links = {};

  const save = () => localStorage.setItem(KEY, JSON.stringify(state));

  // 作答记录以 uid 为键；同时把旧版单考期的记录并进来，升级不丢已有进度
  function loadState() {
    let cur = {};
    try { cur = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { cur = {}; }
    EXAMS.forEach(ex => {
      let old = {};
      try { old = JSON.parse(localStorage.getItem('sc-' + ex.id + '-progress-v1') || '{}'); }
      catch (e) { old = {}; }
      Object.keys(old).forEach(qid => {
        const uid = 'q-' + ex.id + '-' + qid;
        if (cur[uid] === undefined) cur[uid] = old[qid];
      });
    });
    return cur;
  }

  // ---------- 考期 / 分类下拉 ----------
  if (EXAMS.length < 2) document.body.classList.add('single-exam');
  examSel.innerHTML = '<option value="">全部考期</option>' +
    EXAMS.map(e => '<option value="' + e.id + '">' + e.name + '</option>').join('');

  partSel.innerHTML = '<option value="">正确率：全部（午前Ⅰ+Ⅱ）</option>' +
    '<option value="am1">正确率：午前Ⅰ</option>' +
    '<option value="am2">正确率：午前Ⅱ</option>';

  const cats = [...new Set(DATA.map(q => q.category_zh))].sort();
  catSel.innerHTML = '<option value="">全部分类</option>' +
    cats.map(c => '<option value="' + c.replace(/"/g, '&quot;') + '">' + c + '</option>').join('');

  // 筛选下拉记住上次选择（刷新后恢复，避免总是回到默认「全部考期」）
  const FILTER_KEY = 'sc-' + EXAMS.map(e => e.id).join('+') + '-filter-v1';
  const setSel = (sel, v) => {
    if (!v) return;
    for (const o of sel.options) if (o.value === v) { sel.value = v; return; }
  };
  const saveFilter = () =>
    localStorage.setItem(FILTER_KEY, JSON.stringify({
      exam: examSel.value, part: partSel.value, cat: catSel.value
    }));
  let savedFilter = {};
  try { savedFilter = JSON.parse(localStorage.getItem(FILTER_KEY) || '{}'); } catch (e) {}
  if (savedFilter && typeof savedFilter === 'object') {
    setSel(examSel, savedFilter.exam);
    setSel(partSel, savedFilter.part);
    setSel(catSel, savedFilter.cat);
  }

  // ---------- 生成卡片 ----------
  const cards = {};
  DATA.forEach((q, idx) => {
    const el = document.createElement('article');
    el.className = 'q';
    el.id = q.uid;
    el.dataset.part = q.part;
    el.dataset.exam = q.exam;
    el.dataset.cat = q.category_zh;
    el.dataset.idx = idx;

    const NONE_ZH = '<span class="none">（见上方的选项图）</span>';
    const NONE_JP = '<span class="none">（図を参照）</span>';
    const optionBlock = q.option_image
      ? '<div class="optimg">' + q.option_image + '</div>'
      : '';
    // 勾「显示日文原题」时题干与选项就地换日文，并隐藏论点；选中/判分状态不受影响
    const opts = q.options.map((o, i) => {
      const zh = (q.options_zh[i] || '').trim() || NONE_ZH;
      const jp = (o.text || '').trim() || NONE_JP;
      return '<li class="opt" data-label="' + o.label + '" data-correct="' + o.correct + '">' +
          '<span class="lbl">' + o.label + '</span>' +
          '<span class="txt">' +
            '<span class="lang-zh">' + zh + '</span>' +
            '<span class="lang-jp">' + jp + '</span>' +
          '</span>' +
        '</li>';
    }).join('');

    el.innerHTML =
      '<div class="qhead">' +
        '<a class="badge" href="' + q.source_url + '" target="_blank" rel="noopener noreferrer" title="跳转到原题（sc-siken.com）">' + PART_NAME[q.part] + '・問' + q.no + '</a>' +
        '<h2 class="topic">' + q.topic_zh + '</h2>' +
        '<span class="tag exam">' + q.exam_name + '</span>' +
        '<span class="tag">' + q.category_zh + '</span>' +
      '</div>' +
      '<div class="stem">' +
        '<div class="lang-zh">' + q.stem_zh + '</div>' +
        '<div class="lang-jp">' + q.stem + '</div>' +
      '</div>' + optionBlock +
      '<ul class="opts">' + opts + '</ul>' +
      '<div class="acts">' +
        '<button class="btn reveal">查看答案与详解</button>' +
        '<details class="jp"><summary>日文解説</summary><div class="jpbody">' +
          (q.origin ? '<p class="jplabel">出典</p><ul class="opts"><li class="opt" style="cursor:default">' + q.origin + '</li></ul>' : '') +
          '<p class="jplabel">解説</p><div>' + q.explain + '</div>' +
        '</div></details>' +
      '</div>' +
      '<div class="ans" hidden>' +
        '<div class="head"><span class="k">正解</span><span class="pill">' + q.answer + '</span>' +
          '<span class="res"></span></div>' +
        '<div class="exp">' + q.explain_zh + '</div>' +
        (q.origin_zh ? '<div class="src">出典：' + q.origin_zh.replace(/<\/?li>/g, '') + '</div>' : '') +
      '</div>';

    el.querySelectorAll('img[data-img]').forEach(i => { i.src = IMGS[i.dataset.img] || ''; });
    list.appendChild(el);
    cards[q.uid] = el;
  });

  // ---------- 判分 / 显隐 ----------
  function reveal(el, mark) {
    const ans = el.querySelector('.ans');
    const res = el.querySelector('.res');
    ans.hidden = false;
    el.querySelectorAll('.opt .mark').forEach(m => m.remove());
    el.querySelectorAll('.opt').forEach(o => {
      o.classList.remove('right', 'wrong');
      const isC = o.dataset.correct === 'true';
      if (el.dataset.picked === o.dataset.label) {
        o.classList.add(isC ? 'right' : 'wrong');
        o.insertAdjacentHTML('beforeend',
          '<span class="mark">' + (isC ? '✓ 正确' : '✘ 错误') + '</span>');
      } else if (isC) {
        o.classList.add('right');
        if (el.dataset.picked) o.insertAdjacentHTML('beforeend', '<span class="mark">✓ 正解</span>');
      }
    });
    const pick = el.dataset.picked;
    if (pick && mark) {
      const right = el.querySelector('.opt[data-correct="true"]').dataset.label;
      const ok = right === pick;
      res.textContent = ok ? '你选对了' : '正确答案是 ' + right;
      res.className = 'res ' + (ok ? 'ok' : 'bad');
    }
  }

  // 统计范围：同时受「考期」与「午前Ⅰ/Ⅱ/全部」两个维度约束
  function scope() {
    const ex = examSel.value;
    const part = partSel.value;
    return DATA.filter(q => (!ex || q.exam === ex) && (!part || q.part === part));
  }

  function refreshScore() {
    const sc = scope();
    const done = sc.filter(q => state[q.uid]);
    const right = done.filter(q => {
      const el = cards[q.uid];
      return el && el.querySelector('.opt[data-correct="true"]').dataset.label === state[q.uid];
    }).length;
    scoreEl.innerHTML = '已答 <b>' + done.length + '</b>/' + sc.length +
      (done.length ? '・正确 <b>' + right + '</b>（' + Math.round(right / done.length * 100) + '%）' : '');
    DATA.forEach(q => {
      const link = links[q.uid];
      if (!link) return;
      link.classList.remove('done', 'wrong', 'todo');
      const pick = state[q.uid];
      if (!pick) { link.classList.add('todo'); return; }   // 未作答：灰色空心圈
      const el = cards[q.uid];
      const right = el && el.querySelector('.opt[data-correct="true"]').dataset.label === pick;
      link.classList.add(right ? 'done' : 'wrong');          // 对：绿勾 / 错：红叉
    });
  }

  list.addEventListener('click', e => {
    const opt = e.target.closest('.opt');
    const card = e.target.closest('.q');
    if (!card) return;
    if (opt && !opt.closest('.jpbody')) {
      card.dataset.picked = opt.dataset.label;
      card.querySelectorAll('.opt').forEach(o => o.classList.remove('sel'));
      opt.classList.add('sel');
      state[card.id] = opt.dataset.label;
      save(); refreshScore(); reveal(card, true);
      return;
    }
    if (e.target.classList.contains('reveal')) { reveal(card, false); e.target.remove(); }
  });

  showAll.addEventListener('change', () => {
    DATA.forEach(q => {
      const el = cards[q.uid];
      if (showAll.checked) reveal(el, false);
      else el.querySelector('.ans').hidden = true;
    });
  });

  // 显示日文原题 + 隐藏论点：勾选后题干/选项就地换日文，并隐藏每题论点，偏好记在本机
  const LANG_KEY = 'sc-' + EXAMS.map(e => e.id).join('+') + '-lang-v1';
  const applyLang = on => document.body.classList.toggle('jp', on);
  const savedLang = () => {                  // 兼容旧版单考期页面存下的偏好
    const v = localStorage.getItem(LANG_KEY);
    if (v) return v;
    for (const ex of EXAMS) {
      const old = localStorage.getItem('sc-' + ex.id + '-lang-v1');
      if (old) return old;
    }
    return 'zh';
  };
  showJp.checked = savedLang() === 'jp';
  applyLang(showJp.checked);
  showJp.addEventListener('change', () => {
    applyLang(showJp.checked);
    localStorage.setItem(LANG_KEY, showJp.checked ? 'jp' : 'zh');
  });

  // ---------- 目录（按考期分组，多考期才显示组标题） ----------
  const toc = document.getElementById('toc');
  toc.innerHTML = EXAMS.map(ex => {
    const qs = DATA.filter(q => q.exam === ex.id);
    return '<div class="tocgroup" data-exam="' + ex.id + '">' +
      (EXAMS.length > 1 ? '<h3>' + ex.name + '</h3>' : '') +
      ['am1', 'am2'].map(part => {
        const sub = qs.filter(q => q.part === part);
        if (!sub.length) return '';
        return '<div class="tocpart-block" data-part="' + part + '">' +
          '<p class="tocpart">' + PART_NAME[part] + '　' + sub.length + ' 题</p><ol>' +
          sub.map(q => '<li><a href="#' + q.uid + '">問' + q.no + '　<span class="toc-topic">' + q.topic_zh + '</span></a></li>').join('') +
          '</ol></div>';
      }).join('') + '</div>';
  }).join('');

  document.querySelectorAll('aside a').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      document.getElementById(a.getAttribute('href').slice(1))
        .scrollIntoView({ block: 'start' });
    });
    links[a.getAttribute('href').slice(1)] = a;
  });
  const io = new IntersectionObserver(es => {
    es.forEach(en => {
      if (!en.isIntersecting) return;
      Object.values(links).forEach(l => l.classList.remove('on'));
      const l = links[en.target.id];
      if (l) l.classList.add('on');
    });
  }, { rootMargin: '-15% 0px -75% 0px' });
  Object.values(cards).forEach(c => io.observe(c));

  // ---------- 筛选 ----------
  function applyFilter() {
    const kw = qInput.value.trim().toLowerCase();
    const cat = catSel.value;
    const ex = examSel.value;
    let n = 0;
    DATA.forEach(q => {
      const el = cards[q.uid];
      const hay = (q.exam_name + ' ' + q.id + ' ' + q.topic_zh + ' ' + q.category_zh + ' ' +
        q.stem_zh + ' ' + q.options_zh.join(' ') + ' ' + q.explain_zh + ' ' + q.topic + ' ' +
        q.stem).toLowerCase();
      const ok = (!kw || hay.includes(kw)) && (!cat || q.category_zh === cat) &&
        (!ex || q.exam === ex);
      el.classList.toggle('hide', !ok);
      const link = links[q.uid];
      if (link) link.parentElement.style.display = ok ? '' : 'none';
      if (ok) n++;
    });
    // 目录：先收掉全空的「午前Ⅰ/Ⅱ」小节，再收掉整组都空掉的考期
    toc.querySelectorAll('.tocpart-block').forEach(b => {
      const shown = [...b.querySelectorAll('li')].some(li => li.style.display !== 'none');
      b.style.display = shown ? '' : 'none';
    });
    toc.querySelectorAll('.tocgroup').forEach(g => {
      const shown = [...g.querySelectorAll('.tocpart-block')].some(b => b.style.display !== 'none');
      g.style.display = shown ? '' : 'none';
    });
    empty.style.display = n ? 'none' : 'block';
  }
  qInput.addEventListener('input', applyFilter);
  catSel.addEventListener('change', () => { applyFilter(); saveFilter(); });
  examSel.addEventListener('change', () => { applyFilter(); refreshScore(); saveFilter(); });
  partSel.addEventListener('change', () => { refreshScore(); saveFilter(); });

  // ---------- 恢复上次作答 ----------
  DATA.forEach(q => {
    const pick = state[q.uid];
    if (!pick) return;
    const el = cards[q.uid];
    el.dataset.picked = pick;
    const opt = el.querySelector('.opt[data-label="' + pick + '"]');
    if (opt) opt.classList.add('sel');   // 只恢复选择状态，答案仍按开关控制
  });

  // ---------- 回顶部 ----------
  const totop = document.getElementById('totop');
  window.addEventListener('scroll', () => totop.style.display = window.scrollY > 600 ? 'block' : 'none');
  totop.addEventListener('click', () => window.scrollTo({ top: 0 }));

  applyFilter();   // 应用恢复后的考期/分类筛选
  refreshScore();

  // 带 #锚点 打开时，等卡片渲染完再滚过去
  const hash = location.hash.slice(1);
  if (hash && cards[hash]) setTimeout(() => cards[hash].scrollIntoView(), 60);
})();
</script>
</body>
</html>
"""


def collect_images(questions, img_dir, exam):
    """把某考期引用到的插图读成 data URI 字典（同一张图只存一份）。

    键是 "考期/文件名"：不同考期会有同名插图（如两边都有 21.png），
    不带前缀会互相覆盖。
    """
    names = set()
    for q in questions:
        for k in ("stem", "explain", "origin", "option_image", "stem_zh", "explain_zh", "origin_zh"):
            names |= set(re.findall(r'<img src="([^"]+)"', q.get(k) or ""))
        for o in q["options"]:
            names |= set(re.findall(r'<img src="([^"]+)"', o["text"] or ""))
        for t in q.get("options_zh", []):
            names |= set(re.findall(r'<img src="([^"]+)"', t or ""))
    imgs = {}
    for n in sorted(names):
        path = os.path.join(img_dir, n)
        if os.path.exists(path):
            with open(path, "rb") as f:
                imgs[f"{exam}/{n}"] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
        else:
            print(f"  警告：缺插图 {exam}/{n}")
    return imgs


def tag_images(q):
    """把 <img src="xx.png"> 改写成 <img data-img="考期/xx.png">，运行时再填 data URI。"""
    exam = q.get("exam", "")

    def walk(text):
        return re.sub(r'<img src="([^"]+)"[^>]*>',
                      rf'<img data-img="{exam}/\1" alt="">', text or "")

    for k in ("stem", "explain", "origin", "option_image",
              "stem_zh", "explain_zh", "origin_zh"):
        if k in q:
            q[k] = walk(q[k])
    for o in q["options"]:
        o["text"] = walk(o["text"])
    q["options_zh"] = [walk(t) for t in q.get("options_zh", [])]
    return q


def main():
    ap = argparse.ArgumentParser(description="生成单页中文题库")
    ap.add_argument("--exam", default=EXAM, help="考期 ID，多个用逗号分隔，合并成一页")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    exams = [e.strip() for e in args.exam.split(",") if e.strip()]
    if not exams:
        print("--exam 至少要给一个考期")
        return 1

    questions = []
    for ex in exams:
        data_path = os.path.join(args.root, ex, "questions_zh.json")
        if not os.path.exists(data_path):
            print(f"找不到 {data_path}，先跑 extract_questions.py --exam {ex} 并完成翻译")
            return 1
        for q in json.load(open(data_path, encoding="utf-8")):
            q["exam"] = ex
            q["exam_name"] = EXAM_NAME.get(ex, ex)
            q["uid"] = f"q-{ex}-{q['id']}"      # 页面元素 id / 锚点 / 作答记录都用它（前缀 q- 让 id 不以数字开头）
            questions.append(q)

    imgs = {}
    for ex in exams:
        img_dir = os.path.join(args.root, ex, "img")
        imgs.update(collect_images([q for q in questions if q["exam"] == ex], img_dir, ex))
    questions = [tag_images(q) for q in questions]
    n_img = sum(1 for q in questions for k in ("stem_zh", "explain_zh", "option_image")
                if "data-img" in q.get(k, ""))

    names = [EXAM_NAME.get(e, e) for e in exams]
    if len(exams) == 1:
        title = TITLE.get(exams[0], f"{exams[0]} 中文题库")
        h1 = title
    else:
        h1 = "情報処理安全確保支援士 中文题库"
        title = h1 + "（" + "・".join(names) + "）"

    foot = (f"题目与解说取自 sc-siken.com（情報処理安全確保支援士 過去問解説）{'・'.join(names)}，"
            "版权归原站所有，本页仅为个人学习用途的离线整理；译文由 AI 辅助翻译，"
            "如与原题有出入以原题为准。")

    data = json.dumps(questions, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    imgjson = json.dumps(imgs, ensure_ascii=False, separators=(",", ":"))
    examjson = json.dumps([{"id": e, "name": EXAM_NAME.get(e, e)} for e in exams],
                          ensure_ascii=False, separators=(",", ":"))

    html = (HTML.replace("__TITLE__", title).replace("__H1__", h1)
                .replace("__TOTAL__", str(len(questions)))
                .replace("__FOOT__", foot)
                .replace("__IMAGES__", imgjson.replace("<", "\\u003c"))
                .replace("__EXAMS__", examjson)
                .replace("__DATA__", data))

    out = args.out or (f"SC_{exams[0]}_中文题库.html" if len(exams) == 1 else "SC_中文题库.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    size = os.path.getsize(out) / 1024
    print(f"生成 {os.path.abspath(out)}　{size:.0f} KB　{len(questions)} 题"
          f"（{'、'.join(names)}）　内嵌插图 {n_img} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
