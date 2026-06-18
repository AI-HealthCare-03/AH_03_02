"""건강 리포트 PDF 생성 서비스 (xhtml2pdf 기반).

흐름: ReportResponse → Jinja2 HTML 렌더링 → xhtml2pdf → bytes
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

# multiprocessing.spawn 워커에서 pyvenv.cfg 심볼릭 링크 체인 문제로
# venv site-packages가 sys.path에서 빠질 수 있으므로 명시적으로 추가
_SP = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        ".venv",
        "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
)
if os.path.isdir(_SP) and _SP not in sys.path:
    sys.path.insert(0, _SP)

from jinja2 import Environment, FileSystemLoader  # noqa: E402

from app.dtos.health_check import (  # noqa: E402
    ClinicalItem,
    LifestyleDomainSummary,
    LifestyleItem,
    ReportMeta,
    ReportResponse,
    ShapItem,
)

# ── 상수 ─────────────────────────────────────────────────────────────

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

CATEGORY_ORDER = ["혈압·혈당", "지질", "간·혈액", "신체", "기타"]

_STATUS_BG: dict[str, str] = {
    "good": "#d5f5e3",
    "info": "#d6eaf8",
    "caution": "#fef9e7",
    "warnLight": "#fdebd0",
    "danger": "#fadbd8",
}
_STATUS_TEXT: dict[str, str] = {
    "good": "#1a7a4a",
    "info": "#1a5fa8",
    "caution": "#a07a00",
    "warnLight": "#b84a00",
    "danger": "#b22222",
}

# ── 데이터 클래스 ────────────────────────────────────────────────────


@dataclass
class ShapBar:
    rank: int
    label: str
    value_text: str
    bar_pct: float  # 패널 내 최대값 기준 0~100
    total_pct: str  # 전체 |shap| 대비 %
    color: str  # hex


@dataclass
class ShapPanel:
    title: str
    color: str
    bars: list[ShapBar] = field(default_factory=list)


@dataclass
class PDFContext:
    meta: ReportMeta | None
    model1_raise: ShapPanel
    model1_lower: ShapPanel
    model1_summary: str
    clinical_grouped: list[tuple[str, list[ClinicalItem]]]  # (category, items)
    recommended_tests: list[str]
    lifestyle_score: str | None
    model2_raise: ShapPanel
    model2_lower: ShapPanel
    peer_text: str | None
    domain_summaries: list[LifestyleDomainSummary]
    lifestyle_improve: list[LifestyleItem]
    lifestyle_maintain: list[LifestyleItem]
    ai_guide_html: str
    status_bg: dict[str, str]
    status_text: dict[str, str]


# ── 헬퍼 ─────────────────────────────────────────────────────────────


def _fmt_value(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:.1f}"


def _build_shap_panels(
    items: list[ShapItem],
    raise_title: str,
    lower_title: str,
    raise_color: str = "#c0392b",
    lower_color: str = "#1e8449",
) -> tuple[ShapPanel, ShapPanel]:
    total_abs = sum(abs(it.shap) for it in items) or 1.0

    raise_items = sorted([it for it in items if it.shap > 0], key=lambda x: -abs(x.shap))
    lower_items = sorted([it for it in items if it.shap < 0], key=lambda x: -abs(x.shap))

    raise_max = max((abs(it.shap) for it in raise_items), default=1.0)
    lower_max = max((abs(it.shap) for it in lower_items), default=1.0)

    def _bars(panel_items: list[ShapItem], panel_max: float, color: str) -> list[ShapBar]:
        return [
            ShapBar(
                rank=i + 1,
                label=it.feature,
                value_text=_fmt_value(it.value),
                bar_pct=round((abs(it.shap) / panel_max) * 100, 1),
                total_pct=f"{(abs(it.shap) / total_abs) * 100:.1f}%",
                color=color,
            )
            for i, it in enumerate(panel_items)
        ]

    return (
        ShapPanel(title=raise_title, color=raise_color, bars=_bars(raise_items, raise_max, raise_color)),
        ShapPanel(title=lower_title, color=lower_color, bars=_bars(lower_items, lower_max, lower_color)),
    )


def _markdown_to_html(text: str) -> str:
    """Markdown 일부를 HTML로 변환 (xhtml2pdf용 단순 변환)."""
    # ## 헤딩
    text = re.sub(r"^## (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^### (.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    # 굵게
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 목록 항목
    text = re.sub(r"^[-•] (.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
    # 연속 <li> → <ul> 감싸기
    text = re.sub(
        r"((?:<li>.*?</li>\n?)+)",
        lambda m: "<ul>" + m.group(0) + "</ul>",
        text,
        flags=re.DOTALL,
    )
    # 두 개 이상 빈 줄 → 단락 구분
    text = re.sub(r"\n{2,}", "</p><p>", text)
    text = "<p>" + text + "</p>"
    return text


def _group_clinical(items: list[ClinicalItem]) -> list[tuple[str, list[ClinicalItem]]]:
    grouped: dict[str, list[ClinicalItem]] = {}
    for item in items:
        grouped.setdefault(item.category, []).append(item)
    return [(cat, grouped[cat]) for cat in CATEGORY_ORDER if cat in grouped]


def build_pdf_context(report: ReportResponse) -> PDFContext:
    # ── 모델1 SHAP ──
    m1_raise, m1_lower = _build_shap_panels(
        [
            ShapItem(feature=it.feature, value=it.value, shap=it.shap, note=getattr(it, "note", None))
            for it in report.shap_model1
        ],
        raise_title="위험을 높이는 요인",
        lower_title="위험을 낮추는 요인",
    )

    # ── 모델2 SHAP ──
    m2 = report.shap_model2
    if m2 and m2.items:
        m2_raise, m2_lower = _build_shap_panels(
            m2.items,
            raise_title="개선이 필요한 항목",
            lower_title="잘 관리되고 있는 항목",
        )
        ls_score = f"{m2.lifestyle_score * 100:.0f}" if m2.lifestyle_score is not None else None
        peer_parts: list[str] = []
        if m2.peer_top_pct is not None:
            peer_parts.append(f"상위 {m2.peer_top_pct}%")
        if m2.peer_relative:
            peer_parts.append(m2.peer_relative)
        peer_text = " · ".join(peer_parts) if peer_parts else None
    else:
        m2_raise = ShapPanel(title="개선이 필요한 항목", color="#c0392b")
        m2_lower = ShapPanel(title="잘 관리되고 있는 항목", color="#1e8449")
        ls_score = None
        peer_text = None

    return PDFContext(
        meta=report.report_meta,
        model1_raise=m1_raise,
        model1_lower=m1_lower,
        model1_summary=report.model1_summary,
        clinical_grouped=_group_clinical(report.clinical_items),
        recommended_tests=report.recommended_tests,
        lifestyle_score=ls_score,
        model2_raise=m2_raise,
        model2_lower=m2_lower,
        peer_text=peer_text,
        domain_summaries=report.lifestyle_domain_summary,
        lifestyle_improve=[it for it in report.lifestyle_items if it.group == "improve"],
        lifestyle_maintain=[it for it in report.lifestyle_items if it.group == "maintain"],
        ai_guide_html=_markdown_to_html(report.ai_guide) if report.ai_guide.strip() else "",
        status_bg=_STATUS_BG,
        status_text=_STATUS_TEXT,
    )


# venv Python 경로 — spawn 워커 sys.path 문제를 우회하기 위해 subprocess로 PDF 변환
_HERE = os.path.dirname(os.path.abspath(__file__))
_VENV_PYTHON = os.path.normpath(os.path.join(_HERE, "..", "..", ".venv", "bin", "python3"))
_VENV_SITE_PKG = os.path.normpath(
    os.path.join(
        _HERE,
        "..",
        "..",
        ".venv",
        "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
)
# app/fonts/ 에 번들된 폰트 — bind mount로 Docker 내에서도 동일 경로
_FONT_PATH = os.path.normpath(os.path.join(_HERE, "..", "fonts", "AppleGothic.ttf"))

# subprocess 워커: site-packages·폰트 경로를 포맷으로 주입해 sys.path 문제 우회
# link_callback으로 @font-face URL 해석 — file:// 방식은 xhtml2pdf 0.2.x에서 동작 안 함
_PDF_WORKER_TEMPLATE = """\
import sys, os
sys.path.insert(0, {site_pkg!r})
import io
_font = {font_path!r}
html = sys.stdin.buffer.read().decode('utf-8')
_fdir = os.path.dirname(_font)
_fname = os.path.basename(_font)
if os.path.exists(_font):
    _face = '@font-face {{ font-family: Korean; src: url("' + _fname + '"); }}'
    html = html.replace('<style>', '<style>' + _face, 1)
def _font_cb(uri, rel):
    if uri.endswith('.ttf') or uri.endswith('.otf'):
        p = os.path.join(_fdir, os.path.basename(uri))
        if os.path.exists(p):
            return p
    return uri
from xhtml2pdf import pisa
buf = io.BytesIO()
status = pisa.CreatePDF(html, dest=buf, encoding='utf-8', path=_fdir + '/', link_callback=_font_cb)
if status.err:
    sys.stderr.write('xhtml2pdf error: ' + str(status.err) + '\\n')
    sys.exit(1)
sys.stdout.buffer.write(buf.getvalue())
"""


def render_report_pdf(report: ReportResponse, checked_date: str) -> bytes:
    """ReportResponse → PDF bytes. xhtml2pdf는 spawn-safe subprocess로 실행."""
    import subprocess

    ctx = build_pdf_context(report)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = env.get_template("report_pdf.html")
    html_str = template.render(ctx=ctx, checked_date=checked_date)

    script = _PDF_WORKER_TEMPLATE.format(site_pkg=_VENV_SITE_PKG, font_path=_FONT_PATH)
    result = subprocess.run(
        [_VENV_PYTHON, "-c", script],
        input=html_str.encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"PDF 변환 실패: {err[:300]}")
    return result.stdout
