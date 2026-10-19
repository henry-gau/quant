import os
import requests
import pandas as pd
from datetime import datetime

# Official production base URL for the CongressInvests API
BASE_URL = "https://congressinfor-production.up.railway.app"[cite: 7]
CSV_FILE_PATH = "congress_trades.csv"

def fetch_and_update_trades():
    print("Fetching recent trades from CongressInvests API...")
    
    # Request recent trades using the free tier parameters (limit and days)[cite: 8]
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
        # Extract fields based on the API response structure[cite: 8]
        disclosure_date = t.get("disclosed")
        ticker = t.get("ticker")
        raw_action = t.get("trade_type", "").upper()
        
        # Standardize trade action labels to BUY or SELL
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
    
    # Load existing CSV file if it already exists, otherwise create a new DataFrame
    if os.path.exists(CSV_FILE_PATH):
        existing_df = pd.read_csv(CSV_FILE_PATH)
        # Combine existing records with new records and remove duplicates
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Date', 'Ticker', 'Action'])
    else:
        combined_df = new_df
        
    # Sort data chronologically or by date descending
    combined_df.sort_values(by='Date', ascending=False, inplace=True)
    
    # Save back to the local CSV file
    combined_df.to_csv(CSV_FILE_PATH, index=False)
    print(f"Successfully updated {CSV_FILE_PATH} with {len(new_rows)} fetched records!")

if __name__ == "__main__":
    fetch_and_update_trades()
