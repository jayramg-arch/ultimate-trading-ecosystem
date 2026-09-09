import re
from datetime import datetime

STALE_PATTERN = re.compile(r"(-\d{2}[A-Z]{3}\d{2})$", re.IGNORECASE)

def get_stale_watchlists(all_watchlist_names):
    # Dictionary to hold the latest date for each base name
    # base_name -> (latest_date_obj, full_name)
    latest_watchlists = {}
    
    # Also track watchlists that match the pattern to know which ones are candidates for deletion
    auto_watchlists = []
    
    for name in all_watchlist_names:
        match = STALE_PATTERN.search(name)
        if match:
            date_str = match.group(1)[1:] # Remove the leading dash
            try:
                date_obj = datetime.strptime(date_str, "%d%b%y")
                base_name = name[:match.start()]
                auto_watchlists.append({'name': name, 'base': base_name, 'date': date_obj})
                
                if base_name not in latest_watchlists or date_obj > latest_watchlists[base_name]['date']:
                    latest_watchlists[base_name] = {'name': name, 'date': date_obj}
            except ValueError:
                pass # Invalid date format, ignore
                
    to_delete = []
    # Any auto-watchlist that is NOT the latest for its base name is stale
    latest_names = {v['name'] for v in latest_watchlists.values()}
    for item in auto_watchlists:
        if item['name'] not in latest_names:
            to_delete.append(item['name'])
            
    # Also delete anything matching [Auto]
    for name in all_watchlist_names:
        if "[Auto]" in name:
            to_delete.append(name)
            
    return to_delete

# Test
names = [
    "Bull_Hunter-11JUN26",
    "Bull_Hunter-15JUN26",
    "portfolio-11JUN26",
    "portfolio-15JUN26",
    "Nifty 50",
    "FINAL_WATCHLIST-14JUN26",
    "FINAL_WATCHLIST-15JUN26",
    "Old stuff [Auto]"
]
print(get_stale_watchlists(names))
