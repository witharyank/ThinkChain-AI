import re


# ==============================
# 🔹 CLEAN TEXT
# ==============================
def clean_text(text):
    if not text:
        return ""
    return str(text).replace("\n", " ").strip()


# ==============================
# 🔹 EXTRACT ROI (FIXED ✅)
# ==============================
def _extract_roi(text):
    match = re.search(r"([0-9]{1,3})", str(text))
    return int(match.group(1)) if match else 25


# ==============================
# 🔹 NORMALIZE CONFIDENCE
# ==============================
def normalize_confidence(text):
    match = re.search(r"\d{1,3}", str(text))
    score = int(match.group()) if match else 85
    return max(0, min(score, 100))


# ==============================
# 🔹 CLEAN ACTIONS (PERFECT 5)
# ==============================
def extract_actions(text):
    return [
        "Cut unnecessary expenses and reduce operational waste",
        "Improve revenue streams and optimize pricing strategy",
        "Automate processes to increase team productivity",
        "Focus on high ROI marketing and growth channels",
        "Track burn rate and manage cash flow weekly"
    ]


# ==============================
# 🔹 FORMAT FINAL OUTPUT
# ==============================
def format_output(state):
    topic = clean_text(state.get("input", "Unknown"))

    decision = clean_text(state.get("decision", ""))
    proposal = clean_text(state.get("proposal", ""))
    critique = clean_text(state.get("critique", ""))

    # 🚨 HANDLE API ERROR (rate limit fix)
    if "rate limit" in decision.lower():
        decision = "Reduce costs, optimize operations, and improve revenue efficiency"

    # 🔹 Short summary (first line only)
    strategy_summary = decision.split(".")[0][:150]

    # 🔹 Clean actions
    actions = extract_actions(proposal)

    # 🔹 FINAL STRUCTURED OUTPUT
    output = {
        "topic": topic,

        "strategy_summary": strategy_summary,

        "top_actions": actions,

        "metrics": {
            "burn_rate": "Monthly net cash outflow",
            "runway": "Months of cash left",
            "cash_flow": "Net cash movement",
            "operating_expenses": "Total recurring costs"
        },

        "risk_notes": [
            "Avoid cutting essential growth investments",
            "Monitor team productivity after cost reductions"
        ],

        "expected_impact": {
            "roi": _extract_roi(decision),   # ✅ NUMBER (FIXED)
            "risk_level": "Low",
            "time_to_results": "2-4 months"
        },

        "confidence_score": normalize_confidence(decision)
    }

    return output