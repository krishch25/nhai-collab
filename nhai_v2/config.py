import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# NHAI API
NHAI_BASE = "https://nhai.gov.in"
NHAI_TENDERLIST = f"{NHAI_BASE}/nhai/api/tenderlist"
NHAI_TENDERDETAIL = f"{NHAI_BASE}/nhai/api/tenderdetail"

# EYQ AI — Azure OpenAI protocol
# URL format: {endpoint}/openai/deployments/{model}/chat/completions?api-version={version}
# Auth: header "api-key" (NOT "Authorization: Bearer")
# SSL: verify=False (EY corporate cert)
EYQ_BASE = os.environ["EYQ_INCUBATOR_ENDPOINT"]
EYQ_KEY = os.environ["EYQ_INCUBATOR_KEY"]
EYQ_MODEL = "gpt-5.1"
EYQ_API_VERSION = "2024-02-15-preview"
EYQ_URL = f"{EYQ_BASE}/openai/deployments/{EYQ_MODEL}/chat/completions"
AI_TIMEOUT = 120

# Supabase
# Service key used for CLI/server ops (bypasses RLS, required for Storage uploads).
# Falls back to anon key so fetch/list still work while service key is being set up.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or ""
)

# HTTP
REQUEST_TIMEOUT = 30
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Docs cache dir (local mirror before Supabase upload)
DOCS_DIR = Path(__file__).parent / "documents"
DOCS_DIR.mkdir(exist_ok=True)

# PDF extraction: max chars per section chunk sent to AI
# Increased to use more of the model's 128k context window
PDF_CHUNK_MAX_CHARS = 40000

# If a section's collected text exceeds this, split into batches
PDF_BATCH_THRESHOLD = 70000
PDF_BATCH_SIZE = 50000
