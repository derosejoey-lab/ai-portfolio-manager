import streamlit as st
import anthropic
import json
import plotly.graph_objects as go
from datetime import datetime
import math

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
#  CUSTOM CSS — Bloomberg-terminal dark theme
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

    /* Main background */
    .stApp { background-color: #0d1117; }
    header[data-testid="stHeader"] { background-color: #0d1117; }
    .block-container { max-width: 960px; padding-top: 1rem; }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Text area styling */
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

    /* Button styling */
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
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        opacity: 0.9 !important;
        box-shadow: 0 0 20px rgba(79,195,247,0.3) !important;
    }
    .stButton > button:disabled {
        background: #2d3748 !important;
        color: #718096 !important;
    }

    /* Card panels */
    .panel {
        background: #161b22;
        border: 1px solid #1e2a3a;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Section headers */
    .section-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 14px;
    }
    .section-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }
    .section-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        letter-spacing: 2px;
        color: #718096;
        text-transform: uppercase;
    }

    /* Metric chips */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
        gap: 8px;
    }
    .metric-chip {
        background: #1a202c;
        border: 1px solid #2d3748;
        border-radius: 6px;
        padding: 6px 10px;
    }
    .metric-chip-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        letter-spacing: 1px;
        color: #718096;
        text-transform: uppercase;
    }
    .metric-chip-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        font-weight: 600;
        color: #e2e8f0;
    }

    /* Recommendation badge */
    .rec-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        border-radius: 8px;
        padding: 12px 28px;
        border-width: 2px;
        border-style: solid;
    }
    .rec-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 22px;
        font-weight: 800;
        letter-spacing: 3px;
    }

    /* Progress bars */
    .pbar-container { margin-bottom: 14px; }
    .pbar-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
    }
    .pbar-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        letter-spacing: 1px;
        color: #a0aec0;
        text-transform: uppercase;
    }
    .pbar-score {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        font-weight: 700;
    }
    .pbar-track {
        background: #1a202c;
        border-radius: 4px;
        height: 8px;
        overflow: hidden;
    }
    .pbar-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 1.2s cubic-bezier(0.22, 1, 0.36, 1);
    }

    /* Analyst notes */
    .analyst-tag {
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        letter-spacing: 1px;
        padding: 3px 8px;
        border-radius: 4px;
        white-space: nowrap;
        display: inline-block;
    }

    /* Memo box */
    .memo-box {
        background: #0d1117;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #2d3748;
        border-left-width: 3px;
    }
    .memo-text {
        color: #cbd5e0;
        font-size: 13px;
        line-height: 1.75;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }

    /* History table */
    .history-table {
        width: 100%;
        border-collapse: collapse;
    }
    .history-table th {
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        letter-spacing: 2px;
        color: #4a5568;
        text-align: left;
        padding: 8px 12px;
        border-bottom: 1px solid #1e2a3a;
        font-weight: 600;
    }
    .history-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #1a202c;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Header */
    .app-header {
        border-bottom: 1px solid #1e2a3a;
        padding: 16px 0px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: linear-gradient(180deg, #0d1117 0%, #0f1520 100%);
        margin-bottom: 24px;
    }
    .app-logo {
        width: 32px; height: 32px; border-radius: 6px;
        display: inline-flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #4fc3f7, #00e676);
        font-size: 16px; font-weight: 800; color: #0d1117;
    }
    .app-title {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700; font-size: 15px;
        letter-spacing: 1px; color: #e2e8f0;
    }
    .app-subtitle {
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px; letter-spacing: 2px;
        color: #4a5568; margin-top: 1px;
    }
    .date-badge {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px; color: #4a5568;
        padding: 4px 10px; background: #1a202c;
        border-radius: 4px; border: 1px solid #2d3748;
    }

    /* Footer */
    .app-footer {
        text-align: center; padding: 20px 0 8px;
        color: #2d3748;
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px; letter-spacing: 1px;
    }

    /* Spinner override */
    .stSpinner > div { color: #4fc3f7 !important; }

    /* Hide expander borders when not needed */
    .streamlit-expanderHeader {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px !important;
        color: #718096 !important;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  SESSION STATE INIT
# ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "result" not in st.session_state:
    st.session_state.result = None


# ──────────────────────────────────────────────────────────────
#  HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────
def get_rec_color(rec):
    colors = {
        "STRONG BUY": "#00e676",
        "BUY": "#4fc3f7",
        "HOLD": "#ffd54f",
        "SELL": "#ff5252",
    }
    return colors.get(rec, "#ffd54f")


def get_score_color(score):
    if score >= 85:
        return "#00e676"
    elif score >= 70:
        return "#4fc3f7"
    elif score >= 45:
        return "#ffd54f"
    return "#ff5252"


def create_score_dial(score):
    """Create the circular gauge dial using Plotly."""
    color = get_score_color(score)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 48, "color": color, "family": "JetBrains Mono"}},
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": "#4a5568",
                "tickfont": {"size": 10, "color": "#718096", "family": "JetBrains Mono"},
                "dtick": 20,
            },
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": "#1a202c",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 44], "color": "rgba(255,82,82,0.08)"},
                {"range": [44, 69], "color": "rgba(255,213,79,0.08)"},
                {"range": [69, 84], "color": "rgba(79,195,247,0.08)"},
                {"range": [84, 100], "color": "rgba(0,230,118,0.08)"},
            ],
            "threshold": {
                "line": {"color": color, "width": 4},
                "thickness": 0.8,
                "value": score,
            },
        },
    ))

    fig.update_layout(
        height=220,
        margin=dict(t=30, b=10, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "JetBrains Mono"},
    )
    fig.add_annotation(
        text="COMPOSITE",
        x=0.5, y=0.15,
        showarrow=False,
        font=dict(size=10, color="#718096", family="JetBrains Mono"),
    )
    return fig


def render_progress_bar(label, score, max_val, color):
    pct = (score / max_val) * 100
    return f"""
    <div class="pbar-container">
        <div class="pbar-header">
            <span class="pbar-label">{label}</span>
            <span class="pbar-score" style="color:{color}">{score}/{max_val}</span>
        </div>
        <div class="pbar-track">
            <div class="pbar-fill" style="width:{pct}%; background:linear-gradient(90deg,{color}88,{color}); box-shadow:0 0 12px {color}44;"></div>
        </div>
    </div>
    """


def render_recommendation_badge(rec):
    config = {
        "STRONG BUY": {"bg": "#00e67622", "border": "#00e676", "color": "#00e676", "icon": "▲▲"},
        "BUY": {"bg": "#4fc3f722", "border": "#4fc3f7", "color": "#4fc3f7", "icon": "▲"},
        "HOLD": {"bg": "#ffd54f22", "border": "#ffd54f", "color": "#ffd54f", "icon": "◆"},
        "SELL": {"bg": "#ff525222", "border": "#ff5252", "color": "#ff5252", "icon": "▼"},
    }
    c = config.get(rec, config["HOLD"])
    return f"""
    <div style="text-align:center; margin-top:18px;">
        <div class="rec-badge" style="background:{c['bg']}; border-color:{c['border']};">
            <span style="font-size:18px">{c['icon']}</span>
            <span class="rec-text" style="color:{c['color']}">{rec}</span>
        </div>
    </div>
    """


def run_analysis(input_text):
    """Call Anthropic API and parse structured JSON response."""
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

st.markdown(f"""
<div class="app-header">
    <div style="display:flex; align-items:center; gap:12px;">
        <div class="app-logo">α</div>
        <div>
            <div class="app-title">AI PORTFOLIO MANAGER</div>
            <div class="app-subtitle">INSTITUTIONAL QUALITY COMPOUNDING PROTOCOL</div>
        </div>
    </div>
    <div class="date-badge">{today}</div>
</div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  DATA INGESTION TERMINAL
# ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="panel" style="padding-bottom:4px;">
    <div class="section-header">
        <span class="section-dot" style="background:#4fc3f7;"></span>
        <span class="section-label">Data Ingestion Terminal</span>
    </div>
</div>
""", unsafe_allow_html=True)

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

            # Save to session history
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
            st.markdown(f"""
            <div class="panel" style="background:#ff525211; border-color:#ff525244;">
                <span style="font-family:'JetBrains Mono',monospace; font-size:12px; color:#ff5252;">
                    ⚠ Analysis failed. Verify data quality and retry. Error: {str(e)}
                </span>
            </div>
            """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  RESULTS DISPLAY
# ──────────────────────────────────────────────────────────────
result = st.session_state.result

if result:
    # ── Score Header Panel ──
    sector_tag = ""
    if result.get("sector"):
        sector_tag = f"""<span style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:9px;
            padding:3px 8px;background:#1a202c;border-radius:4px;color:#4a5568;
            border:1px solid #2d3748;letter-spacing:1px;">{result['sector']}</span>"""

    st.markdown(f"""
    <div class="panel">
        <div class="section-header">
            <span class="section-dot" style="background:#00e676;"></span>
            <span class="section-label">ANALYSIS COMPLETE — {result.get('ticker','N/A')}</span>
            {sector_tag}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_dial, col_bars = st.columns([1, 1.3])

    with col_dial:
        fig = create_score_dial(result.get("compositeScore", 0))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_bars:
        bars_html = ""
        bars_html += render_progress_bar("Business Quality", result.get("businessQualityScore", 0), 40, "#4fc3f7")
        bars_html += render_progress_bar("Fundamentals", result.get("fundamentalScore", 0), 30, "#00e676")
        bars_html += render_progress_bar("Valuation", result.get("valuationScore", 0), 30, "#ffd54f")
        bars_html += render_recommendation_badge(result.get("recommendation", "HOLD"))
        st.markdown(f'<div style="padding-top:10px;">{bars_html}</div>', unsafe_allow_html=True)

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
        chips_html = ""
        for label, val in metrics:
            chips_html += f"""
            <div class="metric-chip">
                <div class="metric-chip-label">{label}</div>
                <div class="metric-chip-value">{val}</div>
            </div>"""

        st.markdown(f"""
        <div class="panel">
            <div class="section-header">
                <span class="section-dot" style="background:#ffd54f;"></span>
                <span class="section-label">KEY METRICS</span>
            </div>
            <div class="metric-grid">{chips_html}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Analyst Notes ──
    notes = result.get("analystNotes", {})
    if notes:
        analysts = [
            ("FUNDAMENTAL", notes.get("fundamental", ""), "#00e676"),
            ("QUALITY", notes.get("quality", ""), "#4fc3f7"),
            ("VALUATION", notes.get("valuation", ""), "#ffd54f"),
        ]
        notes_html = ""
        for label, note, color in analysts:
            notes_html += f"""
            <div style="display:flex; gap:10px; align-items:flex-start; margin-bottom:10px;">
                <span class="analyst-tag" style="background:{color}11; color:{color}; border:1px solid {color}33; margin-top:1px;">{label}</span>
                <span style="color:#a0aec0; font-size:12px; line-height:1.5;">{note}</span>
            </div>"""

        st.markdown(f"""
        <div class="panel">
            <div class="section-header">
                <span class="section-dot" style="background:#ce93d8;"></span>
                <span class="section-label">ANALYST COMMITTEE NOTES</span>
            </div>
            {notes_html}
        </div>
        """, unsafe_allow_html=True)

    # ── Investment Memo ──
    memo = result.get("memo", "")
    rec_color = get_rec_color(result.get("recommendation", "HOLD"))
    if memo:
        st.markdown(f"""
        <div class="panel">
            <div class="section-header">
                <span class="section-dot" style="background:#ff8a65;"></span>
                <span class="section-label">INVESTMENT MEMO</span>
            </div>
            <div class="memo-box" style="border-left-color:{rec_color};">
                <p class="memo-text">{memo}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  HISTORICAL LOG
# ──────────────────────────────────────────────────────────────
history = st.session_state.history

history_header = f"""
<div class="panel" style="margin-bottom:0; padding-bottom:10px;">
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
        <div style="display:flex; align-items:center; gap:8px;">
            <span class="section-dot" style="background:#78909c;"></span>
            <span class="section-label">HISTORICAL LOG</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:9px;padding:2px 6px;
                background:#1a202c;border-radius:4px;color:#4a5568;border:1px solid #2d3748;">
                {len(history)}
            </span>
        </div>
    </div>
"""

if not history:
    history_header += """
    <div style="text-align:center; padding:32px; color:#2d3748;
        font-family:'JetBrains Mono',monospace; font-size:11px; letter-spacing:1px;">
        No analyses recorded. Submit data above to begin.
    </div>
    """
else:
    history_header += """<table class="history-table">
    <thead><tr>
        <th>DATE</th><th>TICKER</th><th>SECTOR</th><th>SCORE</th><th>REC</th>
    </tr></thead><tbody>"""

    for row in history:
        dt = datetime.fromisoformat(row["date"])
        date_str = dt.strftime("%b %d, '%y")
        score = row["compositeScore"]
        score_color = get_score_color(score)
        rec = row["recommendation"]
        rec_color = get_rec_color(rec)

        history_header += f"""
        <tr>
            <td style="color:#718096; font-size:11px;">{date_str}</td>
            <td style="color:#e2e8f0; font-size:12px; font-weight:700;">{row['ticker']}</td>
            <td style="color:#4a5568; font-size:10px;">{row['sector']}</td>
            <td><span style="font-size:13px; font-weight:700; color:{score_color};">{score}</span></td>
            <td><span style="font-size:9px; letter-spacing:1px; padding:3px 8px; border-radius:4px;
                font-weight:700; color:{rec_color}; background:{rec_color}15;
                border:1px solid {rec_color}33;">{rec}</span></td>
        </tr>"""

    history_header += "</tbody></table>"

history_header += "</div>"
st.markdown(history_header, unsafe_allow_html=True)

if history:
    if st.button("🗑 Clear History", key="clear_hist"):
        st.session_state.history = []
        st.rerun()


# ──────────────────────────────────────────────────────────────
#  FOOTER
# ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-footer">
    INSTITUTIONAL QUALITY COMPOUNDING PROTOCOL v3.0 — NOT FINANCIAL ADVICE
</div>
""", unsafe_allow_html=True)
