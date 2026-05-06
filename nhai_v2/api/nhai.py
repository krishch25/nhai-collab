import httpx
from config import NHAI_TENDERLIST, NHAI_TENDERDETAIL, REQUEST_TIMEOUT, REQUEST_HEADERS


def _client() -> httpx.Client:
    return httpx.Client(timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS, verify=False)


def fetch_tender_list(page: int = 0, page_size: int = 10000) -> list[dict]:
    with _client() as c:
        r = c.post(NHAI_TENDERLIST, data={
            "language": "en",
            "index": str(page),
            "totalrecord": str(page_size),
            "tender_no": "",
            "title": "",
        })
        r.raise_for_status()
        data = r.json()
        if data.get("_resultflag") != 1:
            raise RuntimeError(f"NHAI API error: {data.get('message')}")
        return data.get("list", [])


def fetch_tender_detail(nid: str) -> dict:
    with _client() as c:
        r = c.post(NHAI_TENDERDETAIL, data={"nid": nid, "language": "en"})
        r.raise_for_status()
        data = r.json()
        if data.get("_resultflag") != 1:
            raise RuntimeError(f"Detail API error for nid={nid}: {data.get('message')}")
        return data["detail"]
