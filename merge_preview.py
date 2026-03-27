# -*- coding: utf-8 -*-
"""Merge Trinity shell with Netlify index main content + scoped CSS."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRINITY = ROOT / "트리니티여성의원_요실금.html"
INDEX = ROOT / "index.html"
OUT = ROOT / "트리니티여성의원_요실금.html"


def extract_index_style(css: str) -> str:
    m = re.search(r"<style>([\s\S]*?)</style>", css, re.I)
    if not m:
        raise SystemExit("No <style> in index.html")
    return m.group(1).strip()


def extract_main_html(html: str) -> str:
    m = re.search(r'<section[\s\S]{0,800}?id="hero"', html)
    if not m:
        raise SystemExit("hero section not found")
    start = m.start()
    footer_pos = html.find("<footer")
    if footer_pos < 0:
        raise SystemExit("footer not found")
    chunk = html[:footer_pos]
    end = chunk.rfind("</section>")
    if end < 0:
        raise SystemExit("no </section> before footer")
    return html[start : end + len("</section>")].strip()


def scope_selectors_list(sel: str) -> str:
    parts = []
    depth = 0
    buf = []
    for ch in sel:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    out = []
    prefix = "#trinity-preview-content"
    for p in parts:
        if not p:
            continue
        if p.startswith(prefix):
            out.append(p)
            continue
        if p == "body":
            out.append(prefix)
        elif p == ":root":
            out.append(prefix)
        elif p.startswith("::"):
            out.append(prefix + p)
        else:
            out.append(prefix + " " + p)
    return ", ".join(out)


def scope_css_block(css: str) -> str:
    """Naive but workable: walk chars, scope top-level rules."""
    css = re.sub(r"/\*[\s\S]*?\*/", "", css)
    i = 0
    n = len(css)
    out = []
    scope = "#trinity-preview-content"

    def skip_ws(j):
        while j < n and css[j] in " \t\n\r":
            j += 1
        return j

    while i < n:
        i = skip_ws(i)
        if i >= n:
            break
        if css.startswith("@font-face", i) or css.startswith("@keyframes", i):
            depth = 0
            start = i
            j = css.find("{", i)
            if j < 0:
                break
            depth = 1
            j += 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            out.append(css[start:j])
            i = j
            continue
        if css.startswith("@media", i):
            j = css.find("{", i)
            if j < 0:
                break
            pre = css[i:j].strip()
            depth = 1
            j += 1
            inner_start = j
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            inner = css[inner_start : j - 1]
            scoped_inner = scope_css_block(inner)
            out.append(f"{pre} {{\n{scoped_inner}\n}}")
            i = j
            continue
        j = css.find("{", i)
        if j < 0:
            break
        selectors = css[i:j].strip()
        depth = 1
        j += 1
        body_start = j
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[body_start : j - 1]
        scoped_sel = scope_selectors_list(selectors)
        out.append(f"{scoped_sel} {{\n{body}\n}}")
        i = j
    return "\n".join(out)


def dedupe_style_blocks_by_id(html: str, style_id: str) -> str:
    """Keep only the last <style id="..."> block for given id."""
    pattern = re.compile(
        rf'<style id="{re.escape(style_id)}">[\s\S]*?</style>',
        re.I,
    )
    matches = list(pattern.finditer(html))
    if len(matches) <= 1:
        return html
    keep = matches[-1]
    pieces = []
    last = 0
    for m in matches[:-1]:
        pieces.append(html[last : m.start()])
        last = m.end()
    pieces.append(html[last : keep.start()])
    pieces.append(html[keep.start() : keep.end()])
    pieces.append(html[keep.end() :])
    return "".join(pieces)


def dedupe_injected_vendor_scripts(html: str) -> str:
    """Remove duplicated lucide/tailwind/config snippets before reinjection."""
    html = re.sub(r'\s*<script src="https://unpkg\.com/lucide@latest"></script>\s*', "\n", html)
    html = re.sub(r'\s*<script src="https://cdn\.tailwindcss\.com"></script>\s*', "\n", html)
    html = re.sub(
        r'\s*<script>\s*tailwind\.config\s*=\s*\{\s*corePlugins:\s*\{\s*preflight:\s*false\s*\}\s*\}\s*;\s*</script>\s*',
        "\n",
        html,
        flags=re.I,
    )
    return html


def dedupe_injected_runtime_script(html: str) -> str:
    """Remove previously injected runtime IIFE blocks (keeps one fresh insertion)."""
    out = []
    i = 0
    n = len(html)
    while i < n:
        s = html.find("<script>", i)
        if s < 0:
            out.append(html[i:])
            break
        out.append(html[i:s])
        e = html.find("</script>", s)
        if e < 0:
            out.append(html[s:])
            break
        block = html[s : e + len("</script>")]
        if ("window.switchTab = switchTab;" in block) and ('var ytModal = root.querySelector("#ytModal");' in block):
            i = e + len("</script>")
            continue
        out.append(block)
        i = e + len("</script>")
    return "".join(out)


def strip_template_interference(html: str) -> str:
    """Remove template scripts that frequently alter preview layout/runtime."""
    # 1) Google translate loader script tag and hidden widget container
    html = re.sub(
        r'<script async="" src="\./트리니티여성의원_요실금_files/element\.js\.다운로드"></script>',
        "",
        html,
        flags=re.I,
    )
    html = re.sub(
        r'<div id="google_translate_element"[\s\S]*?</div>\s*</div>',
        "",
        html,
        flags=re.I,
    )

    # 2) Remove problematic inline script blocks by content marker
    out = []
    i = 0
    n = len(html)
    while i < n:
        s = html.find("<script", i)
        if s < 0:
            out.append(html[i:])
            break
        out.append(html[i:s])
        tag_end = html.find(">", s)
        if tag_end < 0:
            out.append(html[s:])
            break
        e = html.find("</script>", tag_end)
        if e < 0:
            out.append(html[s:])
            break
        block = html[s : e + len("</script>")]
        markers = [
            "turl = window.location.href",
            "googleTranslateElementInit",
            "googleTranslateLoaded",
        ]
        if any(m in block for m in markers):
            i = e + len("</script>")
            continue
        out.append(block)
        i = e + len("</script>")
    return "".join(out)


def trim_trinity_inline_style(style_inner: str) -> str:
    """Keep only #menu4-3 section08 rules and @media entries that reference section08."""
    lines = style_inner.splitlines()
    kept = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("@media"):
            header = line
            i += 1
            block = []
            while i < len(lines) and lines[i].strip() != "}":
                if "menu4-3-section08" in lines[i]:
                    block.append(lines[i])
                i += 1
            closer = lines[i] if i < len(lines) else "  }"
            if block:
                kept.append(header)
                kept.extend(block)
                kept.append(closer)
            if i < len(lines):
                i += 1
            continue
        if "menu4-3-section08" in line:
            kept.append(line)
        i += 1
    return "\n".join(kept)


def main():
    idx = INDEX.read_text(encoding="utf-8")
    tr = TRINITY.read_text(encoding="utf-8")

    raw_style = extract_index_style(idx)
    scoped = scope_css_block(raw_style)

    P = "#trinity-preview-content"
    extra = f"""
/* Tailwind preflight 대체 */
{P}, {P} *, {P} *::before, {P} *::after {{
  box-sizing: border-box;
}}
/* 전폭 래퍼: 우측 padding 제거(흰 띠·히어로 단절 방지). 퀵메뉴 여백은 아래 max-w 컬럼에만 */
{P} {{
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  padding-left: 0;
  padding-right: 0;
  font-family: "Paperlogy", system-ui, sans-serif;
  background-color: #ffffff;
  overflow-x: hidden;
  color: #1a1f16;
  border-top: 1px solid rgba(150, 127, 109, 0.18);
}}
/* 템플릿 간섭 레이어보다 항상 위에 오도록 주요 섹션 레이아웃 우선순위 고정 */
@media (min-width: 640px) {{
  {P} #surgical > .max-w-7xl > .grid {{
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
    align-items: start !important;
  }}
  {P} #hero .max-w-2xl, {P} #hero .max-w-3xl {{
    max-width: 72rem !important;
  }}
  {P} #philosophy .max-w-7xl > div {{
    display: flex !important;
    flex-direction: row !important;
    align-items: flex-start !important;
  }}
  {P} #process .max-w-7xl > div {{
    display: flex !important;
    flex-direction: row !important;
    align-items: stretch !important;
  }}
}}
@media (min-width: 1024px) {{
  {P} #hero .max-w-7xl {{
    justify-content: center !important;
    align-items: center !important;
  }}
  {P} #hero .max-w-xl {{
    text-align: center !important;
    margin-left: auto !important;
    margin-right: auto !important;
  }}
}}
"""
    full_scoped = extra + "\n" + scoped

    main_html = extract_main_html(idx)

    # Replace entire #menu4-3 block; keep original section08 markup
    old_start = tr.find('<div id="menu4-3">')
    if old_start < 0:
        raise SystemExit("menu4-3 not found")
    sec08 = tr.find('<section class="menu4-3-section08')
    if sec08 < 0:
        raise SystemExit("section08 not found")
    sec08_end = tr.find("</section>", sec08)
    if sec08_end < 0:
        raise SystemExit("section08 end")
    sec08_end += len("</section>")
    menu_close = tr.find("</div>", sec08_end)
    if menu_close < 0:
        raise SystemExit("menu4-3 closing div not found")
    block_end = menu_close + len("</div>")

    before = tr[:old_start]
    after = tr[block_end:]

    new_block = f'''<div id="menu4-3">
  <div id="trinity-preview-content">
{main_html}
  </div>

{tr[sec08:sec08_end]}
</div>'''

    merged = before + new_block + after

    # Remove previously injected duplicate snippets first
    merged = dedupe_injected_vendor_scripts(merged)
    merged = dedupe_injected_runtime_script(merged)
    merged = strip_template_interference(merged)

    # Inject head: before </head>
    head_inj = """
	<style id="trinity-preview-global-reset">
	html, body { zoom: 1 !important; transform: none !important; }
	.sub-page-container, #menu4-3 { width: 100% !important; max-width: none !important; transform: none !important; zoom: 1 !important; }
	#menu4-3 #trinity-preview-content { width: 100% !important; max-width: 100% !important; margin: 0 auto !important; }
	</style>
	<script src="https://unpkg.com/lucide@latest"></script>
	<script src="https://cdn.tailwindcss.com"></script>
	<script>
	tailwind.config = { corePlugins: { preflight: false } };
	</script>
	<style id="trinity-netlify-scoped">
""" + full_scoped + """
	</style>
"""
    hi = merged.lower().find("</head>")
    if hi < 0:
        raise SystemExit("</head> not found")
    merged = merged[:hi] + head_inj + merged[hi:]

    # Replace inline sub-page-container style
    sub_style_start = merged.find("<style>", merged.find("sub-page-container"))
    sub_style_end = merged.find("</style>", sub_style_start)
    if sub_style_start < 0:
        raise SystemExit("sub-page style not found")
    old_inner = merged[sub_style_start + len("<style>") : sub_style_end]
    new_inner = trim_trinity_inline_style(old_inner)
    merged = (
        merged[: sub_style_start + len("<style>")]
        + "\n"
        + new_inner
        + "\n"
        + merged[sub_style_end:]
    )

    # Append script before Trinity footer or before sub.js - after merged block, inject lucide + interactions
    script_snip = """
<script>
(function () {
  function run() {
    if (window.lucide && lucide.createIcons) lucide.createIcons();
    var root = document.getElementById("trinity-preview-content");
    if (!root) return;

    function switchTab(tabId) {
      root.querySelectorAll(".tab-content").forEach(function (c) { c.classList.remove("active"); });
      root.querySelectorAll(".tab-btn").forEach(function (b) { b.classList.remove("active"); });
      var el = document.getElementById(tabId);
      if (el) el.classList.add("active");
      var btn = document.getElementById("btn-" + tabId);
      if (btn) btn.classList.add("active");
    }
    window.switchTab = switchTab;

    root.querySelectorAll(".tab-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = this.id && this.id.replace(/^btn-/, "");
        if (id) switchTab(id);
      });
    });

    var surgicalSection = root.querySelector("#surgical");
    var surgicalVideoCard = root.querySelector("#surgical-video-card");
    var surgicalTextCol = root.querySelector("#surgical-text-col");
    function updateSurgicalParallax() {
      if (!surgicalVideoCard || !surgicalSection || !surgicalTextCol || window.innerWidth < 768) {
        if (surgicalVideoCard) surgicalVideoCard.style.transform = "";
        return;
      }
      var sectionRect = surgicalSection.getBoundingClientRect();
      var start = window.innerHeight * 0.15;
      var end = Math.max(1, sectionRect.height - window.innerHeight * 0.25);
      var progress = (start - sectionRect.top) / end;
      if (progress < 0) progress = 0;
      if (progress > 1) progress = 1;
      var textTravel = Math.max(0, surgicalTextCol.scrollHeight - surgicalVideoCard.offsetHeight);
      var maxMove = Math.min(textTravel + 40, window.innerHeight * 0.75);
      var y = progress * maxMove;
      surgicalVideoCard.style.transform = "translate3d(0," + y.toFixed(2) + "px,0)";
    }
    window.addEventListener("scroll", updateSurgicalParallax, { passive: true });
    window.addEventListener("resize", updateSurgicalParallax);
    updateSurgicalParallax();

    var ytModal = root.querySelector("#ytModal");
    var ytFrame = root.querySelector("#ytFrame");
    var ytClose = root.querySelector("#ytClose");
    function closeYt() {
      if (!ytModal || !ytFrame) return;
      ytFrame.src = "";
      ytModal.classList.add("hidden");
      ytModal.classList.remove("flex");
    }
    function openYt(embedUrl) {
      if (!ytModal || !ytFrame) return;
      ytFrame.src = embedUrl || "";
      ytModal.classList.remove("hidden");
      ytModal.classList.add("flex");
    }
    root.querySelectorAll("[data-youtube]").forEach(function (el) {
      el.addEventListener("click", function () {
        openYt(el.getAttribute("data-youtube"));
      });
    });
    if (ytClose) ytClose.addEventListener("click", closeYt);
    if (ytModal) {
      ytModal.addEventListener("click", function (e) {
        if (e.target === ytModal) closeYt();
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeYt();
    });
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", run);
  else run();
})();
</script>
"""
    ins = merged.find('<script type="text/javascript" src="./트리니티여성의원_요실금_files/sub.js')
    if ins < 0:
        ins = merged.find("</div>", merged.find("menu4-3-section08"))
    merged = merged[:ins] + script_snip + merged[ins:]

    # Disable hard refresh loop when Google Translate fails
    merged = merged.replace("window.location.reload();", "/* hard reload disabled by merge_preview */")

    merged = dedupe_style_blocks_by_id(merged, "trinity-preview-global-reset")
    merged = dedupe_style_blocks_by_id(merged, "trinity-netlify-scoped")

    OUT.write_text(merged, encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
