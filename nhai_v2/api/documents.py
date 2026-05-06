"""Download tender documents from NHAI and upload to Supabase Storage."""
import hashlib
from pathlib import Path
from typing import Optional

import httpx

from config import DOCS_DIR, REQUEST_TIMEOUT, REQUEST_HEADERS


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def download_document(url: str, tender_id: str) -> Optional[Path]:
    """
    Download a document from NHAI. Returns local Path.
    Skips re-download if already cached locally.
    """
    filename = url.split("/")[-1]
    dest = DOCS_DIR / tender_id
    dest.mkdir(parents=True, exist_ok=True)
    local_path = dest / filename

    if local_path.exists():
        return local_path

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS,
                          verify=False, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            local_path.write_bytes(r.content)
            return local_path
    except Exception as e:
        raise RuntimeError(f"Failed to download {url}: {e}") from e


def download_all_documents(tender_id: str, other_documents: list[dict]) -> list[dict]:
    """
    Download all documents for a tender.
    Returns list of dicts with: url, local_path, description, filesize, filename
    """
    results = []
    for doc in other_documents:
        url = doc.get("file", "").strip()
        if not url:
            continue
        try:
            local_path = download_document(url, tender_id)
            results.append({
                "url": url,
                "local_path": str(local_path),
                "description": doc.get("description", ""),
                "filesize": doc.get("filesize", ""),
                "filename": local_path.name,
                "extension": local_path.suffix.lower(),
            })
        except Exception as e:
            results.append({
                "url": url,
                "local_path": None,
                "description": doc.get("description", ""),
                "filesize": doc.get("filesize", ""),
                "filename": url.split("/")[-1],
                "extension": Path(url).suffix.lower(),
                "error": str(e),
            })
    return results
