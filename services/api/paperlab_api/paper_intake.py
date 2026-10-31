"""Bounded paper intake. Arbitrary URLs and redirects cannot reach local services."""

import hashlib
import io
import re
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import HTTPException
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_HOSTS = {"arxiv.org", "export.arxiv.org", "openaccess.thecvf.com", "openreview.net"}


def pages_from_pdf(data: bytes) -> list[dict]:
    if len(data) > MAX_BYTES or not data.startswith(b"%PDF"):
        raise HTTPException(422, "Upload a PDF no larger than 10 MB.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > 80:
            raise ValueError("Encrypted or oversized paper")
        pages, total = [], 0
        for number, page in enumerate(reader.pages, 1):
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > 5 * 1024 * 1024:
                raise ValueError("Oversized page")
            content = (page.extract_text() or "").strip()
            total += len(content)
            if total > 200000:
                raise ValueError("Too much extracted text")
            pages.append({"page": number, "text": content})
        if sum(len(p["text"]) for p in pages) < 100:
            raise ValueError("No readable text")
        return pages
    except Exception as exc:
        raise HTTPException(
            422, "Could not read this PDF. Use a text-based PDF up to 80 pages, or paste its text."
        ) from exc


def paper_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise HTTPException(422, "Invalid paper URL. Upload or paste the paper instead.") from exc
    if (
        parts.scheme != "https"
        or parts.hostname not in ALLOWED_HOSTS
        or parts.username
        or parts.password
        or port not in (None, 443)
    ):
        raise HTTPException(
            422,
            "URL import supports HTTPS arXiv, CVF and OpenReview PDFs. "
            "Otherwise upload or paste the paper.",
        )
    path = parts.path
    if parts.hostname in {"arxiv.org", "export.arxiv.org"}:
        path = path.replace("/abs/", "/pdf/", 1)
    if parts.hostname == "openaccess.thecvf.com" and path.endswith(".html"):
        path = path.replace("/html/", "/papers/").removesuffix(".html") + ".pdf"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def fetch_pdf(value: str) -> list[dict]:
    url = paper_url(value)
    try:
        with httpx.Client(timeout=40, follow_redirects=False, trust_env=False) as client:
            for _ in range(4):
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = paper_url(
                            str(response.url.join(response.headers.get("location", "")))
                        )
                        continue
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_BYTES:
                            raise HTTPException(422, "Paper exceeds the 10 MB import limit.")
                    return pages_from_pdf(bytes(content))
    except httpx.HTTPError as exc:
        raise HTTPException(
            422, "Paper download failed. Upload the PDF or paste the paper text."
        ) from exc
    raise HTTPException(422, "Too many redirects. Upload the PDF instead.")


def digest(pages: list[dict]) -> str:
    return hashlib.sha256("\n".join(p["text"] for p in pages).encode()).hexdigest()


def source_context(pages: list[dict], query: str) -> list[dict]:
    words = set(re.findall(r"[a-z]{4,}", query.lower()))
    ranked = sorted(
        pages, key=lambda p: (-sum(p["text"].lower().count(word) for word in words), p["page"])
    )
    # Keep the abstract and the strongest matching method/result pages. State coverage explicitly.
    chosen, remaining = {}, 22000
    for page in pages[:1] + ranked:
        if page["page"] in chosen or remaining < 500:
            continue
        content = page["text"][: min(5000, remaining)]
        chosen[page["page"]] = {"page": page["page"], "text": content}
        remaining -= len(content)
    return sorted(chosen.values(), key=lambda p: p["page"])
