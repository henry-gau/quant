import csv
import os
from datetime import datetime, timedelta, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetCalendarRequest,
    GetOrdersRequest,
    MarketOrderRequest,
)

# --- CONFIGURATION ---
CSV_FILE = "congress_trades.csv"
ALLOCATION_PCT = 0.10      # 10% of portfolio equity per BUY position
HOLD_DAYS = 60             # Mandatory holding period before automatic exit
TRADING_DAY_WINDOW = 3     # Number of NYSE trading days to look back in the CSV
PAPER_TRADING = True       # Set to False only when switching to live money


def main():
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        print("ERROR: Missing ALPACA_API_KEY or ALPACA_SECRET_KEY environment variables.")
        return

    trading_client = TradingClient(api_key, secret_key, paper=PAPER_TRADING)

    # 1. Verify market is currently open
    clock = trading_client.get_clock()
    if not clock.is_open:
        print("Market is closed right now. Skipping execution.")
        return

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # 2. Fetch the last 3 actual NYSE trading days (automatically bridges weekends & holidays)
    calendar = trading_client.get_calendar(
        GetCalendarRequest(start=(now - timedelta(days=14)).date(), end=now.date())
    )
    valid_dates = {day.date.strftime("%Y-%m-%d") for day in calendar[-TRADING_DAY_WINDOW:]}
    print(f"Active 3-trading-day window: {sorted(valid_dates)}")

    # 3. Load account details and currently open positions
    account = trading_client.get_account()
    portfolio_value = float(account.portfolio_value)
    buying_power = float(account.buying_power)
    positions = {pos.symbol: pos for pos in trading_client.get_all_positions()}

    # 4. Enforce 60-day mandatory holding exit on existing positions
    if positions:
        filled_buys = trading_client.get_orders(
            GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                side=OrderSide.BUY,
                limit=500,
            )
        )
        latest_entry_by_symbol = {}
        for order in filled_buys:
            if order.filled_at and order.symbol in positions:
                prev = latest_entry_by_symbol.get(order.symbol)
                if prev is None or order.filled_at > prev:
                    latest_entry_by_symbol[order.symbol] = order.filled_at

        for symbol, filled_at in list(latest_entry_by_symbol.items()):
            days_held = (now - filled_at).days
            if days_held >= HOLD_DAYS:
                trading_client.close_position(symbol)
                del positions[symbol]
                print(f"60-DAY EXIT: Liquidated {symbol} after {days_held} days held.")

    # 5. Read CSV and resolve only the latest signal per ticker in the 3-trading-day window
    if not os.path.exists(CSV_FILE):
        print(f"ERROR: {CSV_FILE} not found.")
        return

    latest_signals = {}  # {ticker: (date_str, action)}
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3 or row[0].strip().lower() == "date":
                continue

            date_str = row[0].strip()
            ticker = row[1].strip().upper()
            action = row[2].strip().upper()

            if date_str not in valid_dates or action not in {"BUY", "SELL"}:
                continue

            # Keep the most recent filing date; on same-day ties, SELL overrides BUY
            if ticker not in latest_signals:
                latest_signals[ticker] = (date_str, action)
            else:
                prev_date, prev_action = latest_signals[ticker]
                if date_str > prev_date or (date_str == prev_date and action == "SELL"):
                    latest_signals[ticker] = (date_str, action)

    if not latest_signals:
        print("No actionable signals found in the current 3-trading-day window.")
        return

    # 6. Execute resolved signals
    for ticker, (date_str, action) in latest_signals.items():
        if action == "BUY":
            if ticker in positions:
                print(f"SKIP BUY: Already holding {ticker}.")
                continue

            notional_amount = round(portfolio_value * ALLOCATION_PCT, 2)
            if buying_power < notional_amount or notional_amount < 1.0:
                print(
                    f"SKIP BUY: Insufficient buying power (${buying_power:.2f}) "
                    f"for ${notional_amount:.2f} allocation of {ticker}."
                )
                continue

            try:
                order_data = MarketOrderRequest(
                    symbol=ticker,
                    notional=notional_amount,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
                trading_client.submit_order(order_data=order_data)
                positions
