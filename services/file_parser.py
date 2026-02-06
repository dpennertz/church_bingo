import os

from pypdf import PdfReader
from docx import Document


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def extract_text(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return _extract_from_pdf(filepath)
    elif ext == ".docx":
        return _extract_from_docx(filepath)
    elif ext == ".doc":
        return _extract_from_doc(filepath)
    elif ext == ".txt":
        return _extract_from_txt(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_from_pdf(filepath):
    reader = PdfReader(filepath)
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_from_docx(filepath):
    doc = Document(filepath)
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())


def _extract_from_doc(filepath):
    """Convert .doc to .docx using MS Word via COM, then extract text.

    Only works on Windows with Microsoft Word installed.
    On Linux/cloud deployments, raises a friendly error.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        raise ValueError(
            "Sorry, .doc files are not supported in the cloud-hosted version. "
            "Please save your file as .docx, .pdf, or .txt and try again."
        )

    docx_path = filepath + ".docx"
    abs_path = os.path.abspath(filepath)
    abs_docx_path = os.path.abspath(docx_path)

    try:
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(abs_path)
        # SaveAs2 format 16 = wdFormatDocumentDefault (.docx)
        doc.SaveAs2(abs_docx_path, FileFormat=16)
        doc.Close()
        word.Quit()

        return _extract_from_docx(docx_path)
    except Exception as e:
        raise ValueError(
            f"Could not convert .doc file. Make sure Microsoft Word is installed. Error: {e}"
        )
    finally:
        pythoncom.CoUninitialize()
        if os.path.exists(docx_path):
            os.remove(docx_path)


def _extract_from_txt(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()
