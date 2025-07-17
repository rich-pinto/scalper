import streamlit as st
import time
from datetime import datetime
import pytz
import altair as alt
import pandas as pd
from btc_scalping_bot import fetch_ohlcv, generate_signal, get_coinglass_liquidation

# ----------------- Page Setup -----------------
st.set_page_config(page_title="Crypto Scalping Bot", layout="centered")
st.title("💹 Crypto Scalping Signal Bot")

# ----------------- Symbol Selector -----------------
symbol_map = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "SOL": "SOL/USDT",
    "XRP": "XRP/USDT",
    "BONK": "1000BONK/USDT"
}
selected = st.selectbox("Select Symbol", list(symbol_map.keys()), index=0)
symbol = symbol_map[selected]

# ----------------- Force rerun on symbol change -----------------
if "prev_symbol" not in st.session_state:
    st.session_state.prev_symbol = None
if st.session_state.prev_symbol != selected:
    st.session_state.prev_symbol = selected
    st.rerun()

# ----------------- Sidebar: Confidence Threshold -----------------
confidence_threshold = st.sidebar.slider("Minimum Confidence to show Trade", min_value=0, max_value=100, value=50, step=5)

# ----------------- Fetch Fresh Data -----------------
with st.spinner(f"Fetching {symbol} data..."):
    df = fetch_ohlcv(symbol=symbol)
    result = generate_signal(df.copy(), symbol=symbol)

# ----------------- Show Signal -----------------
st.markdown(f"### 🔔 Signal for `{symbol}`: `{result['signal']}`")

if result['signal'] != "HOLD":
    color = "🟢" if result['confidence'] >= confidence_threshold else "🟡"
    st.success(f"""
    {color} **Signal**: `{result['signal']}`
    💰 **Entry**: `${result['entry']}`
    🎯 **Target Exit**: `${result['exit']}`
    🔻 **Stop Loss**: `${result['stop_loss']}`
    📈 **Confidence**: `{result['confidence']}`
    """)
else:
    st.info("No trade signal currently. Waiting for better alignment.")

# ----------------- Enlarged Candlestick Chart with Dynamic Y-Scale -----------------
st.subheader(f"📊 {symbol} Candlestick Chart (Last 200 candles)")

df_chart = df.copy()
df_chart['timestamp'] = df_chart['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')

min_price = df_chart['low'].min()
max_price = df_chart['high'].max()
padding = (max_price - min_price) * 0.05
y_min = min_price - padding
y_max = max_price + padding

base = alt.Chart(df_chart).encode(
    x=alt.X('timestamp:T', title='Time (IST)')
)

rule = base.mark_rule().encode(
    y=alt.Y('low:Q', scale=alt.Scale(domain=[y_min, y_max]), title='Price'),
    y2='high:Q',
    color=alt.condition("datum.open < datum.close", alt.value("#26a69a"), alt.value("#ef5350")),
    tooltip=[
        alt.Tooltip('timestamp:T', title='Time (IST)', format='%Y-%m-%d %H:%M:%S'),
        alt.Tooltip('open:Q'),
        alt.Tooltip('close:Q'),
        alt.Tooltip('high:Q'),
        alt.Tooltip('low:Q')
    ]
)

bar = base.mark_bar().encode(
    y='open:Q',
    y2='close:Q',
    color=alt.condition("datum.open < datum.close", alt.value("#26a69a"), alt.value("#ef5350"))
)

chart = (rule + bar).properties(
    width=900,
    height=500
).interactive()

st.altair_chart(chart, use_container_width=True)

# ----------------- Debug Info -----------------
with st.expander("🧠 Debug Details", expanded=True):
    st.write(f"**Current Price**: ${result['price']}")
    st.write(f"**15min Ago Price**: ${result['prev_price']}")
    st.write(f"**$ Change**: ${result['price_move']}")
    st.write(f"**RSI**: {result['rsi']}")
    st.write(f"**Trend**: {result['trend']}")
    st.write(f"**Support**: ${result['support']}")
    st.write(f"**Resistance**: ${result['resistance']}")
    st.write(f"**Confidence**: {result['confidence']}")
    st.write(f"**Entry**: {result['entry']}")
    st.write(f"**Exit**: {result['exit']}")
    st.write(f"**Stop Loss**: {result['stop_loss']}")
    st.json(result)

# ----------------- Liquidation Zones -----------------
with st.expander("📉 Liquidation Heatmap (Preview from Coinglass)"):
    st.code(get_coinglass_liquidation(selected), language='json')

# ----------------- Footer -----------------
now_ist = datetime.now(pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S %Z')
st.caption(f"Last checked: {now_ist}")
