import pandas as pd
import yfinance as yf
from lightweight_charts import Chart
import math

class VisualTradeManager:
    def __init__(self, symbol, total_capital=100000, risk_percent=0.01):
        self.symbol = symbol.upper()
        self.total_capital = total_capital
        self.risk_percent = risk_percent
        self.chart = Chart()
        
        # Initial Values (Placeholders)
        self.entry_price = 0.0
        self.stoploss_price = 0.0
        self.target_price = 0.0
        
        # Lines
        self.line_entry = None
        self.line_sl = None
        self.line_target = None

    def fetch_data(self):
        print(f"Fetching data for {self.symbol}...")
        df = yf.Ticker(f"{self.symbol}.NS").history(period="1y")
        if df.empty:
            print("No data found.")
            return False
            
        # Format for lightweight-charts
        df = df.reset_index()
        
        # Explicit Column Mapping to avoid any ambiguity or duplicates
        # yfinance typically gives: Date (index), Open, High, Low, Close, Volume
        
        # 1. Ensure Date is handled
        if 'Date' in df.columns:
            df = df.rename(columns={'Date': 'time'})
        elif 'date' in df.columns:
            df = df.rename(columns={'date': 'time'})
            
        # 2. Lowercase all remaining columns
        df.columns = [c.lower() for c in df.columns]
        
        # 3. STRICTLY select only needed columns to remove any inadvertent duplicates
        needed = ['time', 'open', 'high', 'low', 'close', 'volume']
        
        # Filter for existing columns only
        final_cols = [c for c in needed if c in df.columns]
        df = df[final_cols]
        
        # 4. Remove any duplicate columns (just in case)
        df = df.loc[:, ~df.columns.duplicated()]
        
        # 5. Convert time to string format expected by library
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
            
        # Store for internal use
        self.df = df
        
        # Set chart data
        self.chart.set(df)
        self.chart.watermark(self.symbol)
        
        # Set Grid Layout
        self.chart.layout(background_color='#131722', text_color='#d1d4dc')
        
        # Determine initial prices based on current price
        last_close = df.iloc[-1]['close']
        self.entry_price = last_close
        self.stoploss_price = last_close * 0.95 # 5% below
        self.target_price = last_close * 1.10   # 10% above
        
        return True

    def on_line_move(self, line_name):
        pass
            
    def calculate_position(self):
        risk_per_share = self.entry_price - self.stoploss_price
        if risk_per_share <= 0:
            return "⚠️ INVALID: Entry < Stoploss"
            
        max_risk = self.total_capital * self.risk_percent
        qty = math.floor(max_risk / risk_per_share)
        invested = qty * self.entry_price
        
        rr = (self.target_price - self.entry_price) / risk_per_share if risk_per_share > 0 else 0
        
        return (f"📊 PLAN: {self.symbol}\n"
                f"   Op. Risk: ₹{max_risk:.2f} (1%)\n"
                f"   Qty: {qty}\n"
                f"   Invested: ₹{invested:,.2f}\n"
                f"   R:R Ratio: 1:{rr:.2f}")

    def take_screenshot(self, chart):
        # Save screenshot
        filename = f"screenshot_{self.symbol}.png"
        start_dir = os.path.dirname(os.path.abspath(__file__))
        save_path = os.path.join(start_dir, "trade_screenshots", filename)
        
        # Ensure dir exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # The library supports screenshotting
        chart.screenshot(save_path)
        print(f"📸 Screenshot saved: {save_path}")

    def show(self):
        # Create Lines (Series)
        # We simulate horizontal lines by creating a Line Series with constant data
        
        # 1. Entry (Blue)
        self.line_entry = self.chart.create_line('Entry', color='blue', width=2)
        # Library requires specific column name matching line name for 'value'
        entry_data = pd.DataFrame({'time': self.df['time'], 'Entry': self.entry_price})
        self.line_entry.set(entry_data)
        
        # 2. Stoploss (Red)
        self.line_sl = self.chart.create_line('Stoploss', color='red', width=2)
        sl_data = pd.DataFrame({'time': self.df['time'], 'Stoploss': self.stoploss_price})
        self.line_sl.set(sl_data)
        
        # 3. Target (Green)
        self.line_target = self.chart.create_line('Target', color='green', width=2)
        target_data = pd.DataFrame({'time': self.df['time'], 'Target': self.target_price})
        self.line_target.set(target_data)

        # Legend / Top Bar Calculation
        print("\n" + "="*50)
        print(f"🎨 VISUAL MANAGER: {self.symbol}")
        print(f"   Entry: {self.entry_price:.2f}")
        print(f"   SL:    {self.stoploss_price:.2f}")
        print(f"   Tgt:   {self.target_price:.2f}")
        print("   -> Use the 'Camera' icon in the chart toolbar to save a screenshot.")
        print("   -> Close window to exit.")
        print("="*50)
        
        # Toolbox not available in this version, relying on default context menu or hotkeys if available.
        # self.chart.toolbox.save_image_under_dropdown()
        
        self.chart.show(block=True)

if __name__ == "__main__":
    try:
        symbol = input("Enter Symbol: ")
        vtm = VisualTradeManager(symbol)
        if vtm.fetch_data():
            vtm.show()
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    input("\nPress Enter to exit...")
