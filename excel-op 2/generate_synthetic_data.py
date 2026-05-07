import pandas as pd
import uuid
import random

# Base data provided by user with all required columns
base_data = [
    {"Material Code": "232917", "Material Type": "Subassembly", "Material Description": "P.BOX 1.0HP CSCR DVAM ABS CRI 4\" M1", "L0": "Production Material", "L1": "Mechanical Material", "L2": "Subassembly"},
    {"Material Code": "100552", "Material Type": "Machined Material", "Material Description": "SHAFT FOR 1.0HP PUMP STAINLESS STEEL", "L0": "Production Material", "L1": "Mechanical Material", "L2": "Machined Material"},
    {"Material Code": "990011", "Material Type": "Consumables", "Material Description": "INDUSTRIAL GREASE 500G HIGH TEMP", "L0": "Indirect Material", "L1": "Consumables", "L2": "Lubricants"},
]

def synthesize_variations(base_list, count=100):
    synthetic_rows = []
    
    for _ in range(count):
        base = random.choice(base_list)
        row = base.copy()
        
        # Unique Material Code
        row["Material Code"] = str(random.randint(100000, 999999))
        
        if row["Material Type"] == "Subassembly":
            power = random.choice(["0.5HP", "1.5HP", "2.0HP", "5.0HP"])
            brand = random.choice(["CRI", "Kirloskar", "Texmo", "Grundfos"])
            row["Material Description"] = f"P.BOX {power} CSCR DVAM ABS {brand} 4\" M1"
        elif row["Material Type"] == "Machined Material":
            material = random.choice(["SS304", "SS316", "MS", "CAST IRON"])
            part = random.choice(["SHAFT", "IMPELLER", "CASING", "FLANGE"])
            row["Material Description"] = f"{part} FOR {random.choice(['0.5hp','1hp','2hp'])} PUMP {material}"
        else: # Consumables
            item = random.choice(["GREASE", "OIL", "CLEANING AGENT"])
            vol = random.choice(["100G", "1KG", "5KG", "10KG"])
            row["Material Description"] = f"INDUSTRIAL {item} {vol} {random.choice(['HIGH TEMP', 'FOOD GRADE', 'SYNTHETIC'])}"
            
        synthetic_rows.append(row)

    return pd.DataFrame(synthetic_rows)

if __name__ == "__main__":
    df = synthesize_variations(base_data, 100)
    # Ensure column names match the exact expected training schema (lowercase check)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    output_path = "data/synthetic_training_large.xlsx"
    df.to_excel(output_path, index=False)
    print(f"Generated 100 enterprise-compliant synthetic rows at {output_path}")
