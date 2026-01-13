# TradeBoard v2 — Antifragile MTF Bot + Streamlit UI

Deterministic Pine-parity core with:
- HTF bias (1D/1W), MidTF choppiness (4H/1H CHOP), 3m executor.
- Pivot-confirmed RSI divergence (left/right) with range window (Pine-like).
- BB squeeze prefilter; DXY weekly volatility filter.
- Cooldown only after SL; fees modeled (0.05%/side).
- No ML sizing; Pine-style stops and HTF gate.

## Quickstart
```bash
python -m venv .venv && . .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python backtest.py
```

Run the UI:

```bash
streamlit run streamlit_app.py
```

Environment (optional):

```bash
export TELEGRAM_TOKEN=YOUR_BOT_TOKEN
export TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

Edit `config.yaml` to tweak symbol/timeframes/params.
