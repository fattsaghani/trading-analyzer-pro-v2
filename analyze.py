import os
import re
import sys
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

# Try to import MetaTrader5 for live data
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import target account from config (set MT5_ACCOUNT in config.py)
try:
    from config import MT5_ACCOUNT
    TARGET_ACCOUNT = MT5_ACCOUNT
except (ImportError, AttributeError):
    TARGET_ACCOUNT = None  # None = use any available account


# =============================================================================
# LIVE MT5 DATA (AUTOMATIC - NO MANUAL EXPORT)
# =============================================================================
def get_mt5_live_data():
    """Get live trading data directly from MT5 - FULLY AUTOMATIC"""
    if not MT5_AVAILABLE:
        return None, "MetaTrader5 package not installed"
    
    if not mt5.initialize():
        return None, f"MT5 init failed: {mt5.last_error()}"
    
    try:
        # Get account info
        account = mt5.account_info()
        if account is None:
            return None, "Could not get account info"
        
        # Check if connected to correct account (if TARGET_ACCOUNT is set)
        if TARGET_ACCOUNT and account.login != TARGET_ACCOUNT:
            return None, f"Wrong account ({account.login}), need {TARGET_ACCOUNT}"
        
        # Get all closed deals (history)
        from_date = datetime(2020, 1, 1)
        to_date = datetime.now() + timedelta(days=1)
        
        deals = mt5.history_deals_get(from_date, to_date)
        
        if deals is None or len(deals) == 0:
            # Return basic account info even if no deals
            return {
                "data_source": "MT5_LIVE",
                "total_trades": 0,
                "total_profit": round(account.profit, 2),
                "wins": 0,
                "losses": 0,
                "winrate": 0.0,
                "equity_curve": [],
                "profit_by_symbol": [],
                "profit_by_hour": [],
                "monthly_profit": [],
                "balance": round(account.balance, 2),
                "equity": round(account.equity, 2),
                "margin": round(account.margin, 2),
                "free_margin": round(account.margin_free, 2),
            }, None
        
        # Convert to DataFrame
        df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        
        # Filter only closed trades (entry type 1 = out)
        # Deal types: 0=buy, 1=sell; Entry: 0=in, 1=out, 2=inout, 3=out_by
        closed_deals = df[df['entry'] == 1].copy()
        
        if closed_deals.empty:
            return {
                "data_source": "MT5_LIVE",
                "total_trades": 0,
                "total_profit": round(account.profit, 2),
                "wins": 0,
                "losses": 0,
                "winrate": 0.0,
                "equity_curve": [],
                "profit_by_symbol": [],
                "profit_by_hour": [],
                "monthly_profit": [],
                "balance": round(account.balance, 2),
                "equity": round(account.equity, 2),
            }, None
        
        # Calculate stats
        closed_deals['time_dt'] = pd.to_datetime(closed_deals['time'], unit='s')
        closed_deals = closed_deals.sort_values('time_dt').reset_index(drop=True)
        
        total_trades = len(closed_deals)
        wins = len(closed_deals[closed_deals['profit'] > 0])
        losses = len(closed_deals[closed_deals['profit'] < 0])
        total_profit = closed_deals['profit'].sum()
        winrate = wins / total_trades if total_trades > 0 else 0.0
        
        # Equity curve
        equity_curve = []
        cum = 0.0
        for i, row in closed_deals.iterrows():
            cum += row['profit']
            equity_curve.append({"x": len(equity_curve) + 1, "y": round(cum, 2)})
        
        # Profit by symbol
        profit_by_symbol = []
        grp_sym = closed_deals.groupby('symbol')['profit'].sum().sort_values(ascending=False)
        for sym, val in grp_sym.items():
            profit_by_symbol.append({"symbol": str(sym), "profit": round(float(val), 2)})
        
        # Profit by hour
        profit_by_hour = []
        closed_deals['hour'] = closed_deals['time_dt'].dt.hour
        grp_hour = closed_deals.groupby('hour')['profit'].sum().sort_index()
        for hr, val in grp_hour.items():
            profit_by_hour.append({"hour": int(hr), "profit": round(float(val), 2)})
        
        # Monthly profit
        monthly_profit = []
        closed_deals['month'] = closed_deals['time_dt'].dt.to_period('M')
        grp_month = closed_deals.groupby('month')['profit'].sum()
        for month, val in grp_month.items():
            monthly_profit.append({"month": str(month), "profit": round(float(val), 2)})
        
        return {
            "data_source": "MT5_LIVE",
            "total_trades": int(total_trades),
            "total_profit": round(float(total_profit), 2),
            "wins": int(wins),
            "losses": int(losses),
            "winrate": round(float(winrate), 4),
            "equity_curve": equity_curve,
            "profit_by_symbol": profit_by_symbol,
            "profit_by_hour": profit_by_hour,
            "monthly_profit": monthly_profit,
            "balance": round(account.balance, 2),
            "equity": round(account.equity, 2),
            "margin": round(account.margin, 2),
            "free_margin": round(account.margin_free, 2),
        }, None
        
    except Exception as e:
        return None, str(e)
    finally:
        pass


# =============================================================================
# HTML FALLBACK (Original code for when MT5 not available)
# =============================================================================
def _read_html_robust(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()

    if not raw:
        return ""

    if raw.startswith(b"\xff\xfe"):
        txt = raw.decode("utf-16-le", errors="ignore")
    elif raw.startswith(b"\xfe\xff"):
        txt = raw.decode("utf-16-be", errors="ignore")
    elif raw.startswith(b"\xef\xbb\xbf"):
        txt = raw.decode("utf-8-sig", errors="ignore")
    else:
        nul_ratio = raw.count(b"\x00") / max(1, len(raw))
        if nul_ratio > 0.05:
            txt = raw.decode("utf-16-le", errors="ignore")
        else:
            txt = raw.decode("utf-8", errors="ignore")

    return txt.replace("\x00", "")


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_money(s: str):
    s = _norm(s)
    if not s:
        return None
    s = s.replace(" ", "").replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def _parse_int(s: str):
    s = _norm(s)
    if not s:
        return None
    s = s.replace(" ", "").replace(",", "")
    m = re.search(r"-?\d+", s)
    if not m:
        return None
    try:
        return int(m.group(0))
    except Exception:
        return None


def _extract_b_after_label(html: str, label: str):
    pattern = rf"{re.escape(label)}\s*</td>.*?<b>\s*([^<]+?)\s*</b>"
    m = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return _norm(m.group(1))


def _extract_count_pct_after_label(html: str, label: str):
    txt = _extract_b_after_label(html, label)
    if txt is None:
        return None, None
    cnt = _parse_int(txt)
    pct = None
    m2 = re.search(r"\(([-+]?\d+(?:\.\d+)?)%\)", txt)
    if m2:
        try:
            pct = float(m2.group(1))
        except Exception:
            pct = None
    return cnt, pct


def _parse_results_summary(html: str):
    total_profit = _parse_money(_extract_b_after_label(html, "Total Net Profit:"))
    total_trades = _parse_int(_extract_b_after_label(html, "Total Trades:"))
    wins, winrate_pct = _extract_count_pct_after_label(html, "Profit Trades (% of total):")
    losses, _ = _extract_count_pct_after_label(html, "Loss Trades (% of total):")

    winrate = None
    if winrate_pct is not None:
        winrate = float(winrate_pct) / 100.0
    elif wins is not None and losses is not None and (wins + losses) > 0:
        winrate = float(wins) / float(wins + losses)

    return {
        "total_profit": total_profit,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
    }


_DT_RE = re.compile(r"\b(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})\b")


def _parse_dt(s: str):
    s = _norm(s)
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
    except Exception:
        return None


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return _norm(s)


def _extract_positions_block(html: str) -> str:
    m = re.search(r"<b>\s*Positions\s*</b>", html, flags=re.IGNORECASE)
    if not m:
        return ""

    start = m.start()
    tail = html[start:]

    m2 = re.search(r"<b>\s*Results\s*</b>", tail, flags=re.IGNORECASE)
    if m2:
        return tail[: m2.start()]
    return tail


def _parse_positions_rows_for_charts(html: str):
    block = _extract_positions_block(html)
    if not block:
        return [], {"positions_block_found": False, "rows_seen": 0, "rows_parsed": 0}

    trs = re.findall(r"<tr\b[^>]*>(.*?)</tr>", block, flags=re.IGNORECASE | re.DOTALL)

    rows = []
    rows_seen = 0
    rows_parsed = 0

    for tr_inner in trs:
        if 'colspan="2"' not in tr_inner and "colspan='2'" not in tr_inner:
            continue

        dt_matches = _DT_RE.findall(tr_inner)
        if len(dt_matches) < 1:
            continue

        tds = re.findall(r"<td\b[^>]*>(.*?)</td>", tr_inner, flags=re.IGNORECASE | re.DOTALL)
        if len(tds) < 6:
            continue

        rows_seen += 1

        symbol = _strip_tags(tds[2]) if len(tds) >= 3 else ""
        if not symbol:
            continue

        close_time = _parse_dt(dt_matches[-1])

        profit_raw = _strip_tags(tds[-1])
        profit = _parse_money(profit_raw)
        if profit is None:
            continue

        rows_parsed += 1
        rows.append({"symbol": symbol, "profit": float(profit), "t": close_time})

    dbg = {
        "positions_block_found": True,
        "rows_seen": rows_seen,
        "rows_parsed": rows_parsed,
    }
    return rows, dbg


def _build_charts(rows):
    if not rows:
        return {"equity_curve": [], "profit_by_symbol": [], "profit_by_hour": []}

    df = pd.DataFrame(rows)

    if "t" in df.columns and df["t"].notna().any():
        df = df.sort_values(by="t", na_position="last").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    equity_curve = []
    cum = 0.0
    for i, p in enumerate(df["profit"].tolist(), start=1):
        cum += float(p)
        equity_curve.append({"x": int(i), "y": float(round(cum, 2))})

    profit_by_symbol = []
    grp_sym = df.groupby("symbol")["profit"].sum().sort_values(ascending=False)
    for sym, val in grp_sym.items():
        profit_by_symbol.append({"symbol": str(sym), "profit": float(round(float(val), 2))})

    profit_by_hour = []
    if "t" in df.columns and df["t"].notna().any():
        dfh = df.dropna(subset=["t"]).copy()
        if not dfh.empty:
            dfh["hour"] = dfh["t"].map(lambda d: int(d.hour))
            grp_h = dfh.groupby("hour")["profit"].sum().sort_index()
            for hr, val in grp_h.items():
                profit_by_hour.append({"hour": int(hr), "profit": float(round(float(val), 2))})

    return {
        "equity_curve": equity_curve,
        "profit_by_symbol": profit_by_symbol,
        "profit_by_hour": profit_by_hour,
    }


def get_html_data():
    """Fallback: Get data from HTML file"""
    html_path = os.path.join(BASE_DIR, "history.html")
    if not os.path.exists(html_path):
        return {"error": f"history.html not found at: {html_path}"}

    html = _read_html_robust(html_path)
    if not html.strip():
        return {"error": "history.html appears empty after decoding."}

    results = _parse_results_summary(html)
    rows, pos_dbg = _parse_positions_rows_for_charts(html)
    charts = _build_charts(rows)

    return {
        "data_source": "HTML",
        "total_trades": int(results.get("total_trades") or 0),
        "total_profit": float(round(float(results.get("total_profit") or 0.0), 2)),
        "wins": int(results.get("wins") or 0),
        "losses": int(results.get("losses") or 0),
        "winrate": float(results.get("winrate") or 0.0),
        "equity_curve": charts["equity_curve"],
        "profit_by_symbol": charts["profit_by_symbol"],
        "profit_by_hour": charts["profit_by_hour"],
        "monthly_profit": [],
        "chart_debug": pos_dbg,
    }


# =============================================================================
# MAIN FUNCTION - TRIES MT5 FIRST, FALLS BACK TO HTML
# =============================================================================
def get_trade_data():
    """Get trade data - automatically from MT5 if available, otherwise from HTML"""
    
    # Try MT5 live data first (AUTOMATIC)
    data, error = get_mt5_live_data()
    if data is not None:
        return data
    
    # If wrong account error, don't fallback - show error
    if error and "Wrong account" in error:
        return {
            "data_source": "ERROR",
            "error": error,
            "total_trades": 0,
            "total_profit": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0,
            "equity_curve": [],
            "profit_by_symbol": [],
            "profit_by_hour": [],
            "monthly_profit": [],
        }
    
    # Fallback to HTML file only if MT5 not installed/running
    print(f"[ANALYZER] MT5 not available ({error}), using HTML fallback")
    return get_html_data()

def analyze_user_file(file_path: str):
    """Analyze a user's uploaded trade history file"""
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    
    html = _read_html_robust(file_path)
    if not html.strip():
        return {"error": "File appears empty"}
    
    results = _parse_results_summary(html)
    rows, pos_dbg = _parse_positions_rows_for_charts(html)
    charts = _build_charts(rows)
    
    return {
        "data_source": "UPLOADED",
        "total_trades": int(results.get("total_trades") or 0),
        "total_profit": float(round(float(results.get("total_profit") or 0.0), 2)),
        "wins": int(results.get("wins") or 0),
        "losses": int(results.get("losses") or 0),
        "winrate": float(results.get("winrate") or 0.0),
        "equity_curve": charts["equity_curve"],
        "profit_by_symbol": charts["profit_by_symbol"],
        "profit_by_hour": charts["profit_by_hour"],
        "monthly_profit": [],
    }