import requests
import pandas as pd
from github import Github
from datetime import datetime

# 1. Configuration Keys
FINNHUB_API_KEY = "YOUR_FINNHUB_API_KEY"  # Free key from finnhub.io
GITHUB_TOKEN = "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN" # Created at github.com/settings/tokens
REPO_NAME = "your-username/your-repo"
FILE_PATH = "congress_trades.csv"

def fetch_latest_congress_trades():
    # Fetch congressional disclosures from Finnhub API
    url = f"https://finnhub.io/api/v1/congressional-trading?token={FINNHUB_API_KEY}"
    response = requests.get(url)
    
    if response.status_code != 200:
        print("Failed to fetch data from Finnhub")
        return []
        
    data = response.json().get('data', [])
    new_rows = []
    
    for item in data:
        # We use the filing/disclosure date to avoid lookahead bias
        disclosure_date = item.get('filingDate')
        symbol = item.get('symbol')
        raw_action = item.get('transactionType', '').upper()
        
        # Standardize action labels
        action = None
        if 'PURCHASE' in raw_action or 'BUY' in raw_action:
            action = 'BUY'
        elif 'SALE' in raw_action or 'SELL' in raw_action:
            action = 'SELL'
            
        if disclosure_date and symbol and action:
            new_rows.append({"Date": disclosure_date, "Ticker": symbol, "Action": action})
            
    return new_rows

def update_github_csv(new_trades):
    if not new_trades:
        print("No new trades found.")
        return

    # Authenticate with GitHub API
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    # Retrieve current file content
    contents = repo.get_contents(FILE_PATH)
    current_csv = contents.decoded_content.decode("utf-8")
    
    # Load into Pandas DataFrames to remove duplicates
    existing_df = pd.read_csv(pd.compat.StringIO(current_csv)) if hasattr(pd.compat, 'StringIO') else pd.read_csv(io.StringIO(current_csv))
    new_df = pd.DataFrame(new_trades)
    
    # Merge and deduplicate records
    combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Date', 'Ticker', 'Action'])
    combined_df.sort_values(by='Date', ascending=False, inplace=True)
    
    # Convert updated dataframe back to CSV string
    updated_csv_str = combined_df.to_csv(index=False)
    
    # Commit changes back to GitHub repo
    if updated_csv_str != current_csv:
        repo.update_file(
            path=contents.path,
            message=f"Automated Update: Added new trades on {datetime.now().strftime('%Y-%m-%d')}",
            content=updated_csv_str,
            sha=contents.sha
        )
        print("GitHub CSV updated successfully!")
    else:
        print("CSV is already up to date. No commit needed.")

if __name__ == "__main__":
    trades = fetch_latest_congress_trades()
    update_github_csv(trades)
