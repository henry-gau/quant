import os
import requests
import pandas as pd
from datetime import datetime

BASE_URL = "https://congressinfor-production.up.railway.app"
CSV_FILE_PATH = "congress_trades.csv"

def fetch_and_update_trades():
    print("Fetching recent trades from CongressInvests API...")
    
    url = f"{BASE_URL}/trades/recent"
    params = {"limit": 50, "days": 30}
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Failed to fetch data: {response.status_code} - {response.text}")
        return
        
    data = response.json()
    trades_list = data.get("trades", [])
    
    if not trades_list:
        print("No trades returned from the API.")
        return

    new_rows = []
    for t in trades_list:
        disclosure_date = t.get("disclosed")
        ticker = t.get("ticker")
        raw_action = t.get("trade_type", "").upper()
        
        action = None
        if "BUY" in raw_action or "PURCHASE" in raw_action:
            action = "BUY"
        elif "SELL" in raw_action or "SALE" in raw_action:
            action = "SELL"
            
        if disclosure_date and ticker and action:
            new_rows.append({
                "Date": disclosure_date,
                "Ticker": ticker.strip().upper(),
                "Action": action
            })
            
    if not new_rows:
        print("No valid trade rows to process.")
        return

    new_df = pd.DataFrame(new_rows)
    
    # Safely load existing CSV or create a fresh dataframe if file is empty/corrupted
    if os.path.exists(CSV_FILE_PATH) and os.path.getsize(CSV_FILE_PATH) > 0:
        try:
            existing_df = pd.read_csv(CSV_FILE_PATH)
            combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Date', 'Ticker', 'Action'])
        except Exception as e:
            print(f"Warning: Could not parse existing CSV ({e}). Overwriting with fresh data.")
            combined_df = new_df
    else:
        combined_df = new_df
        
    combined_df.sort_values(by='Date', ascending=False, inplace=True)
    combined_df.to_csv(CSV_FILE_PATH, index=False)
    print(f"Successfully updated {CSV_FILE_PATH} with {len(new_rows)} fetched records!")

if __name__ == "__main__":
    fetch_and_update_trades()
