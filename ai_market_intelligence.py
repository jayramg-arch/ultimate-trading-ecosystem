import pandas as pd
import os
from ai_provider_manager import ask_llm

def generate_breadth_brief():
    """
    Reads the latest scanner CSVs and generates a strategic summary.
    """
    files = {
        "Hunters": "FINAL_Hunter_Picks.csv",
        "Pullbacks": "FINAL_Pullback_Picks.csv",
        "Early Birds": "FINAL_EarlyBird_Picks.csv",
        "Leaders": "FINAL_Leader_Picks.csv"
    }
    
    stats = {}
    total_hits = 0
    
    for label, filename in files.items():
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename)
                count = len(df)
                stats[label] = count
                total_hits += count
            except:
                stats[label] = 0
        else:
            stats[label] = 0
            
    if total_hits == 0:
        return "Scanners haven't detected any significant hits in the latest run. Maintain defensive cash positions."
    
    system_instruction = """
    You are the AI COMMANDER. Your role is to assess 'Market Breadth' based on scanner hits.
    - Many Hunters = Market is entering a speculative or aggressive expansion phase.
    - Many Early Birds = Potential bottoming or internal rotation.
    - Many Leaders = Growth-heavy market environment.
    - Low results = Consolidating or risky market.
    """
    
    prompt = f"""
    SCANNER STATS:
    {stats}
    Total Unique Hits: {total_hits}
    
    COMMAND:
    Provide a 2-3 sentence 'Commander's Brief' on the current market environment and how a trader should behave (Aggressive, Defensive, or Selective). 
    Keep it strictly professional and analytical.
    """
    
    return ask_llm(prompt, system_instruction=system_instruction)

if __name__ == "__main__":
    # Test
    print(generate_breadth_brief())
