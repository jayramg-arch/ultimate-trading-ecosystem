import pandas as pd
from ai_provider_manager import ask_llm

def serialize_portfolio(df):
    """Converts the active ledger dataframe into a compact text format for AI context."""
    if df.empty:
        return "No active trades found."
    
    # Select key columns for AI context
    # Use requested column names from the customized ledger
    cols = ['Sr #', 'Symbol', 'Sector', 'P&L', 'Ageing', 'Status']
    # Filter only available columns to avoid errors
    available_cols = [c for c in cols if c in df.columns]
    
    context_df = df[available_cols].copy()
    
    # Format P&L to string with Currency
    if 'P&L' in context_df.columns:
        context_df['P&L'] = context_df['P&L'].map(lambda x: f"INR {x:,.2f}")
    
    return context_df.to_string(index=False)

def get_commander_response(query, portfolio_df):
    """Processes natural language queries against the portfolio context."""
    
    portfolio_context = serialize_portfolio(portfolio_df)
    
    system_instruction = """
    You are the AI COMMANDER, a strategic risk desk manager. 
    You have full access to the user's active trading ledger.
    Your tone is authoritative, punchy, and professional. 
    Focus on risk, performance trends, and sector concentration.
    If asked for a summary, give a 2-3 sentence strategic brief.
    If asked about a specific stock, provide its current status from the data.
    """
    
    prompt = f"""
    USER QUERY: {query}
    
    CURRENT ACTIVE PORTFOLIO DATA:
    {portfolio_context}
    
    Based on the data above, provide a strategic response to the user. 
    - If the portfolio is empty, encourage them to find 'Hunters' from the scanners.
    - If a specific sector is over-represented, mention the concentration risk.
    - Highlight the biggest winners or losers if relevant.
    """
    
    return ask_llm(prompt, system_instruction=system_instruction)

if __name__ == "__main__":
    # Test stub
    test_data = pd.DataFrame([
        {'Sr #': 1, 'Symbol': 'RELIANCE', 'Sector': 'Energy', 'P&L': 1500.0, 'Ageing': '5 days', 'Status': 'Winning'},
        {'Sr #': 2, 'Symbol': 'TCS', 'Sector': 'IT', 'P&L': -450.0, 'Ageing': '2 days', 'Status': 'Losing'}
    ])
    print(get_commander_response("Give me a strategic brief", test_data))
