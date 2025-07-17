import ccxt
import pandas as pd
import numpy as np
import requests, os, csv
from datetime import datetime
from functools import lru_cache
import threading
import concurrent.futures

# ----------------- Cached Exchange -----------------
@lru_cache(maxsize=1)
def get_exchange():
    return ccxt.binance()

# ----------------- Cached OHLCV -----------------
def fetch_ohlcv(symbol='BTC/USDT', timeframe='5m', limit=200):
    exchange = get_exchange()
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# ----------------- RSI -----------------
def compute_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ----------------- Trend -----------------
def detect_trend(df):
    sma5 = df['close'].rolling(window=5).mean()
    sma20 = df['close'].rolling(window=20).mean()
    return "Uptrend" if sma5.iloc[-1] > sma20.iloc[-1] else "Downtrend"

# ----------------- Support/Resistance -----------------
def support_resistance(df):
    return df['low'][-20:].min(), df['high'][-20:].max()

# ----------------- Liquidation -----------------
def get_coinglass_liquidation(symbol="BTC"):
    try:
        base = symbol.replace("USDT", "").replace("/", "").replace("1000", "").upper()
        url = f"https://fapi.coinglass.com/api/futures/liquidation_chart?symbol={base}&type=binance"
        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0",
            "origin": "https://www.coinglass.com",
            "referer": "https://www.coinglass.com/"
        }
        resp = requests.get(url, headers=headers, timeout=8)
        data = resp.json()
        zones = data.get("data", {}).get("binance", [])
        return "\n".join([f"💥 {z['dir']} @ {z['price']} → {round(z['sum'], 2)}M" for z in zones[:5]]) or "No liquidation data."
    except:
        return "❌ Error fetching liquidation"

# ----------------- Thresholds -----------------
THRESHOLDS = {
    "BTC/USDT": 100,
    "ETH/USDT": 7,
    "SOL/USDT": 0.8,
    "XRP/USDT": 0.0020,
    "1000BONK/USDT": 0.00005
}

# ----------------- Signal -----------------
def generate_signal(df, symbol='BTC/USDT'):
    price = df['close'].iloc[-1]
    prev = df['close'].iloc[-4]
    move = abs(price - prev)
    rsi = compute_rsi(df['close']).iloc[-1]
    trend = detect_trend(df)
    support, resistance = support_resistance(df)
    df['hl'] = df['high'] - df['low']
    atr = df['hl'].rolling(14).mean().iloc[-1]

    target = max(THRESHOLDS.get(symbol, 100), atr)
    stop = 0.5 * target
    confidence = 0
    reason = ""
    entry = exit_ = sl = None
    signal = "HOLD"

    if move >= 0.6 * target:
        if rsi < 45:
            signal = "LONG"
            entry, exit_, sl = price, price + target, price - stop
            confidence += 40
            if trend == "Uptrend": confidence += 30
            if price < support: confidence += 20
        elif rsi > 55:
            signal = "SHORT"
            entry, exit_, sl = price, price - target, price + stop
            confidence += 40
            if trend == "Downtrend": confidence += 30
            if price > resistance: confidence += 20

    if confidence < 35:
        signal = "HOLD"
        entry = exit_ = sl = None
        reason = "Low confidence"

    return {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "price": round(price, 6),
        "prev_price": round(prev, 6),
        "price_move": round(move, 6),
        "rsi": round(rsi, 2),
        "trend": trend,
        "entry": round(entry, 6) if entry else None,
        "exit": round(exit_, 6) if exit_ else None,
        "stop_loss": round(sl, 6) if sl else None,
        "support": round(support, 6),
        "resistance": round(resistance, 6),
        "atr": round(atr, 6),
        "reason": reason
    }

# ----------------- Multi-symbol Execution -----------------
def process_symbols(symbols):
    results = []

    def evaluate(symbol):
        try:
            df = fetch_ohlcv(symbol)
            sig = generate_signal(df, symbol)
            results.append(sig)
        except Exception as e:
            results.append({"symbol": symbol, "signal": "ERROR", "reason": str(e)})

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(evaluate, symbols)

    return results
