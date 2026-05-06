"""
PDF text extraction with page-level tracking.
Each extracted block carries its source page number for citations.
"""
from pathlib import Path
from typing import Optional
import pdfplumber


class PagedText:
    """Text content from a single PDF page."""
    def __init__(self, page_num: int, text: str):
        self.page_num = page_num   # 1-indexed
        self.text = text.strip()

    def __bool__(self):
        return bool(self.text)


class ExtractedDocument:
    def __init__(self, path: Path, pages: list[PagedText]):
        self.path = path
        self.pages = [p for p in pages if p]
        self.total_pages = len(pages)

    def full_text(self) -> str:
        return "\n\n".join(
            f"[PAGE {p.page_num}]\n{p.text}" for p in self.pages
        )

    def text_for_pages(self, page_nums: list[int]) -> str:
        page_set = set(page_nums)
        return "\n\n".join(
            f"[PAGE {p.page_num}]\n{p.text}"
            for p in self.pages if p.page_num in page_set
        )

    def search_pages(self, keywords: list[str]) -> dict[str, list[int]]:
        """Return {keyword: [page_nums]} for all keywords found."""
        hits: dict[str, list[int]] = {}
        for page in self.pages:
            lower = page.text.lower()
            for kw in keywords:
                if kw.lower() in lower:
                    hits.setdefault(kw, [])
                    if page.page_num not in hits[kw]:
                        hits[kw].append(page.page_num)
        return hits

    def get_pages_containing(
        self,
        keywords: list[str],
        window: int = 1,
        min_page: int = 6,
    ) -> list[int]:
        """Return sorted unique page numbers containing any keyword, +/- window pages.

        min_page skips cover/TOC pages (default 6) so TOC keyword hits don't
        pull in pages 1-3 for every section.
        """
        raw = set()
        for page in self.pages:
            if page.page_num < min_page:
                continue
            lower = page.text.lower()
            if any(kw.lower() in lower for kw in keywords):
                raw.add(page.page_num)

        expanded = set()
        max_page = self.total_pages
        for p in raw:
            for w in range(-window, window + 1):
                if 1 <= p + w <= max_page:
                    expanded.add(p + w)
        return sorted(expanded)


def extract_pdf(path: Path) -> ExtractedDocument:
    pages = []
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append(PagedText(page_num=i + 1, text=text))
    return ExtractedDocument(path=path, pages=pages)


def extract_document(path: Path) -> Optional[ExtractedDocument]:
    """Extract text from PDF or return None for unsupported types."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    # XLSX / other formats: not text-extractable here, handled separately
    return None
