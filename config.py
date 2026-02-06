import os
import platform

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

    # .doc files require Microsoft Word via COM — only available on Windows
    if platform.system() == "Windows":
        ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}
    else:
        ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
