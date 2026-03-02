# AI Portfolio Manager

Institutional-grade equity analysis dashboard powered by Claude AI. Implements a three-pillar scoring framework:

- **Fundamental Analysis** (0-30): ROIC, margins, FCF conversion, forensic accounting scores
- **Business Quality** (0-40): Economic moats, management quality, industry structure
- **Valuation** (0-30): DCF margin of safety, PEG, EV multiples

Composite Score (0-100) drives STRONG BUY / BUY / HOLD / SELL recommendations.

## Setup

1. Clone this repo
2. Install dependencies: `pip install -r requirements.txt`
3. Add your Anthropic API key to `.streamlit/secrets.toml`:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   ```
4. Run: `streamlit run app.py`

## Deployment

Hosted on [Streamlit Community Cloud](https://streamlit.io/cloud). See deployment guide for details.

---

*NOT FINANCIAL ADVICE — Institutional Quality Compounding Protocol v3.0*
