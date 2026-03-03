import streamlit as st
import streamlit.components.v1 as components
import anthropic
import json
import plotly.graph_objects as go
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Portfolio Manager",
    page_icon="α",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────
#  SYSTEM PROMPT — Institutional Quality Compounding Protocol
# ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a composite of three elite institutional equity analysts operating under the Institutional Quality Compounding Protocol. You must evaluate the provided stock data and return ONLY valid JSON. No markdown, no explanation outside the JSON.

ANALYST 1 — FUNDAMENTAL ANALYST (Quantitative Framework):
Evaluate: ROIC (TTM & 5Y avg, target >15%), Operating Margin (stability, CV), Gross Profitability (Novy-Marx), FCF Conversion (target >100%), D/E Ratio (target <0.5x), Interest Coverage (target >10x), Beneish M-Score (flag if >-1.78), Altman Z-Score (safe >3.0), Piotroski F-Score (strong 8-9), Cash Conversion Cycle, Revenue Growth (5Y CAGR target >10%), ROIIC vs WACC.
Weight: Capital Efficiency 45%, Operational Health 30%, Cash & Solvency 15%, Growth & Integrity 10%.
Output a score from 0-30 for the Fundamental pillar.

ANALYST 2 — BUSINESS STRATEGY ANALYST (Qualitative Moat Framework):
Evaluate across 100 points: Economic Moats (40pts: Intangible Assets 10, Switching Costs 10, Network Effects 10, Cost/Scale Advantage 10), Management Quality (30pts: Owner-Orientation 10, Capital Allocation 10, Culture & Transparency 10), Industry Structure (15pts: Competitive Intensity 5, Replication Difficulty 5, Resilience/Product Type 5), Stakeholder Satisfaction (15pts: Employee Sentiment 7.5, Customer Loyalty/NPS 7.5).
Normalize the 0-100 qualitative score to a 0-40 scale for the Business Quality pillar.

ANALYST 3 — VALUATION ANALYST (Quality-Centric Valuation Framework):
Evaluate: DCF Margin of Safety (45% weight: Score 100 if P < 0.6*V, Score 50 if P=V, Score 0 if P > 1.5*V), Forward Revenue PEG (35% weight: <1.0 bargain, 1.0-2.0 fair, >2.5 expensive), Forward EV/Sales (10% weight: absolute, industry, 5Y historical), Forward EV/FCF (10% weight: absolute, industry, 5Y historical).
Output a score from 0-30 for the Valuation pillar.

COMPOSITE SCORE = Fundamental (0-30) + Business Quality (0-40) + Valuation (0-30) = 0-100.

RECOMMENDATION LOGIC:
- 85-100: STRONG BUY
- 70-84: BUY
- 45-69: HOLD
- 0-44: SELL

You MUST respond with ONLY this JSON structure:
{
  "ticker": "EXTRACTED_TICKER_OR_UNKNOWN",
  "sector": "GICS Sector",
  "fundamentalScore": <0-30>,
  "businessQualityScore": <0-40>,
  "valuationScore": <0-30>,
  "compositeScore": <0-100>,
  "recommendation": "STRONG BUY|BUY|HOLD|SELL",
  "memo": "A single paragraph investment memo (3-5 sentences) citing specific metrics from the framework. Reference ROIC, moat type, FCF conversion, margin of safety, and any forensic flags. Be precise and data-driven.",
  "keyMetrics": {
    "roicTTM": "<value or N/A>",
    "operatingMargin": "<value or N/A>",
    "fcfConversion": "<value or N/A>",
    "debtToEquity": "<value or N/A>",
    "mScore": "<value or N/A>",
    "zScore": "<value or N/A>",
    "fScore": "<value or N/A>",
    "moatType": "<primary moat type>",
    "pegRatio": "<value or N/A>"
  },
  "analystNotes": {
    "fundamental": "One sentence summary of fundamental findings.",
    "quality": "One sentence summary of business quality findings.",
    "valuation": "One sentence summary of valuation findings."
  }
}"""


# ──────────────────────────────────────────────────────────────
#  CUSTOM CSS
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    .stApp { background-color: #0d1117; }
    header[data-testid="stHeader"] { background-color: #0d1117; }
    .block-container { max-width: 960px; padding-top: 1rem; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    .stTextArea textarea {
        background-color: #0d1117 !important;
        border: 1px solid #2d3748 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        line-height: 1.6 !important;
    }
    .stTextArea textarea:focus {
        border-color: #4fc3f7 !important;
        box-shadow: 0 0 0 2px rgba(79,195,247,0.13) !important;
    }
    .stTextArea label { display: none !important; }
    .stButton > button {
        background: linear-gradient(135deg, #4fc3f7, #00e676) !important;
        color: #0d1117 !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 10px 28px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        letter-spacing: 2px !important;
        text-transform: uppercase !important;
    }
    .stButton > button:hover {
        opacity: 0.9 !important;
        box-shadow: 0 0 20px rgba(79,195,247,0.3) !important;
    }
    .stButton > button:disabled {
        background: #2d3748 !important;
        color: #718096 !important;
    }
    .stSpinner > div { color: #4fc3f7 !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  SESSION STATE
# ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "result" not in st.session_state:
    st.session_state.result = None


# ──────────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────────
def get_rec_color(rec):
    return {"STRONG BUY": "#00e676", "BUY": "#4fc3f7", "HOLD": "#ffd54f", "SELL": "#ff5252"}.get(rec, "#ffd54f")

def get_score_color(score):
    if score >= 85: return "#00e676"
    if score >= 70: return "#4fc3f7"
    if score >= 45: return "#ffd54f"
    return "#ff5252"

def render_html(html_content, height):
    """Render HTML reliably using components.html with full page wrapper."""
    full_html = f"""<!DOCTYPE html>
<html><head>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>body {{ background:transparent; margin:0; padding:0; font-family:'Segoe UI',system-ui,-apple-system,sans-serif; }}</style>
</head><body>{html_content}</body></html>"""
    components.html(full_html, height=height, scrolling=False)


def create_score_dial(score):
    color = get_score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 48, "color": color, "family": "JetBrains Mono"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#4a5568",
                     "tickfont": {"size": 10, "color": "#718096", "family": "JetBrains Mono"}, "dtick": 20},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": "#1a202c",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 44], "color": "rgba(255,82,82,0.08)"},
                {"range": [44, 69], "color": "rgba(255,213,79,0.08)"},
                {"range": [69, 84], "color": "rgba(79,195,247,0.08)"},
                {"range": [84, 100], "color": "rgba(0,230,118,0.08)"},
            ],
            "threshold": {"line": {"color": color, "width": 4}, "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(
        height=220, margin=dict(t=30, b=10, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "JetBrains Mono"},
    )
    fig.add_annotation(text="COMPOSITE", x=0.5, y=0.15, showarrow=False,
                       font=dict(size=10, color="#718096", family="JetBrains Mono"))
    return fig


def run_analysis(input_text):
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Analyze the following stock data and business information. Apply all three analyst frameworks rigorously. Return ONLY valid JSON.\n\n---\n{input_text}\n---"
        }],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    clean = text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


# ──────────────────────────────────────────────────────────────
#  APP HEADER
# ──────────────────────────────────────────────────────────────
today = datetime.now().strftime("%a, %b %d, %Y")

render_html(f"""
<div style="border-bottom:1px solid #1e2a3a;padding:16px 0;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(180deg,#0d1117 0%,#0f1520 100%);">
    <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:32px;height:32px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#4fc3f7,#00e676);font-size:16px;font-weight:800;color:#0d1117;">α</div>
        <div>
            <div style="font-family:'JetBrains Mono',monospace;font-weight:700;font-size:15px;letter-spacing:1px;color:#e2e8f0;">AI PORTFOLIO MANAGER</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:#4a5568;margin-top:1px;">INSTITUTIONAL QUALITY COMPOUNDING PROTOCOL</div>
        </div>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#4a5568;padding:4px 10px;background:#1a202c;border-radius:4px;border:1px solid #2d3748;">{today}</div>
</div>
""", height=70)


# ──────────────────────────────────────────────────────────────
#  DATA INGESTION TERMINAL
# ──────────────────────────────────────────────────────────────
render_html("""
<div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px 10px 0 0;padding:16px 20px 8px;">
    <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:8px;height:8px;border-radius:50%;background:#4fc3f7;display:inline-block;"></span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;text-transform:uppercase;">Data Ingestion Terminal</span>
    </div>
</div>
""", height=52)

input_text = st.text_area(
    "data_input",
    height=180,
    placeholder="Paste raw financial data, earnings transcripts, 10-K excerpts, or business descriptions here.\n\nExample:\nTicker: MSFT\nROIC TTM: 31.2% | 5Y Avg: 28.5%\nOperating Margin: 44.6% | Gross Margin: 69.4%\nFCF/Net Income: 1.12 | D/E: 0.29\nRevenue Growth 5Y CAGR: 14.2%\nForward P/E: 32.1 | Forward Rev Growth: 14.8%\nEV/Sales: 13.2 | EV/FCF: 38.5\nMoat: Network effects (Azure/Office 365 ecosystem), high switching costs\nManagement: Satya Nadella, significant insider ownership...",
)

col_info, col_btn = st.columns([3, 1])
with col_info:
    char_count = len(input_text) if input_text else 0
    msg = f"{char_count} chars" if char_count > 0 else "Awaiting data input"
    st.markdown(f'<span style="font-size:10px;color:#4a5568;font-family:JetBrains Mono,monospace;">{msg}</span>', unsafe_allow_html=True)
with col_btn:
    analyze_clicked = st.button("▶ RUN ANALYSIS", disabled=not input_text or not input_text.strip())


# ──────────────────────────────────────────────────────────────
#  RUN ANALYSIS
# ──────────────────────────────────────────────────────────────
if analyze_clicked and input_text and input_text.strip():
    with st.spinner("Three-analyst committee deliberation in progress..."):
        try:
            result = run_analysis(input_text)
            st.session_state.result = result
            entry = {
                "date": datetime.now().isoformat(),
                "ticker": result.get("ticker", "N/A"),
                "sector": result.get("sector", "N/A"),
                "compositeScore": result.get("compositeScore", 0),
                "recommendation": result.get("recommendation", "HOLD"),
            }
            st.session_state.history.insert(0, entry)
            st.session_state.history = st.session_state.history[:50]
        except Exception as e:
            st.error(f"⚠ Analysis failed. Verify data quality and retry. Error: {str(e)}")


# ──────────────────────────────────────────────────────────────
#  RESULTS DISPLAY
# ──────────────────────────────────────────────────────────────
result = st.session_state.result

if result:
    ticker = result.get("ticker", "N/A")
    sector = result.get("sector", "")
    composite = result.get("compositeScore", 0)
    bq = result.get("businessQualityScore", 0)
    fund = result.get("fundamentalScore", 0)
    valuation = result.get("valuationScore", 0)
    rec = result.get("recommendation", "HOLD")
    rec_color = get_rec_color(rec)

    rec_config = {
        "STRONG BUY": {"bg": "#00e67622", "icon": "▲▲"},
        "BUY": {"bg": "#4fc3f722", "icon": "▲"},
        "HOLD": {"bg": "#ffd54f22", "icon": "◆"},
        "SELL": {"bg": "#ff525222", "icon": "▼"},
    }
    rc = rec_config.get(rec, rec_config["HOLD"])

    # ── Section Header ──
    sector_html = f'<span style="margin-left:auto;font-family:\'JetBrains Mono\',monospace;font-size:9px;padding:3px 8px;background:#1a202c;border-radius:4px;color:#4a5568;border:1px solid #2d3748;letter-spacing:1px;">{sector}</span>' if sector else ""

    render_html(f"""
    <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:16px 20px;">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="width:8px;height:8px;border-radius:50%;background:#00e676;display:inline-block;"></span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">ANALYSIS COMPLETE — {ticker}</span>
            {sector_html}
        </div>
    </div>
    """, height=56)

    # ── Dial + Bars ──
    col_dial, col_bars = st.columns([1, 1.3])

    with col_dial:
        fig = create_score_dial(composite)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_bars:
        bq_pct = (bq / 40) * 100
        fund_pct = (fund / 30) * 100
        val_pct = (valuation / 30) * 100

        render_html(f"""
        <div style="padding-top:10px;">
            <div style="margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;color:#a0aec0;text-transform:uppercase;">Business Quality</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#4fc3f7;">{bq}/40</span>
                </div>
                <div style="background:#1a202c;border-radius:4px;height:8px;overflow:hidden;">
                    <div style="width:{bq_pct}%;height:100%;background:linear-gradient(90deg,#4fc3f788,#4fc3f7);border-radius:4px;box-shadow:0 0 12px #4fc3f744;"></div>
                </div>
            </div>
            <div style="margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;color:#a0aec0;text-transform:uppercase;">Fundamentals</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#00e676;">{fund}/30</span>
                </div>
                <div style="background:#1a202c;border-radius:4px;height:8px;overflow:hidden;">
                    <div style="width:{fund_pct}%;height:100%;background:linear-gradient(90deg,#00e67688,#00e676);border-radius:4px;box-shadow:0 0 12px #00e67644;"></div>
                </div>
            </div>
            <div style="margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;color:#a0aec0;text-transform:uppercase;">Valuation</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#ffd54f;">{valuation}/30</span>
                </div>
                <div style="background:#1a202c;border-radius:4px;height:8px;overflow:hidden;">
                    <div style="width:{val_pct}%;height:100%;background:linear-gradient(90deg,#ffd54f88,#ffd54f);border-radius:4px;box-shadow:0 0 12px #ffd54f44;"></div>
                </div>
            </div>
            <div style="text-align:center;margin-top:18px;">
                <div style="display:inline-flex;align-items:center;gap:10px;border-radius:8px;padding:12px 28px;border:2px solid {rec_color};background:{rc['bg']};">
                    <span style="font-size:18px;">{rc['icon']}</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:800;letter-spacing:3px;color:{rec_color};">{rec}</span>
                </div>
            </div>
        </div>
        """, height=250)

    # ── Key Metrics ──
    km = result.get("keyMetrics", {})
    if km:
        metrics = [
            ("ROIC TTM", km.get("roicTTM", "N/A")),
            ("OP. MARGIN", km.get("operatingMargin", "N/A")),
            ("FCF CONV.", km.get("fcfConversion", "N/A")),
            ("D/E RATIO", km.get("debtToEquity", "N/A")),
            ("M-SCORE", km.get("mScore", "N/A")),
            ("Z-SCORE", km.get("zScore", "N/A")),
            ("F-SCORE", km.get("fScore", "N/A")),
            ("MOAT TYPE", km.get("moatType", "N/A")),
            ("PEG RATIO", km.get("pegRatio", "N/A")),
        ]
        chips = ""
        for label, val_str in metrics:
            chips += f"""
            <div style="background:#1a202c;border:1px solid #2d3748;border-radius:6px;padding:6px 10px;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;color:#718096;text-transform:uppercase;">{label}</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:#e2e8f0;">{val_str}</div>
            </div>"""

        render_html(f"""
        <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:20px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#ffd54f;display:inline-block;"></span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">KEY METRICS</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;">
                {chips}
            </div>
        </div>
        """, height=160)

    # ── Analyst Notes ──
    notes = result.get("analystNotes", {})
    if notes:
        fund_note = notes.get("fundamental", "")
        qual_note = notes.get("quality", "")
        val_note = notes.get("valuation", "")

        render_html(f"""
        <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:20px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#ce93d8;display:inline-block;"></span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">ANALYST COMMITTEE NOTES</span>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;white-space:nowrap;background:#00e67611;color:#00e676;border:1px solid #00e67633;margin-top:1px;">FUNDAMENTAL</span>
                <span style="color:#a0aec0;font-size:12px;line-height:1.5;">{fund_note}</span>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;white-space:nowrap;background:#4fc3f711;color:#4fc3f7;border:1px solid #4fc3f733;margin-top:1px;">QUALITY</span>
                <span style="color:#a0aec0;font-size:12px;line-height:1.5;">{qual_note}</span>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;white-space:nowrap;background:#ffd54f11;color:#ffd54f;border:1px solid #ffd54f33;margin-top:1px;">VALUATION</span>
                <span style="color:#a0aec0;font-size:12px;line-height:1.5;">{val_note}</span>
            </div>
        </div>
        """, height=200)

    # ── Investment Memo ──
    memo = result.get("memo", "")
    if memo:
        render_html(f"""
        <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:20px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#ff8a65;display:inline-block;"></span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">INVESTMENT MEMO</span>
            </div>
            <div style="background:#0d1117;border-radius:8px;padding:16px;border:1px solid #2d3748;border-left:3px solid {rec_color};">
                <p style="color:#cbd5e0;font-size:13px;line-height:1.75;font-family:'Segoe UI',system-ui,sans-serif;margin:0;">{memo}</p>
            </div>
        </div>
        """, height=180)


# ──────────────────────────────────────────────────────────────
#  HISTORICAL LOG
# ──────────────────────────────────────────────────────────────
history = st.session_state.history

if not history:
    render_html("""
    <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:20px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
            <span style="width:8px;height:8px;border-radius:50%;background:#78909c;display:inline-block;"></span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">HISTORICAL LOG</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:9px;padding:2px 6px;background:#1a202c;border-radius:4px;color:#4a5568;border:1px solid #2d3748;">0</span>
        </div>
        <div style="text-align:center;padding:32px;color:#2d3748;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;">
            No analyses recorded. Submit data above to begin.
        </div>
    </div>
    """, height=130)
else:
    rows_html = ""
    for row in history:
        dt = datetime.fromisoformat(row["date"])
        date_str = dt.strftime("%b %d, '%y")
        sc = row["compositeScore"]
        sc_color = get_score_color(sc)
        r = row["recommendation"]
        r_color = get_rec_color(r)
        rows_html += f"""
        <tr>
            <td style="padding:8px 12px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#718096;border-bottom:1px solid #1a202c;">{date_str}</td>
            <td style="padding:8px 12px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#e2e8f0;font-weight:700;border-bottom:1px solid #1a202c;">{row['ticker']}</td>
            <td style="padding:8px 12px;font-family:'JetBrains Mono',monospace;font-size:10px;color:#4a5568;border-bottom:1px solid #1a202c;">{row['sector']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #1a202c;"><span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:{sc_color};">{sc}</span></td>
            <td style="padding:8px 12px;border-bottom:1px solid #1a202c;"><span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;font-weight:700;color:{r_color};background:{r_color}15;border:1px solid {r_color}33;">{r}</span></td>
        </tr>"""

    table_height = 100 + len(history) * 42
    render_html(f"""
    <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:20px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
            <span style="width:8px;height:8px;border-radius:50%;background:#78909c;display:inline-block;"></span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">HISTORICAL LOG</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:9px;padding:2px 6px;background:#1a202c;border-radius:4px;color:#4a5568;border:1px solid #2d3748;">{len(history)}</span>
        </div>
        <table style="width:100%;border-collapse:collapse;">
            <thead><tr>
                <th style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:#4a5568;text-align:left;padding:8px 12px;border-bottom:1px solid #1e2a3a;font-weight:600;">DATE</th>
                <th style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:#4a5568;text-align:left;padding:8px 12px;border-bottom:1px solid #1e2a3a;font-weight:600;">TICKER</th>
                <th style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:#4a5568;text-align:left;padding:8px 12px;border-bottom:1px solid #1e2a3a;font-weight:600;">SECTOR</th>
                <th style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:#4a5568;text-align:left;padding:8px 12px;border-bottom:1px solid #1e2a3a;font-weight:600;">SCORE</th>
                <th style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:#4a5568;text-align:left;padding:8px 12px;border-bottom:1px solid #1e2a3a;font-weight:600;">REC</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """, height=table_height)

    if st.button("🗑 Clear History", key="clear_hist"):
        st.session_state.history = []
        st.session_state.result = None
        st.rerun()


# ──────────────────────────────────────────────────────────────
#  FOOTER
# ──────────────────────────────────────────────────────────────
render_html("""
<div style="text-align:center;padding:20px 0 8px;color:#2d3748;font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;">
    INSTITUTIONAL QUALITY COMPOUNDING PROTOCOL v3.0 — NOT FINANCIAL ADVICE
</div>
""", height=50)
