import os
import csv
from datetime import datetime, timedelta, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

# Connect to Alpaca Paper Trading
API_KEY = os.environ["ALPACA_API_KEY"]
SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

CSV_FILE = "congress_trades.csv"
HOLDING_PERIOD_DAYS = 60
ALLOCATION_PCT = 0.10

def main():
    # 1. Check if the stock market is open right now
    clock = trading_client.get_clock()
    if not clock.is_open:
        print("Market is closed today. Skipping execution.")
        return

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    valid_dates = {(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)}

    # 2. Get current account equity and open positions
    account = trading_client.get_account()
    portfolio_value = float(account.portfolio_value)
    positions = {p.symbol: p for p in trading_client.get_all_positions()}

    # 3. Enforce 60-day time-based exit using Alpaca's filled order history
    filled_orders = trading_client.get_orders(
        GetOrdersRequest(status=QueryOrderStatus.CLOSED, side=OrderSide.BUY, limit=500)
    )
    latest_buy_date = {}
    for order in filled_orders:
        if order.filled_at and order.symbol not in latest_buy_date:
            latest_buy_date[order.symbol] = order.filled_at

    for symbol in list(positions.keys()):
        if symbol in latest_buy_date:
            days_held = (now - latest_buy_date[symbol]).days
            if days_held >= HOLDING_PERIOD_DAYS:
                trading_client.close_position(symbol)
                print(f"TIME EXIT: Liquidated {symbol} after {days_held} days.")

    # 4. Read CSV and process 3-day rolling window signals
    if not os.path.exists(CSV_FILE):
        print(f"ERROR: {CSV_FILE} not found.")
        return

    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3 or row[0].strip().lower() == "date":
                continue

            date_str = row[0].strip()
            ticker = row[1].strip().upper()
            action = row[2].strip().upper()

            if date_str not in valid_dates:
                continue

            if action == "BUY" and ticker not in positions:
                notional_amount = round(portfolio_value * ALLOCATION_PCT, 2)
                if float(account.buying_power) >= notional_amount and notional_amount >= 1.0:
                    order_data = MarketOrderRequest(
                        symbol=ticker,
                        notional=notional_amount,  # Buys exact 10% dollar amount via fractional shares
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY
                    )
                    trading_client.submit_order(order_data=order_data)
                    positions[ticker] = True  # Prevent duplicate buys in same run
                    print(f"EXECUTED BUY: ${notional_amount} of {ticker} (Filed: {date_str}, Executed: {today_str})")

            elif action == "SELL" and ticker in positions:
                trading_client.close_position(ticker)
                del positions[ticker]
                print(f"EXECUTED SELL: Liquidated {ticker} (Filed: {date_str}, Executed: {today_str})")

if __name__ == "__main__":
    main()
