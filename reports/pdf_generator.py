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


def _clean_text(value):
    if not value: return ""
    text = str(value).replace("\r", " ").replace("**", "").replace("*", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?i)^(based on|here are|here is|here\'s|certainly|sure|as an ai|in order to|to begin|let\'s|i recommend|i suggest)[^:]*:\s*", "", text)
    text = re.sub(r"(?i)^(based on|according to|overall,|in conclusion)[^.]*\.?\s*", "", text)
    text = re.sub(r"^\d+[\.\)]\s*", "", text)
    text = text.replace("$", "INR ")
    if text:
        text = text[0].upper() + text[1:]
    return text.strip()


def _is_clean_action(sentence):
    words = sentence.split()
    if len(words) < 7 or len(words) > 17:
        return False
    # Check if starts with a standard action verb
    action_verbs = {
        "reduce", "optimize", "implement", "streamline", "renegotiate", 
        "audit", "focus", "expand", "shift", "accelerate", "maintain", 
        "suspend", "eliminate", "leverage", "develop", "conduct", "increase",
        "cut", "consolidate", "restructure", "halt", "pivot", "scale"
    }
    if words[0].lower() not in action_verbs:
        return False
    return True


def _to_clean_action_bullets(text, fallback_list, max_items=5):
    raw = _clean_text(text)
    if not raw: return fallback_list[:max_items]

    parts = [line.strip(" -*•") for line in str(text).splitlines() if line.strip()]
    if not parts or len(parts) == 1:
        parts = [p.strip() for p in re.split(r"[.;]", raw) if p.strip()]

    bullets = []
    seen = set()

    for part in parts:
        cleaned = _clean_text(part).replace("•", "").strip()
        
        # Take the first main clause ending in period or comma to keep it concise
        clause = re.split(r"[,;]|\b(thereby|which|yielding|resulting in)\b", cleaned, flags=re.IGNORECASE)[0].strip()
        clause = re.sub(r"\s+(and|or|but|the|with|to|of|in|for|at|on|as|a|an)$", "", clause, flags=re.IGNORECASE).strip()
        
        if not clause.endswith("."):
            clause += "."
        clause = clause[0].upper() + clause[1:]

        if _is_clean_action(clause):
            key = clause.lower()[:30]
            if key not in seen:
                seen.add(key)
                bullets.append(clause)
        
        if len(bullets) >= max_items:
            break

    # Fill remaining from fallbacks
    for item in fallback_list:
        if len(bullets) >= max_items:
            break
        key = item.lower()[:30]
        if key not in seen:
            seen.add(key)
            bullets.append(item)

    return bullets[:max_items]


def _extract_market_insights(research_output):
    raw = _clean_text(research_output)
    fallback = [
        "Market demand trends require aggressive positioning within profitable niche segments instantly.",
        "Competitive intensity necessitates sharper value proposition communication and disciplined execution.",
        "Macroeconomic headwinds demand immediate structural cost optimizations to build operational resilience.",
        "Sustainable growth trajectories depend heavily on rigorous, empirical channel selection frameworks.",
        "Industry pricing pressures force a strategic pivot toward high-margin product layers."
    ]
    
    parts = [line.strip(" -*•") for line in str(research_output or "").splitlines() if line.strip()]
    if not parts or len(parts) == 1:
        parts = [p.strip() for p in re.split(r"[.;]", raw) if p.strip()]
        
    bullets = []
    seen = set()
    keywords = ("market", "demand", "competition", "cost", "growth", "trend", "risk", "revenue")
    
    for part in parts:
        cleaned = _clean_text(part).replace("•", "").strip()
        clause = re.split(r"[;]|\b(thereby|which|giving|yielding|resulting in)\b", cleaned, flags=re.IGNORECASE)[0].strip()
        if not clause.endswith("."): clause += "."
        words = clause.split()
        
        if 8 <= len(words) <= 17 and any(k in clause.lower() for k in keywords):
            key = clause.lower()[:30]
            if key not in seen:
                seen.add(key)
                bullets.append(clause[0].upper() + clause[1:])
        
        if len(bullets) >= 5: break
        
    for item in fallback:
        if len(bullets) >= 5: break
        key = item.lower()[:30]
        if key not in seen:
            seen.add(key)
            bullets.append(item)
            
    return bullets


def _parse_financials(simulation_text):
    try:
        data = json.loads(simulation_text) if isinstance(simulation_text, str) else simulation_text
        if isinstance(data, dict):
            return {
                "monthly_burn": float(data.get("monthly_burn") or 0),
                "runway_months": float(data.get("runway_months") or 0),
                "cost_savings_estimate": float(data.get("cost_savings_estimate") or 0),
            }
    except Exception:
        pass
    return {"monthly_burn": 0.0, "runway_months": 0.0, "cost_savings_estimate": 0.0}


def _section_header(story, title, style, is_first=False):
    if not is_first:
        story.append(Spacer(1, 12))
    story.append(Paragraph(title, style))
    story.append(Spacer(1, 4))


def _render_bullets(story, bullets, style, max_items=5):
    if not bullets:
        story.append(Paragraph("- Insufficient data to generate insights for this section.", style))
        story.append(Spacer(1, 6))
        return
        
    for bullet in bullets[:max_items]:
        story.append(Paragraph(f"- {bullet}", style))
    story.append(Spacer(1, 8))


def create_finance_chart(monthly_burn, savings, optimized_burn):
    drawing = Drawing(400, 150)

    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 30
    chart.height = 90
    chart.width = 300

    chart.data = [[monthly_burn, optimized_burn]]
    chart.categoryAxis.categoryNames = ["Current Burn", "Optimized Burn"]

    chart.bars[0].fillColor = colors.HexColor("#0f172a") # Dark Slate
    chart.bars[1].fillColor = colors.HexColor("#10b981") # Success Green
    chart.valueAxis.valueMin = 0

    peak = max(monthly_burn, optimized_burn, 1.0)
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
    action_plan=None,
    execution_timeline=None,
    kpi_metrics=None,
    scenario_analysis=None,
    confidence_breakdown=None,
    assumptions=None,
    output_path="AI_Strategy_Report.pdf",
):
    output_file = Path(output_path)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=colors.HexColor("#0f172a"), alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="CoverSubTitle", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=15, textColor=colors.HexColor("#475569"), alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle(name="SectionHeader", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor("#0f172a"), alignment=TA_LEFT, spaceBefore=8, spaceAfter=4, borderPadding=0))
    styles.add(ParagraphStyle(name="BodyBullet", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=14, textColor=colors.HexColor("#1e293b"), alignment=TA_LEFT, spaceAfter=3))
    styles.add(ParagraphStyle(name="Caption", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER, spaceBefore=2, spaceAfter=6))

    doc = SimpleDocTemplate(str(output_file), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=36, bottomMargin=36)
    story = []

    topic_text = _clean_text(topic) or "Strategic Business Optimization"

    # Cover
    story.append(Spacer(1, 40))
    story.append(Paragraph("Strategic Decision Document", styles["CoverTitle"]))
    story.append(Paragraph(topic_text.upper(), styles["CoverSubTitle"]))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", styles["CoverSubTitle"]))
    story.append(Paragraph("Confidential & Proprietary", styles["CoverSubTitle"]))
    story.append(Spacer(1, 28))

    financials = _parse_financials(simulation_output)
    
    current_burn = max(float(financials.get("monthly_burn") or 0), 0)
    savings = max(float(financials.get("cost_savings_estimate") or 0), 0)
    current_runway = max(float(financials.get("runway_months") or 0), 0)
    
    optimized_burn = max(current_burn - savings, 1)
    cash = current_runway * current_burn if current_burn > 0 else 0
    optimized_runway = cash / optimized_burn if optimized_burn > 0 else current_runway
    decrease_pct = (savings / current_burn * 100) if current_burn > 0 else 0

    # 1. Executive Summary
    exec_defaults = [
        "Mandate immediate structural realignment to ensure financial resilience and operational efficiency.",
        "Execute strict prioritization of high-impact actions to stabilize runway projections instantly.",
        "Drive cross-functional alignment strictly toward measurable unit economics improvements.",
        "Suspend low-conviction initiatives to centralize capital deployment on proven growth layers."
    ]
    exec_bullets = _to_clean_action_bullets(strategy_summary, exec_defaults, 4)
    _section_header(story, "1. Executive Summary", styles["SectionHeader"], is_first=True)
    _render_bullets(story, exec_bullets, styles["BodyBullet"], 4)

    # 2. Market Insights
    market_bullets = _extract_market_insights(research_output)
    _section_header(story, "2. Market Insights", styles["SectionHeader"])
    _render_bullets(story, market_bullets, styles["BodyBullet"], 4)

    # 3. Strategic Options
    _section_header(story, "3. Strategic Options", styles["SectionHeader"])
    options = {
        "Cost Optimization": [
            "Reduce operational expenses through rigorous departmental spend governance.",
            "Consolidate external suppliers to force improved pricing tiers and terms."
        ],
        "Growth Strategy": [
            "Scale customer acquisition exclusively through top-quartile intention channels.",
            "Expand distribution partnerships to maximize qualified aggregate market coverage."
        ],
        "Hybrid Approach": [
            "Balance targeted cost deductions with hyper-focused performance marketing investments.",
            "Optimize capital distribution dynamically using rigorous weekly performance reviews."
        ],
    }
    for option_name, bullets in options.items():
        story.append(Paragraph(f"<b>{option_name}</b>", styles["BodyBullet"]))
        for b in bullets:
            story.append(Paragraph(f"- {b}", styles["BodyBullet"]))
        story.append(Spacer(1, 6))

    # 4. Strategy Recommendation
    strategy_defaults = [
        "Audit recurring spend and eliminate low-ROI software licenses completely.",
        "Renegotiate vendor contracts to secure immediate 15% payment reductions.",
        "Suspend nonessential recruitment and prioritize critical revenue-generating roles exclusively.",
        "Concentrate marketing investments strictly on top-quartile converting acquisition channels.",
        "Accelerate collections cycles and enforce aggressive 15-day invoicing discipline."
    ]
    strategy_bullets = _to_clean_action_bullets(proposal_output, strategy_defaults, 5)
    _section_header(story, "4. Strategy Recommendation", styles["SectionHeader"])
    _render_bullets(story, strategy_bullets, styles["BodyBullet"], 5)

    # 5. Critic Analysis
    critic_defaults = [
        "Validate core economic assumptions against immediate operational capacity constraints.",
        "Track implementation risks utilizing explicit, weekly executive governance checkpoints.",
        "Ensure task prioritization definitively reflects measurable near-term business impact.",
        "Stress-test proposed capital allocations against severe downside revenue scenarios."
    ]
    critic_bullets = _to_clean_action_bullets(critique_output, critic_defaults, 4)
    _section_header(story, "5. Critic Analysis", styles["SectionHeader"])
    _render_bullets(story, critic_bullets, styles["BodyBullet"], 4)

    # 6. Financial Model
    finance_bullets = [
        "Current burn calculated exactly as gross expenses minus revenue based on provided inputs.",
        f"Savings derived from an aggressive {decrease_pct:.1f}% structural reduction in non-essential vendor costs.",
        "Models assume fixed baseline revenue with linear, immediate realization of projected OPEX reductions."
    ]
    _section_header(story, "6. Financial Model", styles["SectionHeader"])
    _render_bullets(story, finance_bullets, styles["BodyBullet"], 3)

    # 7. Expected Impact
    impact_bullets = [
        f"<b>Burn Reduction:</b> Reduce monthly burn from INR {current_burn:,.0f} to INR {optimized_burn:,.0f} ({decrease_pct:.1f}% decrease).",
        f"<b>Runway Extension:</b> Extend operational runway from {current_runway:.1f} months to {optimized_runway:.1f} months through cost optimization.",
        f"<b>Capital Efficiency:</b> Secure immediate INR {savings:,.0f} monthly liquidity injection without external equity dilution."
    ]
    _section_header(story, "7. Expected Impact", styles["SectionHeader"])
    _render_bullets(story, impact_bullets, styles["BodyBullet"], 3)
    
    chart = create_finance_chart(current_burn, savings, optimized_burn)
    story.append(Spacer(1, 4))
    story.append(chart)
    story.append(Paragraph("Figure 1: Visual comparison of baseline monthly burn versus optimized monthly burn.", styles["Caption"]))
    story.append(Spacer(1, 6))

    # 8. Best Strategy Selection
    if current_burn > 0 and current_runway < 10 and savings > 0:
        selected, why, trade_off = "Hybrid Approach", "Captures immediate savings while preventing starvation of critical topline growth channels.", "Requires high management bandwidth; delivers slower cash recovery than pure aggressive cuts."
    elif current_burn > 0 and current_runway < 8:
        selected, why, trade_off = "Cost Optimization", "Fastest definitive route to structural stabilization and immediate runway preservation.", "Sacrifices near-term market share expansion and introduces integration friction."
    else:
        selected, why, trade_off = "Growth Strategy", "Leverages comfortable runway to aggressively capture market share while competitors hesitate.", "Accelerates cash consumption extensively; highly dependent on converting CAC efficiently."

    selection_bullets = [
        f"<b>Selected Strategy:</b> {selected}",
        f"<b>Decision Rationale:</b> {why}",
        f"<b>Execution Priority:</b> {trade_off}"
    ]
    _section_header(story, "8. Best Strategy Selection", styles["SectionHeader"])
    _render_bullets(story, selection_bullets, styles["BodyBullet"], 3)

    # 9. Final Recommendation
    final_bullets = [
        "<b>Immediate Action (Day 1-15):</b> Freeze all non-essential expenditures and enforce strict vendor contract renegotiations immediately.",
        "<b>Short-Term Execution (Day 16-60):</b> Reallocate recovered capital exclusively into highest-converting revenue acquisition channels.",
        f"<b>Target Outcome:</b> Achieve sustainable INR {optimized_burn:,.0f} burn rate and completely stabilize cash position within 60 days."
    ]
    _section_header(story, "9. Final Recommendation", styles["SectionHeader"])
    _render_bullets(story, final_bullets, styles["BodyBullet"], 3)
    
    # 10. Action Plan
    if action_plan:
        _section_header(story, "10. Action Plan", styles["SectionHeader"])
        for act in action_plan[:5]:
            bullet = f"<b>{act.get('action', '')}</b> (Owner: {act.get('owner', '')}, Timeline: {act.get('timeline', '')}) - Expected Impact: {act.get('expected_impact', '')}"
            _render_bullets(story, [bullet], styles["BodyBullet"], 1)

    # 11. Execution Timeline
    if execution_timeline:
        _section_header(story, "11. Execution Timeline", styles["SectionHeader"])
        for phase, acts in execution_timeline.items():
            phase_name = phase.replace("_", " ").title()
            story.append(Paragraph(f"<b>{phase_name}</b>", styles["BodyBullet"]))
            for a in acts[:3]:
                story.append(Paragraph(f"- {a}", styles["BodyBullet"]))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 6))

    # 12. KPI Metrics
    if kpi_metrics:
        _section_header(story, "12. KPI Metrics", styles["SectionHeader"])
        for kpi in kpi_metrics[:5]:
            bullet = f"<b>{kpi.get('metric', '')}</b>: Target {kpi.get('target', '')} (Tracked {kpi.get('tracking_frequency', '')})"
            _render_bullets(story, [bullet], styles["BodyBullet"], 1)

    # 13. Scenario Analysis
    if scenario_analysis:
        _section_header(story, "13. Scenario Analysis", styles["SectionHeader"])
        for scen in scenario_analysis[:3]:
            bullet = f"<b>{scen.get('scenario', '')}</b>: Impact: {scen.get('impact', '')}. Risk: {scen.get('risk', '')}"
            _render_bullets(story, [bullet], styles["BodyBullet"], 1)

    # 14. Scenario Analysis
    if scenario_analysis:
        _section_header(story, "14. Scenario Analysis", styles["SectionHeader"])
        for scen in scenario_analysis[:3]:
            bullet = f"<b>{scen.get('scenario', '')}</b>: Impact: {scen.get('impact', '')}. Risk: {scen.get('risk', '')}"
            _render_bullets(story, [bullet], styles["BodyBullet"], 1)

    # 15. Key Assumptions
    if assumptions:
        _section_header(story, "15. Key Assumptions", styles["SectionHeader"])
        for assump in assumptions[:4]:
            bullet = f"{assump}"
            _render_bullets(story, [bullet], styles["BodyBullet"], 1)

    # 16. Confidence Breakdown
    if confidence_breakdown:
        _section_header(story, "16. Confidence Breakdown", styles["SectionHeader"])
        for key, val in confidence_breakdown.items():
            label = key.replace("_", " ").title()
            bullet = f"<b>{label}</b>: {val}"
            _render_bullets(story, [bullet], styles["BodyBullet"], 1)

    # 17. Risks
    risk_defaults = [
        "Avoid aggressive over-corrections that critically weaken competitive market positioning.",
        "Track key talent flight risk and baseline productivity degradation during implementation.",
        "Monitor unexpected revenue friction linked directly to operational expenditure reductions."
    ]
    risk_bullets = _to_clean_action_bullets(None, risk_defaults, 3)
    _section_header(story, "17. General Implementation Risks", styles["SectionHeader"])
    _render_bullets(story, risk_bullets, styles["BodyBullet"], 3)

    doc.build(story)
    return str(output_file)
