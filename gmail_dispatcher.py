import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from dotenv import load_dotenv

load_dotenv(override=True)

# Credentials
SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.getenv("GMAIL_RECEIVER_EMAIL", SENDER_EMAIL)  # Default to sending to self

def send_email(subject, body_text="", html_content=None, attachments=[]):
    """
    Core function to dispatch an email via Gmail SMTP.
    """
    if not SENDER_EMAIL or not APP_PASSWORD:
        print("❌ Error: GMAIL_SENDER_EMAIL or GMAIL_APP_PASSWORD not found in .env matching.")
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"Weinstein Commander <{SENDER_EMAIL}>"
    msg['To'] = RECEIVER_EMAIL

    # Set content
    if html_content:
        msg.set_content(body_text)
        msg.add_alternative(html_content, subtype='html')
    else:
        msg.set_content(body_text)

    # Add Attachments
    for file_path in attachments:
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                file_data = f.read()
                file_name = os.path.basename(file_path)
                
            # Basic mime-type guessing
            if file_name.endswith('.csv'):
                maintype = 'text'
                subtype = 'csv'
            elif file_name.endswith('.pdf'):
                maintype = 'application'
                subtype = 'pdf'
            else:
                maintype = 'application'
                subtype = 'octet-stream'
                
            msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_name)
        else:
            print(f"⚠️ Warning: Attachment {file_path} not found.")

    try:
        # Connect to Gmail SMTP server
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
            print(f"✅ Email sent successfully: '{subject}' to {RECEIVER_EMAIL}")
            return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Authentication Error: Invalid App Password or Email. Ensure 2FA is active and App Password is used.")
        return False
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

def dispatch_golden_matches():
    """Aggregates all 4 strategy outputs, ranks them, and emails the Master List as an HTML table."""
    pmap = {"Stage 2 Hunter":"FINAL_Hunter_Picks.csv",
            "Stage 2 Pullback":"FINAL_Pullback_Picks.csv",
            "Early Birds":"FINAL_EarlyBird_Picks.csv",
            "Strong Leaders":"FINAL_Leader_Picks.csv"}
    
    master_dfs = []
    for strat_name, fname in pmap.items():
        if os.path.exists(fname):
            try:
                df_t = pd.read_csv(fname)
                df_t.insert(0, 'Strategy', strat_name)
                master_dfs.append(df_t)
            except: pass
            
    if not master_dfs:
        send_email("🦁 Weinstein Commander: Golden Matches Empty", "No 5-Star setups found today across any strategy.")
        return True
        
    master_df = pd.concat(master_dfs, ignore_index=True)
    
    # Sort by Conviction Score
    conv_map = {'High': 3, 'Medium': 2, 'Low': 1, 'N/A': 0}
    if 'Conviction' in master_df.columns:
        master_df['Conv_Score'] = master_df['Conviction'].map(conv_map).fillna(0)
    else: master_df['Conv_Score'] = 0
        
    sort_cols = ['Conv_Score']
    asc_opts = [False]
    if '%Chg' in master_df.columns:
        sort_cols.append('%Chg')
        asc_opts.append(False)
        
    master_df = master_df.sort_values(by=sort_cols, ascending=asc_opts)
    
    # Clean up columns for email display
    show_cols = ['Strategy', 'Symbol']
    if 'Conviction' in master_df.columns: show_cols.append('Conviction')
    if 'AI Catalyst' in master_df.columns: show_cols.append('AI Catalyst')
    if 'AI_Catalyst' in master_df.columns: show_cols.append('AI_Catalyst')
    if '%Chg' in master_df.columns: show_cols.append('%Chg')
    if 'Volume' in master_df.columns: show_cols.append('Volume')
    
    final_df = master_df[show_cols].head(20) # Top 20 across all
    master_csv_path = "MASTER_Golden_Picks.csv"
    final_df.to_csv(master_csv_path, index=False)
    
    # Format a nice HTML table for mobile reading
    html_table = final_df.to_html(index=False, classes="styled-table", border=0)
    
    html_template = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; }}
          h2 {{ color: #238636; }}
          .styled-table {{ width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 0.9em; }}
          .styled-table thead tr {{ background-color: #238636; color: #ffffff; text-align: left; }}
          .styled-table th, .styled-table td {{ padding: 12px 15px; }}
          .styled-table tbody tr {{ border-bottom: 1px solid #dddddd; }}
          .styled-table tbody tr:nth-of-type(even) {{ background-color: #f3f3f3; }}
          .styled-table tbody tr:last-of-type {{ border-bottom: 2px solid #238636; }}
        </style>
      </head>
      <body>
        <h2>🦁 Weinstein Commander - Ultimate Golden Meta-Ranking</h2>
        <p>Here are the absolute Top Ranked 5-Star setups across ALL active strategies:</p>
        <br>
        {html_table}
        <br>
        <p><em>Autogenerated by Weinstein Commander Web</em></p>
      </body>
    </html>
    """
    
    return send_email(
        subject="🦁 Weinstein Commander: Ultimate Master Ranking",
        body_text="Your Ultimate Meta-Ranked 5-star setups are attached.",
        html_content=html_template,
        attachments=[master_csv_path]
    )

def dispatch_strategic_briefing():
    """Emails the generated Strategic Briefing PDF report to the user."""
    pdf_path = "Strategic_Briefing_Automated.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"⚠️ Report {pdf_path} not found. Cannot email.")
        return False
        
    html_template = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; }}
          h2 {{ color: #238636; }}
        </style>
      </head>
      <body>
        <h2>🦁 Daily Strategic Briefing</h2>
        <p>The latest Market & Sector Strategic Briefing report has been generated successfully.</p>
        <p>Please find the attached PDF detailing Nifty health, Sector Rotation models, and key risk indicators.</p>
        <br>
        <p><em>Autogenerated by Weinstein Commander Web</em></p>
      </body>
    </html>
    """
    
    return send_email(
        subject="📈 Weinstein Commander: Strategic Briefing Report",
        body_text="Your Daily Strategic Briefing PDF is attached.",
        html_content=html_template,
        attachments=[pdf_path]
    )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gmail Dispatcher")
    parser.add_argument("--mode", type=str, choices=["matches", "briefing", "test"], default="test", help="What to email.")
    args = parser.parse_args()
    
    if args.mode == "test":
        send_email("🦁 Commander Web: Connection Test", "If you receive this, your SMTP settings are configured correctly!")
    elif args.mode == "matches":
        dispatch_golden_matches()
    elif args.mode == "briefing":
        dispatch_strategic_briefing()
