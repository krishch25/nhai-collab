from app.db.session import SessionLocal
from app.services.classification_service import run_training
from app.services.excel_service import read_training_excel
import os

db = SessionLocal()
file_path = "data/output_data.xlsx"
df = read_training_excel(file_path)

print("Starting run_training...")
res = run_training(db, batch_id="TEST-1234", file_name="output_data.xlsx", df_training=df)
print("Result:", res)
