import streamlit as st
import streamlit.components.v1 as components
import anthropic
import json
import requests
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

ANALYST 3 — VALUATION ANALYST (Quality-Centric Forward Valuation Framework):
CRITICAL: Use FORWARD (consensus analyst estimate) multiples, NOT trailing/TTM. All valuation metrics must be forward-looking.
Evaluate:
- DCF Margin of Safety (45% weight: Score 100 if P < 0.6*V, Score 50 if P=V, Score 0 if P > 1.5*V).
- Forward PEG Ratio (Revenue-based) (20% weight): Forward PE / Forward Revenue Growth Rate. <1.0 bargain, 1.0-2.0 fair, >2.5 expensive.
- Forward P/E Ratio (15% weight): Current Price / Forward EPS estimate. Benchmark against sector median and 5Y historical range.
- Forward EV/Sales (10% weight): Enterprise Value / Forward Revenue estimate. Evaluate absolute level, industry average, and 5Y historical average.
- Forward EV/FCF (10% weight): Enterprise Value / Forward FCF estimate. Evaluate absolute FCF yield vs risk-free rate, industry average, and 5Y historical average.
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
  "memo": "A single paragraph investment memo (3-5 sentences) citing specific metrics from the framework. Reference ROIC, moat type, FCF conversion, margin of safety, forward valuation multiples, and any forensic flags. Be precise and data-driven.",
  "keyMetrics": {
    "roicTTM": "<value or N/A>",
    "operatingMargin": "<value or N/A>",
    "fcfConversion": "<value or N/A>",
    "debtToEquity": "<value or N/A>",
    "mScore": "<value or N/A>",
    "zScore": "<value or N/A>",
    "fScore": "<value or N/A>",
    "moatType": "<primary moat type>",
    "forwardPE": "<value or N/A>",
    "forwardPEG": "<value or N/A>",
    "forwardEVSales": "<value or N/A>",
    "forwardEVFCF": "<value or N/A>",
    "dcfIntrinsicValue": "<value or N/A>",
    "marginOfSafety": "<percentage or N/A>"
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
    header[data-testid="stHeader"] { background-color: #0d1117; visibility: hidden; height: 0px; }
    .block-container { max-width: 960px; padding-top: 2.5rem; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    .stTextArea textarea, .stTextInput input {
        background-color: #0d1117 !important;
        border: 1px solid #2d3748 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #4fc3f7 !important;
        box-shadow: 0 0 0 2px rgba(79,195,247,0.13) !important;
    }
    .stTextArea label, .stTextInput label { display: none !important; }
    div[data-testid="stTabs"] button {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        letter-spacing: 1px !important;
        color: #718096 !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #4fc3f7 !important;
        border-bottom-color: #4fc3f7 !important;
    }
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
if "fmp_data_preview" not in st.session_state:
    st.session_state.fmp_data_preview = None
if "fmp_diagnostics" not in st.session_state:
    st.session_state.fmp_diagnostics = {}


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
    full_html = f"""<!DOCTYPE html>
<html><head>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>body {{ background:transparent; margin:0; padding:0; font-family:'Segoe UI',system-ui,-apple-system,sans-serif; }}</style>
</head><body>{html_content}</body></html>"""
    components.html(full_html, height=height, scrolling=False)

def create_score_dial(score):
    color = get_score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number={"font": {"size": 48, "color": color, "family": "JetBrains Mono"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#4a5568",
                     "tickfont": {"size": 10, "color": "#718096", "family": "JetBrains Mono"}, "dtick": 20},
            "bar": {"color": color, "thickness": 0.3}, "bgcolor": "#1a202c", "borderwidth": 0,
            "steps": [
                {"range": [0, 44], "color": "rgba(255,82,82,0.08)"},
                {"range": [44, 69], "color": "rgba(255,213,79,0.08)"},
                {"range": [69, 84], "color": "rgba(79,195,247,0.08)"},
                {"range": [84, 100], "color": "rgba(0,230,118,0.08)"},
            ],
            "threshold": {"line": {"color": color, "width": 4}, "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(height=220, margin=dict(t=30, b=10, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"family": "JetBrains Mono"})
    fig.add_annotation(text="COMPOSITE", x=0.5, y=0.15, showarrow=False,
                       font=dict(size=10, color="#718096", family="JetBrains Mono"))
    return fig


def safe_get(data, key, default="N/A"):
    """Safely extract a value from dict, return formatted string or default."""
    if not data:
        return default
    val = data.get(key)
    if val is None:
        return default
    if isinstance(val, float):
        return round(val, 4)
    return val


def fmt_pct(val):
    """Format a decimal as percentage string."""
    if val is None or val == "N/A":
        return "N/A"
    try:
        return f"{float(val) * 100:.1f}%"
    except (ValueError, TypeError):
        return str(val)


def fmt_num(val, decimals=2):
    """Format a number with specified decimal places."""
    if val is None or val == "N/A":
        return "N/A"
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)


# ──────────────────────────────────────────────────────────────
#  FMP DATA FETCHER
# ──────────────────────────────────────────────────────────────
def fetch_fmp_data(ticker):
    """Fetch all required financial data from Financial Modeling Prep API.
    Tries the new 'stable' endpoints first, falls back to legacy v3/v4 if needed."""
    api_key = st.secrets["FMP_API_KEY"].strip().strip('"').strip("'")
    ticker = ticker.strip().upper()

    # New stable endpoints (current FMP standard)
    stable = "https://financialmodelingprep.com/stable"
    # Legacy endpoints (for older accounts)
    v3 = "https://financialmodelingprep.com/api/v3"
    v4 = "https://financialmodelingprep.com/api/v4"

    # Try stable format first, fallback to legacy
    endpoint_pairs = {
        "profile": (
            f"{stable}/profile?symbol={ticker}&apikey={api_key}",
            f"{v3}/profile/{ticker}?apikey={api_key}",
        ),
        "ratios_ttm": (
            f"{stable}/ratios-ttm?symbol={ticker}&apikey={api_key}",
            f"{v3}/ratios-ttm/{ticker}?apikey={api_key}",
        ),
        "ratios_annual": (
            f"{stable}/ratios?symbol={ticker}&period=annual&limit=5&apikey={api_key}",
            f"{v3}/ratios/{ticker}?period=annual&limit=5&apikey={api_key}",
        ),
        "income": (
            f"{stable}/income-statement?symbol={ticker}&period=annual&limit=5&apikey={api_key}",
            f"{v3}/income-statement/{ticker}?period=annual&limit=5&apikey={api_key}",
        ),
        "balance": (
            f"{stable}/balance-sheet-statement?symbol={ticker}&period=annual&limit=5&apikey={api_key}",
            f"{v3}/balance-sheet-statement/{ticker}?period=annual&limit=5&apikey={api_key}",
        ),
        "cashflow": (
            f"{stable}/cash-flow-statement?symbol={ticker}&period=annual&limit=5&apikey={api_key}",
            f"{v3}/cash-flow-statement/{ticker}?period=annual&limit=5&apikey={api_key}",
        ),
        "key_metrics_ttm": (
            f"{stable}/key-metrics-ttm?symbol={ticker}&apikey={api_key}",
            f"{v3}/key-metrics-ttm/{ticker}?apikey={api_key}",
        ),
        "key_metrics_annual": (
            f"{stable}/key-metrics?symbol={ticker}&period=annual&limit=5&apikey={api_key}",
            f"{v3}/key-metrics/{ticker}?period=annual&limit=5&apikey={api_key}",
        ),
        "dcf": (
            f"{stable}/discounted-cash-flow?symbol={ticker}&apikey={api_key}",
            f"{v3}/discounted-cash-flow/{ticker}?apikey={api_key}",
        ),
        "ev": (
            f"{stable}/enterprise-values?symbol={ticker}&period=annual&limit=5&apikey={api_key}",
            f"{v3}/enterprise-values/{ticker}?period=annual&limit=5&apikey={api_key}",
        ),
        "growth": (
            f"{stable}/financial-growth?symbol={ticker}&period=annual&limit=5&apikey={api_key}",
            f"{v3}/financial-growth/{ticker}?period=annual&limit=5&apikey={api_key}",
        ),
        "analyst_estimates": (
            f"{stable}/analyst-estimates?symbol={ticker}&period=annual&limit=3&apikey={api_key}",
            f"{v3}/analyst-estimates/{ticker}?period=annual&limit=3&apikey={api_key}",
        ),
        "score": (
            f"{stable}/rating?symbol={ticker}&apikey={api_key}",
            f"{v4}/score?symbol={ticker}&apikey={api_key}",
        ),
        "price_target": (
            f"{stable}/price-target-consensus?symbol={ticker}&apikey={api_key}",
            f"{v4}/price-target-consensus?symbol={ticker}&apikey={api_key}",
        ),
    }

    data = {}
    diagnostics = {"success": [], "failed": [], "errors": []}

    def is_valid_response(result):
        """Check if FMP response contains actual data."""
        if result is None:
            return False
        if isinstance(result, dict):
            if "Error Message" in result or "error" in result:
                return False
            return len(result) > 0
        if isinstance(result, list):
            return len(result) > 0
        return False

    for name, (stable_url, fallback_url) in endpoint_pairs.items():
        fetched = False
        for url in [stable_url, fallback_url]:
            try:
                resp = requests.get(url, timeout=12)
                if resp.status_code == 200:
                    result = resp.json()
                    if is_valid_response(result):
                        data[name] = result if isinstance(result, list) else [result] if isinstance(result, dict) else result
                        diagnostics["success"].append(name)
                        fetched = True
                        break
                    else:
                        # Capture the actual error for diagnostics
                        if isinstance(result, dict) and "Error Message" in result:
                            diagnostics["errors"].append(f"{name}: {result['Error Message'][:80]}")
                elif resp.status_code == 401:
                    diagnostics["errors"].append(f"{name}: 401 Unauthorized")
                elif resp.status_code == 403:
                    diagnostics["errors"].append(f"{name}: 403 Forbidden (plan limit)")
            except requests.exceptions.Timeout:
                diagnostics["errors"].append(f"{name}: timeout")
            except Exception as e:
                diagnostics["errors"].append(f"{name}: {str(e)[:50]}")

        if not fetched:
            data[name] = None
            diagnostics["failed"].append(name)

    data["_diagnostics"] = diagnostics
    return data


def format_fmp_for_analysis(ticker, data):
    """Convert raw FMP data into structured text for Claude analysis."""
    lines = []

    # ── Profile ──
    profile = data.get("profile", [None])[0] if data.get("profile") else None
    if profile:
        lines.append(f"=== COMPANY PROFILE ===")
        lines.append(f"Ticker: {ticker}")
        lines.append(f"Company: {safe_get(profile, 'companyName')}")
        lines.append(f"Sector: {safe_get(profile, 'sector')}")
        lines.append(f"Industry: {safe_get(profile, 'industry')}")
        lines.append(f"Market Cap: ${safe_get(profile, 'mktCap'):,}" if isinstance(safe_get(profile, 'mktCap'), (int,float)) else f"Market Cap: {safe_get(profile, 'mktCap')}")
        lines.append(f"Current Price: ${safe_get(profile, 'price')}")
        lines.append(f"Beta: {safe_get(profile, 'beta')}")
        lines.append(f"Full-Time Employees: {safe_get(profile, 'fullTimeEmployees')}")
        desc = safe_get(profile, 'description', '')
        if desc and desc != 'N/A':
            lines.append(f"Description: {desc[:500]}")
    else:
        lines.append(f"Ticker: {ticker}")

    # ── TTM Ratios (Fundamental Analyst) ──
    ratios_ttm = data.get("ratios_ttm", [None])[0] if data.get("ratios_ttm") else None
    if ratios_ttm:
        lines.append(f"\n=== TTM FINANCIAL RATIOS ===")
        lines.append(f"ROIC TTM: {fmt_pct(safe_get(ratios_ttm, 'returnOnCapitalEmployedTTM'))}")
        lines.append(f"ROE TTM: {fmt_pct(safe_get(ratios_ttm, 'returnOnEquityTTM'))}")
        lines.append(f"ROA TTM: {fmt_pct(safe_get(ratios_ttm, 'returnOnAssetsTTM'))}")
        lines.append(f"Gross Margin TTM: {fmt_pct(safe_get(ratios_ttm, 'grossProfitMarginTTM'))}")
        lines.append(f"Operating Margin TTM: {fmt_pct(safe_get(ratios_ttm, 'operatingProfitMarginTTM'))}")
        lines.append(f"Net Margin TTM: {fmt_pct(safe_get(ratios_ttm, 'netProfitMarginTTM'))}")
        lines.append(f"D/E Ratio: {fmt_num(safe_get(ratios_ttm, 'debtEquityRatioTTM'))}")
        lines.append(f"Interest Coverage: {fmt_num(safe_get(ratios_ttm, 'interestCoverageTTM'))}")
        lines.append(f"Current Ratio: {fmt_num(safe_get(ratios_ttm, 'currentRatioTTM'))}")
        lines.append(f"Quick Ratio: {fmt_num(safe_get(ratios_ttm, 'quickRatioTTM'))}")
        lines.append(f"FCF/Share TTM: {fmt_num(safe_get(ratios_ttm, 'freeCashFlowPerShareTTM'))}")
        lines.append(f"PEG Ratio: {fmt_num(safe_get(ratios_ttm, 'pegRatioTTM'))}")
        lines.append(f"P/E Ratio TTM: {fmt_num(safe_get(ratios_ttm, 'peRatioTTM'))}")
        lines.append(f"Price/Book TTM: {fmt_num(safe_get(ratios_ttm, 'priceToBookRatioTTM'))}")
        lines.append(f"Price/Sales TTM: {fmt_num(safe_get(ratios_ttm, 'priceToSalesRatioTTM'))}")
        lines.append(f"Dividend Yield TTM: {fmt_pct(safe_get(ratios_ttm, 'dividendYieldTTM'))}")
        lines.append(f"Payout Ratio TTM: {fmt_pct(safe_get(ratios_ttm, 'payoutRatioTTM'))}")
        lines.append(f"Days Sales Outstanding: {fmt_num(safe_get(ratios_ttm, 'daysOfSalesOutstandingTTM'), 0)}")
        lines.append(f"Days Inventory Outstanding: {fmt_num(safe_get(ratios_ttm, 'daysOfInventoryOutstandingTTM'), 0)}")
        lines.append(f"Days Payables Outstanding: {fmt_num(safe_get(ratios_ttm, 'daysOfPayablesOutstandingTTM'), 0)}")
        lines.append(f"Cash Conversion Cycle: {fmt_num(safe_get(ratios_ttm, 'cashConversionCycleTTM'), 0)} days")

    # ── 5-Year Historical Ratios (for stability/CV calculation) ──
    ratios_annual = data.get("ratios_annual") or []
    if ratios_annual:
        lines.append(f"\n=== 5-YEAR HISTORICAL RATIOS ===")
        for yr in ratios_annual:
            period = safe_get(yr, 'date', 'N/A')
            lines.append(f"  {period}: ROIC={fmt_pct(safe_get(yr, 'returnOnCapitalEmployed'))} | OpMargin={fmt_pct(safe_get(yr, 'operatingProfitMargin'))} | GrossMargin={fmt_pct(safe_get(yr, 'grossProfitMargin'))} | D/E={fmt_num(safe_get(yr, 'debtEquityRatio'))} | FCF/Share={fmt_num(safe_get(yr, 'freeCashFlowPerShare'))}")

    # ── Income Statement (Revenue Growth, Margins) ──
    income = data.get("income") or []
    if income:
        lines.append(f"\n=== INCOME STATEMENT (5Y) ===")
        for yr in income:
            period = safe_get(yr, 'date', 'N/A')
            rev = safe_get(yr, 'revenue')
            gp = safe_get(yr, 'grossProfit')
            oi = safe_get(yr, 'operatingIncome')
            ni = safe_get(yr, 'netIncome')
            rd = safe_get(yr, 'researchAndDevelopmentExpenses')
            lines.append(f"  {period}: Revenue=${rev:,.0f} | GrossProfit=${gp:,.0f} | OpIncome=${oi:,.0f} | NetIncome=${ni:,.0f} | R&D=${rd:,.0f}" if all(isinstance(x, (int,float)) for x in [rev,gp,oi,ni,rd]) else f"  {period}: Revenue={rev} | GrossProfit={gp} | OpIncome={oi} | NetIncome={ni} | R&D={rd}")

        # Calculate 5Y Revenue CAGR
        if len(income) >= 2:
            try:
                rev_latest = income[0].get('revenue', 0)
                rev_oldest = income[-1].get('revenue', 0)
                years = len(income) - 1
                if rev_oldest and rev_oldest > 0 and rev_latest and rev_latest > 0 and years > 0:
                    cagr = (rev_latest / rev_oldest) ** (1 / years) - 1
                    lines.append(f"  → Revenue {years}Y CAGR: {cagr*100:.1f}%")
            except Exception:
                pass

    # ── Balance Sheet ──
    balance = data.get("balance") or []
    if balance:
        lines.append(f"\n=== BALANCE SHEET (Latest) ===")
        b = balance[0]
        lines.append(f"Total Assets: {safe_get(b, 'totalAssets')}")
        lines.append(f"Total Debt: {safe_get(b, 'totalDebt')}")
        lines.append(f"Total Equity: {safe_get(b, 'totalStockholdersEquity')}")
        lines.append(f"Cash & Equivalents: {safe_get(b, 'cashAndCashEquivalents')}")
        lines.append(f"Goodwill & Intangibles: {safe_get(b, 'goodwillAndIntangibleAssets')}")

    # ── Cash Flow Statement (FCF Conversion) ──
    cashflow = data.get("cashflow") or []
    if cashflow:
        lines.append(f"\n=== CASH FLOW STATEMENT (5Y) ===")
        for yr in cashflow:
            period = safe_get(yr, 'date', 'N/A')
            ocf = safe_get(yr, 'operatingCashFlow')
            capex = safe_get(yr, 'capitalExpenditure')
            fcf = safe_get(yr, 'freeCashFlow')
            div = safe_get(yr, 'dividendsPaid')
            buyback = safe_get(yr, 'commonStockRepurchased')
            lines.append(f"  {period}: OpCF={ocf} | CapEx={capex} | FCF={fcf} | Dividends={div} | Buybacks={buyback}")

        # FCF Conversion ratios
        if income and cashflow and len(income) == len(cashflow):
            lines.append(f"\n  → FCF Conversion (FCF/Net Income):")
            for i in range(min(len(income), len(cashflow))):
                try:
                    ni = income[i].get('netIncome', 0)
                    fcf = cashflow[i].get('freeCashFlow', 0)
                    if ni and ni != 0:
                        ratio = fcf / ni
                        lines.append(f"    {income[i].get('date','')}: {ratio:.2f}x")
                except Exception:
                    pass

    # ── Key Metrics TTM (Valuation Analyst) ──
    km_ttm = data.get("key_metrics_ttm", [None])[0] if data.get("key_metrics_ttm") else None
    if km_ttm:
        lines.append(f"\n=== KEY VALUATION METRICS (TTM) ===")
        lines.append(f"EV/Sales: {fmt_num(safe_get(km_ttm, 'evToSalesTTM'))}")
        lines.append(f"EV/FCF: {fmt_num(safe_get(km_ttm, 'evToFreeCashFlowTTM'))}")
        lines.append(f"EV/Operating CF: {fmt_num(safe_get(km_ttm, 'evToOperatingCashFlowTTM'))}")
        lines.append(f"EV/EBITDA: {fmt_num(safe_get(km_ttm, 'enterpriseValueOverEBITDATTM'))}")
        lines.append(f"FCF Yield: {fmt_pct(safe_get(km_ttm, 'freeCashFlowYieldTTM'))}")
        lines.append(f"Earnings Yield: {fmt_pct(safe_get(km_ttm, 'earningsYieldTTM'))}")
        lines.append(f"Gross Profitability (GP/Assets): {fmt_num(safe_get(km_ttm, 'grahamNumberTTM'))}")
        lines.append(f"Revenue per Share: {fmt_num(safe_get(km_ttm, 'revenuePerShareTTM'))}")
        lines.append(f"Net Income per Share: {fmt_num(safe_get(km_ttm, 'netIncomePerShareTTM'))}")
        lines.append(f"Book Value per Share: {fmt_num(safe_get(km_ttm, 'bookValuePerShareTTM'))}")
        lines.append(f"Tangible Book Value per Share: {fmt_num(safe_get(km_ttm, 'tangibleBookValuePerShareTTM'))}")

    # ── Historical Key Metrics (5Y EV/Sales, EV/FCF trends) ──
    km_annual = data.get("key_metrics_annual") or []
    if km_annual:
        lines.append(f"\n=== HISTORICAL VALUATION METRICS (5Y) ===")
        for yr in km_annual:
            period = safe_get(yr, 'date', 'N/A')
            lines.append(f"  {period}: EV/Sales={fmt_num(safe_get(yr, 'evToSales'))} | EV/FCF={fmt_num(safe_get(yr, 'evToFreeCashFlow'))} | EV/EBITDA={fmt_num(safe_get(yr, 'enterpriseValueOverEBITDA'))} | FCF_Yield={fmt_pct(safe_get(yr, 'freeCashFlowYield'))}")

    # ── DCF Intrinsic Value ──
    dcf = data.get("dcf", [None])[0] if data.get("dcf") else None
    if dcf:
        lines.append(f"\n=== DCF VALUATION ===")
        lines.append(f"DCF Intrinsic Value: ${safe_get(dcf, 'dcf')}")
        lines.append(f"Current Price: ${safe_get(dcf, 'Stock Price')}")
        try:
            dcf_val = dcf.get('dcf', 0)
            price = dcf.get('Stock Price', 0)
            if dcf_val and price and dcf_val > 0:
                mos = (dcf_val - price) / dcf_val
                lines.append(f"Margin of Safety: {mos*100:.1f}%")
        except Exception:
            pass

    # ── Analyst Forward Estimates (Forward PE, Forward PEG, Forward EV/S, Forward EV/FCF) ──
    estimates = data.get("analyst_estimates") or []
    profile_data = data.get("profile", [None])[0] if data.get("profile") else None
    ev_data = data.get("ev") or []
    current_price = profile_data.get("price") if profile_data else None
    current_ev = ev_data[0].get("enterpriseValue") if ev_data else None

    if estimates:
        # Use the nearest forward year (first entry is typically next fiscal year)
        fwd = estimates[0]
        lines.append(f"\n=== FORWARD ANALYST CONSENSUS ESTIMATES ===")
        lines.append(f"Estimate Period: {safe_get(fwd, 'date', 'Next FY')}")
        fwd_eps = safe_get(fwd, 'estimatedEpsAvg')
        fwd_rev = safe_get(fwd, 'estimatedRevenueAvg')
        fwd_ebitda = safe_get(fwd, 'estimatedEbitdaAvg')
        fwd_ni = safe_get(fwd, 'estimatedNetIncomeAvg')
        lines.append(f"Forward EPS (Consensus Avg): {fwd_eps}")
        lines.append(f"Forward Revenue (Consensus Avg): {fwd_rev}")
        lines.append(f"Forward EBITDA (Consensus Avg): {fwd_ebitda}")
        lines.append(f"Forward Net Income (Consensus Avg): {fwd_ni}")
        lines.append(f"EPS Range: Low={safe_get(fwd, 'estimatedEpsLow')} | High={safe_get(fwd, 'estimatedEpsHigh')}")
        lines.append(f"Revenue Range: Low={safe_get(fwd, 'estimatedRevenueLow')} | High={safe_get(fwd, 'estimatedRevenueHigh')}")
        lines.append(f"Number of Analysts: {safe_get(fwd, 'numberAnalystEstimatedRevenue')}")

        # ── Compute Forward Valuation Multiples ──
        lines.append(f"\n=== COMPUTED FORWARD VALUATION MULTIPLES ===")

        # Forward P/E
        try:
            if current_price and fwd_eps and isinstance(fwd_eps, (int, float)) and fwd_eps > 0:
                forward_pe = float(current_price) / float(fwd_eps)
                lines.append(f"Forward P/E: {forward_pe:.2f}x  (Price={current_price} / Fwd_EPS={fwd_eps})")
            else:
                lines.append(f"Forward P/E: N/A (insufficient data)")
        except Exception:
            lines.append(f"Forward P/E: N/A")

        # Forward Revenue Growth (for PEG calculation)
        try:
            if income and len(income) >= 1 and fwd_rev and isinstance(fwd_rev, (int, float)):
                last_rev = income[0].get('revenue', 0)
                if last_rev and last_rev > 0:
                    fwd_rev_growth = (float(fwd_rev) - float(last_rev)) / float(last_rev)
                    lines.append(f"Forward Revenue Growth Rate: {fwd_rev_growth*100:.1f}%")

                    # Forward PEG (Revenue-based) = Forward PE / Forward Revenue Growth %
                    if current_price and fwd_eps and isinstance(fwd_eps, (int, float)) and fwd_eps > 0 and fwd_rev_growth > 0:
                        forward_pe_val = float(current_price) / float(fwd_eps)
                        forward_peg = forward_pe_val / (fwd_rev_growth * 100)
                        lines.append(f"Forward PEG (Revenue-based): {forward_peg:.2f}x  (Fwd_PE={forward_pe_val:.1f} / Fwd_RevGrowth={fwd_rev_growth*100:.1f}%)")
                    else:
                        lines.append(f"Forward PEG (Revenue-based): N/A")
                else:
                    lines.append(f"Forward Revenue Growth Rate: N/A")
                    lines.append(f"Forward PEG (Revenue-based): N/A")
        except Exception:
            lines.append(f"Forward PEG (Revenue-based): N/A")

        # Forward EV/Sales
        try:
            if current_ev and fwd_rev and isinstance(fwd_rev, (int, float)) and fwd_rev > 0:
                fwd_ev_sales = float(current_ev) / float(fwd_rev)
                lines.append(f"Forward EV/Sales: {fwd_ev_sales:.2f}x  (EV={current_ev:,.0f} / Fwd_Rev={fwd_rev:,.0f})")
            else:
                lines.append(f"Forward EV/Sales: N/A")
        except Exception:
            lines.append(f"Forward EV/Sales: N/A")

        # Forward EV/FCF (estimate FCF as EBITDA - estimated CapEx, or use Net Income * historical FCF conversion)
        try:
            # Approach: use Forward EBITDA minus historical CapEx ratio as FCF proxy
            if current_ev and fwd_ebitda and isinstance(fwd_ebitda, (int, float)) and fwd_ebitda > 0:
                # Estimate FCF from EBITDA using historical FCF/EBITDA ratio
                cashflow_data = data.get("cashflow") or []
                if cashflow_data:
                    hist_fcf = cashflow_data[0].get('freeCashFlow', 0)
                    hist_ocf = cashflow_data[0].get('operatingCashFlow', 0)
                    hist_capex = abs(cashflow_data[0].get('capitalExpenditure', 0))
                    if income:
                        hist_ebitda_calc = income[0].get('ebitda', 0) or income[0].get('operatingIncome', 0)
                        if hist_ebitda_calc and hist_ebitda_calc > 0 and hist_fcf:
                            fcf_ebitda_ratio = float(hist_fcf) / float(hist_ebitda_calc)
                            fwd_fcf_est = float(fwd_ebitda) * fcf_ebitda_ratio
                            if fwd_fcf_est > 0:
                                fwd_ev_fcf = float(current_ev) / fwd_fcf_est
                                lines.append(f"Forward EV/FCF: {fwd_ev_fcf:.2f}x  (EV={current_ev:,.0f} / Est_FCF={fwd_fcf_est:,.0f})")
                                lines.append(f"  → FCF estimated using historical FCF/EBITDA conversion ratio of {fcf_ebitda_ratio:.2f}")
                            else:
                                lines.append(f"Forward EV/FCF: N/A (negative estimated FCF)")
                        else:
                            lines.append(f"Forward EV/FCF: N/A (insufficient historical data for FCF estimation)")
                    else:
                        lines.append(f"Forward EV/FCF: N/A")
                else:
                    lines.append(f"Forward EV/FCF: N/A (no cash flow history)")
            else:
                lines.append(f"Forward EV/FCF: N/A")
        except Exception:
            lines.append(f"Forward EV/FCF: N/A")

    # ── Price Target Consensus ──
    pt = None
    raw_pt = data.get("price_target")
    if raw_pt:
        if isinstance(raw_pt, list) and len(raw_pt) > 0:
            pt = raw_pt[0]
        elif isinstance(raw_pt, dict) and "Error Message" not in raw_pt:
            pt = raw_pt
    if pt:
        lines.append(f"\n=== ANALYST PRICE TARGET CONSENSUS ===")
        lines.append(f"Target High: ${safe_get(pt, 'targetHigh')}")
        lines.append(f"Target Low: ${safe_get(pt, 'targetLow')}")
        lines.append(f"Target Consensus: ${safe_get(pt, 'targetConsensus')}")
        lines.append(f"Target Median: ${safe_get(pt, 'targetMedian')}")

    # ── Altman Z-Score & Piotroski F-Score ──
    score_data = None
    raw_score = data.get("score")
    if raw_score:
        if isinstance(raw_score, list) and len(raw_score) > 0:
            score_data = raw_score[0]
        elif isinstance(raw_score, dict):
            score_data = raw_score
    if score_data:
        lines.append(f"\n=== FORENSIC / QUALITY SCORES ===")
        lines.append(f"Altman Z-Score: {safe_get(score_data, 'altmanZScore')}")
        lines.append(f"Piotroski F-Score: {safe_get(score_data, 'piotroskiScore')}")

    # ── Growth Metrics ──
    growth = data.get("growth") or []
    if growth:
        lines.append(f"\n=== GROWTH METRICS (5Y) ===")
        for yr in growth:
            period = safe_get(yr, 'date', 'N/A')
            lines.append(f"  {period}: RevGrowth={fmt_pct(safe_get(yr, 'revenueGrowth'))} | EPS_Growth={fmt_pct(safe_get(yr, 'epsgrowth'))} | FCF_Growth={fmt_pct(safe_get(yr, 'freeCashFlowGrowth'))} | OpIncome_Growth={fmt_pct(safe_get(yr, 'operatingIncomeGrowth'))}")

    # ── Enterprise Values (for EV trend) ──
    ev = data.get("ev") or []
    if ev:
        lines.append(f"\n=== ENTERPRISE VALUE HISTORY ===")
        for yr in ev:
            period = safe_get(yr, 'date', 'N/A')
            lines.append(f"  {period}: EV={safe_get(yr, 'enterpriseValue')} | Shares={safe_get(yr, 'numberOfShares')}")

    # ── Calculate Novy-Marx Gross Profitability ──
    if income and balance:
        try:
            gp = income[0].get('grossProfit', 0)
            ta = balance[0].get('totalAssets', 0)
            if gp and ta and ta > 0:
                novy_marx = gp / ta
                lines.append(f"\n=== COMPUTED METRICS ===")
                lines.append(f"Novy-Marx Gross Profitability (GP/TA): {novy_marx:.4f} ({novy_marx*100:.1f}%)")
        except Exception:
            pass

    return "\n".join(lines)


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
#  DATA INGESTION — TABS: Ticker Lookup vs Manual Paste
# ──────────────────────────────────────────────────────────────
render_html("""
<div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px 10px 0 0;padding:16px 20px 8px;">
    <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:8px;height:8px;border-radius:50%;background:#4fc3f7;display:inline-block;"></span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;text-transform:uppercase;">Data Ingestion Terminal</span>
    </div>
</div>
""", height=52)

tab_ticker, tab_manual = st.tabs(["⚡ TICKER LOOKUP", "📋 MANUAL PASTE"])

analysis_text = None

with tab_ticker:
    st.markdown('<span style="font-size:11px;color:#718096;font-family:JetBrains Mono,monospace;">Enter a stock ticker to auto-fetch financial data from FMP</span>', unsafe_allow_html=True)

    col_tick, col_fetch = st.columns([3, 1])
    with col_tick:
        ticker_input = st.text_input("ticker_input", placeholder="e.g. AAPL, MSFT, NVDA, COST")
    with col_fetch:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_clicked = st.button("⚡ FETCH DATA", key="fetch_btn", disabled=not ticker_input)

    # Debug: API connection test
    with st.expander("🔧 Test FMP API Connection", expanded=False):
        if st.button("Run Connection Test", key="test_api"):
            try:
                api_key = st.secrets["FMP_API_KEY"].strip().strip('"').strip("'")
                masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
                st.code(f"Key (masked): {masked}\nKey length: {len(api_key)} chars")

                # Test stable endpoint
                url1 = f"https://financialmodelingprep.com/stable/profile?symbol=AAPL&apikey={api_key}"
                r1 = requests.get(url1, timeout=10)
                st.code(f"Stable endpoint: HTTP {r1.status_code}\nResponse: {r1.text[:300]}")

                # Test v3 endpoint
                url2 = f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={api_key}"
                r2 = requests.get(url2, timeout=10)
                st.code(f"Legacy v3 endpoint: HTTP {r2.status_code}\nResponse: {r2.text[:300]}")
            except Exception as e:
                st.error(f"Test failed: {str(e)}")

    if fetch_clicked and ticker_input:
        with st.spinner(f"Fetching data for {ticker_input.upper()} from FMP..."):
            try:
                fmp_raw = fetch_fmp_data(ticker_input)
                diag = fmp_raw.pop("_diagnostics", {"success": [], "failed": [], "errors": []})
                formatted = format_fmp_for_analysis(ticker_input.upper(), fmp_raw)
                st.session_state.fmp_data_preview = formatted
                st.session_state.fmp_diagnostics = diag
                st.rerun()
            except Exception as e:
                st.error(f"FMP fetch failed: {str(e)}")

    if st.session_state.fmp_data_preview:
        # Show diagnostics
        diag = st.session_state.get("fmp_diagnostics", {})
        success_count = len(diag.get("success", []))
        failed_list = diag.get("failed", [])
        error_list = diag.get("errors", [])

        if success_count == 0:
            st.error("⚠ No data returned from FMP.")
            if error_list:
                st.warning("**FMP API errors:**\n" + "\n".join([f"- `{e}`" for e in error_list[:5]]))
            else:
                st.warning("No specific error messages captured. Please verify:\n"
                           "1. Your `FMP_API_KEY` in Streamlit secrets has no extra quotes or spaces\n"
                           "2. Your FMP plan is active (check dashboard at site.financialmodelingprep.com)\n"
                           "3. You haven't exceeded daily request limits (free plan = 250/day)")
        elif failed_list:
            st.markdown(f'<span style="font-size:10px;color:#ffd54f;font-family:JetBrains Mono,monospace;">⚠ {len(failed_list)} endpoint(s) unavailable: {", ".join(failed_list)}</span>', unsafe_allow_html=True)

        with st.expander(f"📊 Fetched Data Preview — {success_count} endpoints loaded (click to expand)", expanded=False):
            st.code(st.session_state.fmp_data_preview, language="text")

        col_info2, col_run = st.columns([3, 1])
        with col_info2:
            line_count = len([l for l in st.session_state.fmp_data_preview.split('\n') if l.strip() and not l.startswith('===')])
            st.markdown(f'<span style="font-size:10px;color:#00e676;font-family:JetBrains Mono,monospace;">✓ {line_count} data points loaded from {success_count} endpoints</span>', unsafe_allow_html=True)
        with col_run:
            if st.button("▶ RUN ANALYSIS", key="run_ticker"):
                analysis_text = st.session_state.fmp_data_preview

with tab_manual:
    manual_input = st.text_area(
        "manual_data_input",
        height=180,
        placeholder="Paste raw financial data, earnings transcripts, 10-K excerpts, or business descriptions here.\n\nExample:\nTicker: MSFT\nROIC TTM: 31.2% | 5Y Avg: 28.5%\nOperating Margin: 44.6% | Gross Margin: 69.4%\nFCF/Net Income: 1.12 | D/E: 0.29\n...",
    )
    col_info3, col_run2 = st.columns([3, 1])
    with col_info3:
        mc = len(manual_input) if manual_input else 0
        mmsg = f"{mc} chars" if mc > 0 else "Awaiting data input"
        st.markdown(f'<span style="font-size:10px;color:#4a5568;font-family:JetBrains Mono,monospace;">{mmsg}</span>', unsafe_allow_html=True)
    with col_run2:
        if st.button("▶ RUN ANALYSIS", key="run_manual", disabled=not manual_input or not manual_input.strip()):
            analysis_text = manual_input


# ──────────────────────────────────────────────────────────────
#  RUN ANALYSIS
# ──────────────────────────────────────────────────────────────
if analysis_text:
    with st.spinner("Three-analyst committee deliberation in progress..."):
        try:
            result = run_analysis(analysis_text)
            st.session_state.result = result
            st.session_state.fmp_data_preview = None  # Clear preview after analysis
            entry = {
                "date": datetime.now().isoformat(),
                "ticker": result.get("ticker", "N/A"),
                "sector": result.get("sector", "N/A"),
                "compositeScore": result.get("compositeScore", 0),
                "recommendation": result.get("recommendation", "HOLD"),
            }
            st.session_state.history.insert(0, entry)
            st.session_state.history = st.session_state.history[:50]
            st.rerun()
        except Exception as e:
            st.error(f"⚠ Analysis failed. Verify data quality and retry. Error: {str(e)}")


# ──────────────────────────────────────────────────────────────
#  RESULTS DISPLAY
# ──────────────────────────────────────────────────────────────
result = st.session_state.result

if result:
    ticker_display = result.get("ticker", "N/A")
    sector = result.get("sector", "")
    composite = result.get("compositeScore", 0)
    bq = result.get("businessQualityScore", 0)
    fund = result.get("fundamentalScore", 0)
    valuation = result.get("valuationScore", 0)
    rec = result.get("recommendation", "HOLD")
    rec_color = get_rec_color(rec)

    rc = {"STRONG BUY": {"bg": "#00e67622", "icon": "▲▲"}, "BUY": {"bg": "#4fc3f722", "icon": "▲"},
          "HOLD": {"bg": "#ffd54f22", "icon": "◆"}, "SELL": {"bg": "#ff525222", "icon": "▼"}}.get(rec, {"bg": "#ffd54f22", "icon": "◆"})

    sector_html = f'<span style="margin-left:auto;font-family:\'JetBrains Mono\',monospace;font-size:9px;padding:3px 8px;background:#1a202c;border-radius:4px;color:#4a5568;border:1px solid #2d3748;letter-spacing:1px;">{sector}</span>' if sector else ""

    render_html(f"""
    <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:16px 20px;">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="width:8px;height:8px;border-radius:50%;background:#00e676;display:inline-block;"></span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">ANALYSIS COMPLETE — {ticker_display}</span>
            {sector_html}
        </div>
    </div>
    """, height=56)

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
        metrics = [("ROIC TTM", km.get("roicTTM","N/A")), ("OP. MARGIN", km.get("operatingMargin","N/A")),
            ("FCF CONV.", km.get("fcfConversion","N/A")), ("D/E RATIO", km.get("debtToEquity","N/A")),
            ("M-SCORE", km.get("mScore","N/A")), ("Z-SCORE", km.get("zScore","N/A")),
            ("F-SCORE", km.get("fScore","N/A")), ("MOAT TYPE", km.get("moatType","N/A")),
            ("FWD P/E", km.get("forwardPE","N/A")), ("FWD PEG", km.get("forwardPEG","N/A")),
            ("FWD EV/S", km.get("forwardEVSales","N/A")), ("FWD EV/FCF", km.get("forwardEVFCF","N/A")),
            ("DCF VALUE", km.get("dcfIntrinsicValue","N/A")), ("MARGIN/SAFETY", km.get("marginOfSafety","N/A"))]
        chips = "".join([f'<div style="background:#1a202c;border:1px solid #2d3748;border-radius:6px;padding:6px 10px;"><div style="font-family:\'JetBrains Mono\',monospace;font-size:9px;letter-spacing:1px;color:#718096;text-transform:uppercase;">{l}</div><div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;font-weight:600;color:#e2e8f0;">{v}</div></div>' for l,v in metrics])
        render_html(f"""
        <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:20px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#ffd54f;display:inline-block;"></span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">KEY METRICS</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;">{chips}</div>
        </div>""", height=320)

    # ── Analyst Notes ──
    notes = result.get("analystNotes", {})
    if notes:
        fn = notes.get("fundamental",""); qn = notes.get("quality",""); vn = notes.get("valuation","")
        render_html(f"""
        <div style="background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:20px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#ce93d8;display:inline-block;"></span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#718096;">ANALYST COMMITTEE NOTES</span>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;white-space:nowrap;background:#00e67611;color:#00e676;border:1px solid #00e67633;">FUNDAMENTAL</span>
                <span style="color:#a0aec0;font-size:12px;line-height:1.5;">{fn}</span>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;white-space:nowrap;background:#4fc3f711;color:#4fc3f7;border:1px solid #4fc3f733;">QUALITY</span>
                <span style="color:#a0aec0;font-size:12px;line-height:1.5;">{qn}</span>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;white-space:nowrap;background:#ffd54f11;color:#ffd54f;border:1px solid #ffd54f33;">VALUATION</span>
                <span style="color:#a0aec0;font-size:12px;line-height:1.5;">{vn}</span>
            </div>
        </div>""", height=260)

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
        </div>""", height=300)


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
    </div>""", height=130)
else:
    rows_html = ""
    for row in history:
        dt = datetime.fromisoformat(row["date"])
        date_str = dt.strftime("%b %d, '%y")
        sc = row["compositeScore"]; sc_color = get_score_color(sc)
        r = row["recommendation"]; r_color = get_rec_color(r)
        rows_html += f'<tr><td style="padding:8px 12px;font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#718096;border-bottom:1px solid #1a202c;">{date_str}</td><td style="padding:8px 12px;font-family:\'JetBrains Mono\',monospace;font-size:12px;color:#e2e8f0;font-weight:700;border-bottom:1px solid #1a202c;">{row["ticker"]}</td><td style="padding:8px 12px;font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#4a5568;border-bottom:1px solid #1a202c;">{row["sector"]}</td><td style="padding:8px 12px;border-bottom:1px solid #1a202c;"><span style="font-family:\'JetBrains Mono\',monospace;font-size:13px;font-weight:700;color:{sc_color};">{sc}</span></td><td style="padding:8px 12px;border-bottom:1px solid #1a202c;"><span style="font-family:\'JetBrains Mono\',monospace;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:4px;font-weight:700;color:{r_color};background:{r_color}15;border:1px solid {r_color}33;">{r}</span></td></tr>'

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
    </div>""", height=100 + len(history) * 42)

    if st.button("🗑 Clear History", key="clear_hist"):
        st.session_state.history = []
        st.session_state.result = None
        st.rerun()

# ── Footer ──
render_html("""<div style="text-align:center;padding:20px 0 8px;color:#2d3748;font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1px;">
    INSTITUTIONAL QUALITY COMPOUNDING PROTOCOL v3.0 — NOT FINANCIAL ADVICE
</div>""", height=50)
