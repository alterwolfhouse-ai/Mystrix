import yaml
import pandas as pd
import streamlit as st
from engine.bot import RemixBot
from engine.data import resample_ohlcv

st.set_page_config(page_title="TradeBoard v2", layout="wide")

@st.cache_resource
def load_cfg():
    with open("config.yaml","r") as f:
        return yaml.safe_load(f)

cfg = load_cfg()
st.title("🧭 TradeBoard v2 — Antifragile MTF Bot")

colA, colB, colC = st.columns(3)
with colA:
    start = st.text_input("Backtest start", cfg["backtest_start"])
with colB:
    end = st.text_input("Backtest end", cfg["backtest_end"])
with colC:
    init_cap = st.number_input("Initial capital", value=float(cfg["initial_capital"]), step=100.0)

run = st.button("Run Backtest")

if run:
    cfg["backtest_start"] = start
    cfg["backtest_end"] = end
    cfg["initial_capital"] = init_cap
    bot = RemixBot(cfg)
    metrics = bot.run_backtest()
    st.subheader("Metrics")
    st.json(metrics)

    # Show recent trades table
    trades_df = pd.DataFrame(bot.trades)
    if not trades_df.empty:
        st.subheader("Trades")
        st.dataframe(trades_df.tail(200), use_container_width=True)

        # Simple equity curve from trades
        equity = float(cfg["initial_capital"])
        eq = []
        for t in bot.trades:
            if t["type"] == "enter":
                # fee accounted in bot.equity metrics; here we just chart equity snapshots
                pass
            if t["type"].startswith("exit"):
                equity += t["pnl"]
            eq.append(equity)
        if eq:
            st.subheader("Equity (stepwise)")
            st.line_chart(pd.Series(eq))
else:
    st.info("Adjust dates/capital and click Run Backtest.")

