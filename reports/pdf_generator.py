import json
import re
from datetime import datetime
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _remove_topic(text, topic):
    if not text:
        return ""
    if not topic:
        return text.strip()

    cleaned = str(text)
    topic_text = str(topic).strip()
    if topic_text:
        cleaned = re.sub(re.escape(topic_text), "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _clean_text(value, topic=None):
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("**", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?i)^based on[^.]*\.?\s*", "", text)
    text = re.sub(r"^\d+\.\s*", "", text)
    text = text.replace("$", "INR ")
    text = _remove_topic(text, topic)
    return text


def _to_bullets(text, max_items=5, min_words=5, max_words=15, topic=None):
    raw = _clean_text(text, topic=topic)
    if not raw:
        return []

    parts = [line.strip(" -*•") for line in str(text).splitlines() if line.strip()]
    if not parts:
        parts = [p.strip() for p in re.split(r"[.;]", raw) if p.strip()]

    bullets = []
    seen = set()
    filler_markers = (
        "it is important",
        "this strategy",
        "overall strategy",
        "in conclusion",
        "this approach",
        "given",
    )
    topic_lower = str(topic or "").strip().lower()

    for part in parts:
        cleaned = _clean_text(part, topic=topic).replace("•", "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered.startswith("*"):
            continue
        if re.match(r"^\d+\.", lowered):
            continue
        if any(marker in lowered for marker in filler_markers):
            continue

        words = cleaned.split()
        if len(words) < min_words or len(words) > max_words:
            continue
        if cleaned.endswith(":") or cleaned.endswith(","):
            continue
        if not re.search(r"[A-Za-z]{3,}", cleaned):
            continue
        if topic_lower and (lowered == topic_lower or lowered.startswith(topic_lower)):
            continue

        key = lowered
        if key in seen:
            continue
        seen.add(key)
        bullets.append(cleaned)
        if len(bullets) >= max_items:
            break
    return bullets


def _extract_market_insights(research_output, topic):
    keywords = ("market", "demand", "competition", "cost", "growth")
    lines = [line.strip(" -*•") for line in str(research_output or "").splitlines() if line.strip()]

    filtered = []
    for line in lines:
        lowered = line.lower()
        if any(k in lowered for k in keywords):
            filtered.append(line)

    insights = _to_bullets("\n".join(filtered), max_items=5, min_words=5, max_words=15, topic=topic)
    if insights:
        return insights

    fallback = [
        "Market demand trends indicate clear opportunities for focused positioning",
        "Competitive intensity requires sharper value communication and execution",
        "Cost structure optimization can improve resilience under growth pressure",
        "Sustainable growth depends on disciplined channel and pricing strategy",
    ]
    return fallback


def _strategy_bullets(text):
    candidates = _to_bullets(text, max_items=10, min_words=5, max_words=15)
    action_prefixes = (
        "optimize",
        "reduce",
        "renegotiate",
        "prioritize",
        "improve",
        "shift",
        "implement",
        "track",
        "automate",
        "focus",
        "increase",
        "strengthen",
        "expand",
        "balance",
        "maintain",
    )

    picked = []
    seen = set()
    for item in candidates:
        lowered = item.lower()
        if not lowered.startswith(action_prefixes):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        picked.append(item)
        if len(picked) == 5:
            break

    defaults = [
        "Reduce operational expenses through focused spend governance controls",
        "Improve supplier efficiency with stronger contract discipline",
        "Increase customer acquisition through high-conversion channels only",
        "Optimize ROI by reallocating budget to top-performing initiatives",
        "Maintain sustainable scaling with weekly execution performance reviews",
    ]
    for item in defaults:
        if len(picked) == 5:
            break
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        picked.append(item)

    return picked[:5]


def _parse_financials(simulation_text):
    try:
        data = json.loads(simulation_text) if isinstance(simulation_text, str) else simulation_text
        if isinstance(data, dict):
            return {
                "monthly_burn": float(data.get("monthly_burn", 0)),
                "runway_months": float(data.get("runway_months", 0)),
                "cost_savings_estimate": float(data.get("cost_savings_estimate", 0)),
            }
    except Exception:
        pass
    return {"monthly_burn": 0.0, "runway_months": 0.0, "cost_savings_estimate": 0.0}


def _section_header(story, title, style):
    story.append(Paragraph(title, style))
    story.append(Spacer(1, 4))


def _render_bullets(story, bullets, style, max_items=5):
    for bullet in bullets[:max_items]:
        story.append(Paragraph(f"- {_clean_text(bullet)}", style))
    story.append(Spacer(1, 10))


def _build_strategic_options(financials):
    options = {
        "Option 1: Cost Optimization": [
            "Reduce operational expenses with strict spend governance",
            "Improve supplier efficiency through contract rationalization",
            "Focus decision-making on stronger unit economics outcomes",
        ],
        "Option 2: Growth Strategy": [
            "Increase customer acquisition through targeted high-intent channels",
            "Strengthen branding with differentiated value communication",
            "Expand distribution to improve qualified market coverage",
        ],
        "Option 3: Hybrid Strategy": [
            "Balance cost actions with focused growth investments",
            "Optimize ROI channels using weekly performance reviews",
            "Maintain sustainable scaling through controlled execution pace",
        ],
    }

    burn = float(financials.get("monthly_burn", 0))
    runway = float(financials.get("runway_months", 0))
    savings = float(financials.get("cost_savings_estimate", 0))

    if burn > 0 and runway < 10 and savings > 0:
        selected = "Option 3: Hybrid Strategy"
        reason = "Best balance of burn reduction and growth continuity"
    elif burn > 0 and runway < 8:
        selected = "Option 1: Cost Optimization"
        reason = "Fastest route to immediate runway stabilization"
    else:
        selected = "Option 2: Growth Strategy"
        reason = "Improves topline momentum while keeping cost profile manageable"

    selection_bullets = [
        f"Selected strategy: {selected}",
        f"Selection rationale: {reason}",
        "Decision based on feasibility, impact, and execution resilience",
    ]
    return options, selection_bullets


def create_finance_chart(monthly_burn, savings):
    drawing = Drawing(400, 200)

    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 30
    chart.height = 120
    chart.width = 300

    burn_value = max(0.0, float(monthly_burn or 0))
    savings_value = max(0.0, float(savings or 0))
    chart.data = [[burn_value, savings_value]]
    chart.categoryAxis.categoryNames = ["Burn", "Savings"]

    chart.bars[0].fillColor = colors.HexColor("#0f172a")
    chart.valueAxis.valueMin = 0

    peak = max(burn_value, savings_value, 1.0)
    chart.valueAxis.valueMax = peak * 1.2
    chart.valueAxis.valueStep = max(10000, int(peak / 5))

    chart.categoryAxis.labels.fillColor = colors.HexColor("#334155")
    chart.valueAxis.labels.fillColor = colors.HexColor("#334155")
    chart.strokeColor = colors.HexColor("#94a3b8")

    drawing.add(chart)
    return drawing


def generate_consulting_pdf(
    topic,
    strategy_summary,
    research_output,
    proposal_output,
    critique_output,
    simulation_output,
    decision_output,
    risk_notes=None,
    sources=None,
    output_path="AI_Strategy_Report.pdf",
):
    output_file = Path(output_path)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=31,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_LEFT,
            spaceBefore=7,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyBullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
            alignment=TA_LEFT,
            spaceAfter=2,
        )
    )

    doc = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=36,
        bottomMargin=34,
    )

    story = []
    topic_text = _clean_text(topic) or "Strategic Business Topic"

    story.append(Spacer(1, 70))
    story.append(Paragraph("AI Business Strategy Report", styles["CoverTitle"]))
    story.append(Paragraph(topic_text, styles["CoverSubTitle"]))
    story.append(Paragraph(datetime.now().strftime("%d %b %Y"), styles["CoverSubTitle"]))
    story.append(Paragraph("Generated by: AI System", styles["CoverSubTitle"]))
    story.append(Spacer(1, 28))

    financials = _parse_financials(simulation_output)
    options, selection_bullets = _build_strategic_options(financials)

    exec_bullets = _to_bullets(strategy_summary, max_items=5, min_words=5, max_words=15, topic=topic_text)
    if not exec_bullets:
        exec_bullets = _to_bullets(decision_output, max_items=5, min_words=5, max_words=15, topic=topic_text)
    if not exec_bullets:
        exec_bullets = ["Prioritize high-impact actions with measurable owner accountability"]
    _section_header(story, "Executive Summary", styles["SectionHeader"])
    _render_bullets(story, exec_bullets, styles["BodyBullet"], 5)

    market_bullets = _extract_market_insights(research_output, topic_text)
    _section_header(story, "Market Insights", styles["SectionHeader"])
    _render_bullets(story, market_bullets, styles["BodyBullet"], 5)

    _section_header(story, "Strategic Options", styles["SectionHeader"])
    for option_name, bullets in options.items():
        story.append(Paragraph(f"- {option_name}", styles["BodyBullet"]))
        _render_bullets(story, bullets, styles["BodyBullet"], 3)

    strategy_bullets = _strategy_bullets(proposal_output)
    _section_header(story, "Strategy Recommendation", styles["SectionHeader"])
    _render_bullets(story, strategy_bullets, styles["BodyBullet"], 5)

    critic_bullets = _to_bullets(critique_output, 5, min_words=5, max_words=15, topic=topic_text) or [
        "Validate assumptions against current execution and capacity constraints",
        "Track implementation risks with explicit weekly governance checkpoints",
        "Ensure prioritization reflects measurable business impact and feasibility",
    ]
    _section_header(story, "Critic Analysis", styles["SectionHeader"])
    _render_bullets(story, critic_bullets, styles["BodyBullet"], 5)

    finance_bullets = [
        f"Monthly burn estimated at INR {financials['monthly_burn']:.2f}",
        f"Runway projected at {financials['runway_months']:.2f} months",
        f"Cost savings potential estimated at INR {financials['cost_savings_estimate']:.2f}",
    ]
    _section_header(story, "Financial Model", styles["SectionHeader"])
    _render_bullets(story, finance_bullets, styles["BodyBullet"], 3)
    chart = create_finance_chart(
        financials["monthly_burn"],
        financials["cost_savings_estimate"],
    )
    story.append(Spacer(1, 10))
    story.append(chart)
    story.append(Spacer(1, 20))

    _section_header(story, "Best Strategy Selection", styles["SectionHeader"])
    _render_bullets(story, selection_bullets, styles["BodyBullet"], 3)

    final_bullets = _to_bullets(decision_output, 5, min_words=5, max_words=15, topic=topic_text) or [
        "Execute phased rollout with clear milestones and ownership tracking",
        "Protect core growth levers while improving near-term cash performance",
    ]
    _section_header(story, "Final Recommendation", styles["SectionHeader"])
    _render_bullets(story, final_bullets, styles["BodyBullet"], 5)

    risk_items = risk_notes or [
        "Avoid over-corrections that weaken strategic momentum",
        "Track productivity, quality, and retention during implementation changes",
    ]
    risk_bullets = _to_bullets("\n".join(risk_items), 5, min_words=5, max_words=15) or risk_items[:5]
    _section_header(story, "Risks", styles["SectionHeader"])
    _render_bullets(story, risk_bullets, styles["BodyBullet"], 5)

    if sources:
        appendix_bullets = []
        for src in sources[:5]:
            title = _clean_text(src.get("title", "Untitled Source"), topic=topic_text)
            url = _clean_text(src.get("url", ""))
            if title and url:
                appendix_bullets.append(f"{title} {url}")
            elif title:
                appendix_bullets.append(title)
        if appendix_bullets:
            _section_header(story, "Appendix", styles["SectionHeader"])
            _render_bullets(story, appendix_bullets, styles["BodyBullet"], 5)

    doc.build(story)
    return str(output_file)
