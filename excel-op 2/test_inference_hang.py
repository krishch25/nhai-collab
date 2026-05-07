import pandas as pd
import uuid
import logging
import sys

from app.db.session import SessionLocal
from app.services.classification_service import run_inference
from app.db.models import ProcessingJob

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Create a dummy DataFrame
df = pd.DataFrame([
    {"Material Description": "TEST PUMP 1HP", "Material Code": "12345"}
])

batch_id = str(uuid.uuid4())
print(f"Starting test for batch: {batch_id}")

# Run inference directly
run_inference(
    batch_id=batch_id,
    file_name="test.xlsx",
    df_inference=df,
    parallel=False
)

# Check status
db = SessionLocal()
job = db.query(ProcessingJob).filter_by(batch_id=batch_id).first()
print(f"Final Job Status: {job.status}")
print(f"Error Log: {job.error_log}")
db.close()
