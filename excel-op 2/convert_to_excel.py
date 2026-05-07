import pandas as pd

# Convert input TSV to excel
input_df = pd.read_csv('data/input_data.tsv', sep='\t')
input_df.to_excel('data/input_data.xlsx', index=False)

# Convert output TSV to excel
output_df = pd.read_csv('data/output_data.tsv', sep='\t')
output_df.to_excel('data/output_data.xlsx', index=False)

print("Created input_data.xlsx and output_data.xlsx in data/ directory")
