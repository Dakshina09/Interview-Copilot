"""Extract plain text from an uploaded resume PDF."""

from io import BytesIO
from pypdf import PdfReader


def extract_text_from_pdf(uploaded_file) -> str:
    """uploaded_file: a Streamlit UploadedFile object."""
    reader = PdfReader(BytesIO(uploaded_file.read()))
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n".join(text_parts).strip()
