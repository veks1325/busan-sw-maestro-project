"""ReportViewer — 백엔드가 주는 보고서(.md)를 미리보기.

기능:
- 마크다운 렌더링(미리보기)
- 좌측 목차(헤딩 네비게이터) — 클릭 시 해당 섹션으로 스크롤
- 하단 스크롤 진행바 — 문서의 몇 %를 봤는지 표시
"""
from __future__ import annotations

import markdown as _md
import streamlit.components.v1 as components

_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
:root{--ink:#1f2430;--body:#3b4252;--muted:#6b7280;--accent:#4f6bed;
      --soft:#f6f7f9;--line:#e3e6ea;}
*{box-sizing:border-box;}
html,body{height:100%;margin:0;}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;color:var(--body);
     background:#fff;}
.wrap{display:flex;height:calc(100% - 16px);}
.toc{flex:0 0 200px;overflow:auto;border-right:1px solid var(--line);
     background:var(--soft);padding:14px 12px;}
.toc .ttl{font-size:11px;font-weight:700;letter-spacing:.5px;color:var(--muted);
     text-transform:uppercase;margin:0 0 8px;}
.toc a{display:block;padding:3px 6px;border-radius:6px;color:var(--body);
     text-decoration:none;font-size:13px;line-height:1.35;}
.toc a:hover{background:#e9edf7;color:var(--accent);}
.toc a.active{background:#e3e9fb;color:var(--accent);font-weight:600;}
.content{flex:1;overflow:auto;padding:8px 26px 28px;scroll-behavior:smooth;}
.content h1,.content h2,.content h3{color:var(--ink);scroll-margin-top:8px;}
.content h1{font-size:1.5rem;border-bottom:1px solid var(--line);padding-bottom:6px;}
.content h2{font-size:1.2rem;margin-top:1.4em;}
.content h3{font-size:1.03rem;}
.content p,.content li{font-size:0.95rem;line-height:1.7;}
.content blockquote{margin:.6em 0;padding:.4em 1em;border-left:3px solid var(--accent);
     background:var(--soft);color:var(--ink);border-radius:0 8px 8px 0;}
.content code{background:var(--soft);padding:1px 5px;border-radius:5px;
     font-family:ui-monospace,Menlo,monospace;font-size:.86em;}
.content pre{background:#1f2430;color:#e6e8ec;padding:12px;border-radius:10px;
     overflow:auto;}
.content pre code{background:none;color:inherit;padding:0;}
.content table{border-collapse:collapse;margin:.6em 0;}
.content th,.content td{border:1px solid var(--line);padding:6px 10px;font-size:.9rem;}
.content th{background:var(--soft);}
.progress{position:relative;height:10px;background:#e3e6ea;
     border-top:1px solid var(--line);}
.bar{height:100%;width:0%;background:#2b3240;transition:width .06s linear;}
</style></head><body>
<div class="wrap">
  <nav id="toc" class="toc"><div class="ttl">목차</div></nav>
  <main id="content" class="content">__BODY__</main>
</div>
<div class="progress"><div id="bar" class="bar"></div></div>
<script>
(function(){
  var content=document.getElementById('content');
  var toc=document.getElementById('toc');
  var bar=document.getElementById('bar');
  var heads=content.querySelectorAll('h1,h2,h3');
  var links=[];
  if(!heads.length){ toc.style.display='none'; }
  var n=0;
  heads.forEach(function(h){
    if(!h.id){ h.id='sec-'+(n++); }
    var a=document.createElement('a');
    a.textContent=h.textContent;
    a.href='#'+h.id;
    a.style.paddingLeft=((parseInt(h.tagName.substring(1))-1)*12+6)+'px';
    a.addEventListener('click',function(e){
      e.preventDefault();
      h.scrollIntoView({behavior:'smooth',block:'start'});
    });
    toc.appendChild(a);
    links.push({a:a,h:h});
  });
  function update(){
    var max=content.scrollHeight-content.clientHeight;
    var p= max>0 ? (content.scrollTop/max*100) : 0;
    if(p<0)p=0; if(p>100)p=100;
    bar.style.width=p.toFixed(1)+'%';
    // 현재 섹션 강조
    var top=content.scrollTop+12, cur=null;
    links.forEach(function(o){ if(o.h.offsetTop<=top) cur=o; });
    links.forEach(function(o){ o.a.classList.toggle('active', o===cur); });
  }
  content.addEventListener('scroll',update);
  window.addEventListener('resize',update);
  update();
})();
</script>
</body></html>"""


def md_to_html(md_text: str) -> str:
    """마크다운 텍스트를 HTML로 변환(헤딩 id 부여)."""
    return _md.markdown(md_text or "", extensions=["extra", "toc", "sane_lists"])


def render(md_text: str, height: int = 620) -> None:
    """보고서 미리보기(목차 + 스크롤 진행바)를 렌더한다."""
    body = md_to_html(md_text or "# 보고서\n\n내용이 없습니다.")
    doc = _TEMPLATE.replace("__BODY__", body)
    components.html(doc, height=height, scrolling=False)
