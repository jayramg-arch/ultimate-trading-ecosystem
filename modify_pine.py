import re

PINE_PATH = "Weinstein and Swing Pro Dashboard v67.4.12.pine"

def modify_pine():
    with open(PINE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add finalT1 and finalT2 declaration
    if "var float finalT1" not in content:
        content = content.replace("var float finalTSL = 0.0", "var float finalTSL = 0.0\nvar float finalT1 = 0.0\nvar float finalT2 = 0.0")

    # 2. Reset in the `else` block
    if "finalT1 := 0.0" not in content:
        content = content.replace("finalTSL := 0.0\n", "finalTSL := 0.0\n    finalT1 := 0.0\n    finalT2 := 0.0\n")

    # 3. Add to quick_ent block
    if "finalT1   := 0.0" not in content:
        content = content.replace("finalTSL   := 0.0\n", "finalTSL   := 0.0\n    finalT1   := 0.0\n    finalT2   := 0.0\n")

    # 4. Add to each pX block
    for i in range(1, 31):
        old_block = f"    finalTSL := p{i}_tsl"
        new_block = f"    finalTSL := p{i}_tsl\n    finalT1 := p{i}_t1\n    finalT2 := p{i}_t2"
        if new_block not in content:
            content = content.replace(old_block, new_block)

    # 5. Modify Target Logic
    # Original: float t1_val = finalEntry + (risk_per_share * dyn_T1_R)
    old_t1 = "float t1_val = finalEntry + (risk_per_share * dyn_T1_R)"
    new_t1 = "float t1_val = finalT1 > 0 ? finalT1 : finalEntry + (risk_per_share * dyn_T1_R)"
    content = content.replace(old_t1, new_t1)

    old_t2 = "float t2_val = finalEntry + (risk_per_share * dyn_T2_R)"
    new_t2 = "float t2_val = finalT2 > 0 ? finalT2 : finalEntry + (risk_per_share * dyn_T2_R)"
    content = content.replace(old_t2, new_t2)

    with open(PINE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("✅ Pine script routing logic successfully updated.")

if __name__ == "__main__":
    modify_pine()
