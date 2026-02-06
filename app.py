import json
import os
import random
import time
import uuid

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from config import Config
from services import file_parser, word_extractor, board_generator, pdf_renderer
from services.pdf_renderer import format_date
from services.settings_store import load_settings, save_settings

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# --- Server-side session store (file-backed so it survives restarts) ---
_SESSION_DIR = os.path.join(os.path.dirname(__file__), "uploads", ".sessions")
os.makedirs(_SESSION_DIR, exist_ok=True)


def _session_path(sid):
    """Return the file path for a given session ID."""
    return os.path.join(_SESSION_DIR, f"{sid}.json")


def get_session_data():
    sid = session.get("sid")

    # Try to load existing session from disk
    if sid:
        path = _session_path(sid)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    store = json.load(f)
                store["timestamp"] = time.time()
                _save_session(sid, store)
                return store["data"]
            except (json.JSONDecodeError, OSError):
                pass  # Corrupt file, create fresh session

    # Create new session
    sid = str(uuid.uuid4())
    session["sid"] = sid
    store = {"data": {}, "timestamp": time.time()}
    _save_session(sid, store)
    return store["data"]


def _save_session(sid, store):
    """Write session data to disk."""
    try:
        with open(_session_path(sid), "w", encoding="utf-8") as f:
            json.dump(store, f)
    except OSError:
        pass


def save_session_data(data):
    """Persist current session data to disk. Call after modifying data."""
    sid = session.get("sid")
    if sid:
        store = {"data": data, "timestamp": time.time()}
        _save_session(sid, store)


def cleanup_sessions(max_age=3600):
    now = time.time()
    try:
        for fname in os.listdir(_SESSION_DIR):
            fpath = os.path.join(_SESSION_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    store = json.load(f)
                if now - store.get("timestamp", 0) > max_age:
                    os.remove(fpath)
            except (json.JSONDecodeError, OSError):
                os.remove(fpath)
    except OSError:
        pass


# --- Routes ---


@app.route("/")
def index():
    cleanup_sessions()
    return render_template("index.html")


# --- BINGO: Step 1 - Upload ---


@app.route("/bingo/upload", methods=["GET", "POST"])
def bingo_upload():
    if request.method == "GET":
        exts = Config.ALLOWED_EXTENSIONS
        accept_str = ",".join(f".{e}" for e in sorted(exts))
        # Build human-readable format list (e.g. "PDF, Word (.docx), or Text (.txt)")
        labels = []
        if "pdf" in exts:
            labels.append("PDF")
        if "doc" in exts and "docx" in exts:
            labels.append("Word (.doc/.docx)")
        elif "docx" in exts:
            labels.append("Word (.docx)")
        if "txt" in exts:
            labels.append("Text (.txt)")
        format_text = ", ".join(labels[:-1]) + ", or " + labels[-1] if len(labels) > 1 else labels[0]
        return render_template("bingo/upload.html", step=1, accept_str=accept_str, format_text=format_text)

    # Handle file upload
    if "bulletin" not in request.files:
        flash("No file selected.", "danger")
        return redirect(url_for("bingo_upload"))

    file = request.files["bulletin"]
    if file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("bingo_upload"))

    if not file_parser.allowed_file(file.filename, Config.ALLOWED_EXTENSIONS):
        ext_list = ", ".join(f".{e}" for e in sorted(Config.ALLOWED_EXTENSIONS))
        flash(f"Unsupported file type. Please upload one of: {ext_list}", "danger")
        return redirect(url_for("bingo_upload"))

    # Save file temporarily
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file.save(filepath)

    try:
        # Extract text
        text = file_parser.extract_text(filepath)
        if not text or len(text.strip()) < 20:
            flash("Could not extract enough text from the file. Try a different file or enter words manually.", "warning")
            return redirect(url_for("bingo_upload"))

        # Extract words via Claude
        words = word_extractor.extract_words(text)

        # Compute word frequencies from the full bulletin text
        word_counts = word_extractor.compute_word_frequencies(text, words)

        data = get_session_data()
        data["extracted_text"] = text[:2000]  # Store a snippet for reference
        data["full_text"] = text  # Store full text for frequency recalculation
        data["suggested_words"] = words
        data["selected_words"] = words[:]  # Copy - all selected by default
        data["word_counts"] = word_counts
        save_session_data(data)

        flash(f"Found {len(words)} words from your bulletin!", "success")
        return redirect(url_for("bingo_words"))

    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("bingo_upload"))
    except Exception as e:
        flash(f"Error processing bulletin: {str(e)}", "danger")
        return redirect(url_for("bingo_upload"))
    finally:
        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route("/bingo/manual-words", methods=["POST"])
def bingo_manual_words():
    text = request.form.get("manual_text", "").strip()
    if not text:
        flash("Please enter some words or text.", "warning")
        return redirect(url_for("bingo_upload"))

    # Check if it looks like a word list (comma or newline separated)
    if "," in text or "\n" in text:
        # Parse as word list
        raw_words = [w.strip().lower() for w in text.replace("\n", ",").split(",")]
        words = [w for w in raw_words if w and len(w) >= 3]
    else:
        # Treat as bulletin text, send to Claude
        try:
            words = word_extractor.extract_words(text)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("bingo_upload"))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("bingo_upload"))

    if len(words) < 5:
        flash("Not enough words found. Please provide more text or words.", "warning")
        return redirect(url_for("bingo_upload"))

    # Compute word frequencies from the input text
    word_counts = word_extractor.compute_word_frequencies(text, words)

    data = get_session_data()
    data["suggested_words"] = words
    data["selected_words"] = words[:]
    data["full_text"] = text
    data["word_counts"] = word_counts
    save_session_data(data)

    flash(f"Added {len(words)} words!", "success")
    return redirect(url_for("bingo_words"))


# --- BINGO: Step 2 - Words ---


@app.route("/bingo/words", methods=["GET", "POST"])
def bingo_words():
    data = get_session_data()

    if "suggested_words" not in data:
        flash("Please upload a bulletin first.", "warning")
        return redirect(url_for("bingo_upload"))

    if request.method == "GET":
        words = data.get("selected_words", data.get("suggested_words", []))
        word_counts = data.get("word_counts", {})
        return render_template("bingo/words.html", step=2, words=words, word_counts=word_counts)

    # POST - save selected words
    selected_json = request.form.get("selected_words", "[]")
    try:
        selected = json.loads(selected_json)
    except json.JSONDecodeError:
        selected = []

    if len(selected) < 16:
        flash(f"You need at least 16 words. Currently have {len(selected)}.", "warning")
        word_counts = data.get("word_counts", {})
        return render_template("bingo/words.html", step=2, words=data.get("selected_words", []), word_counts=word_counts)

    data["selected_words"] = selected

    # Track which words were manually added so they always appear on cards
    custom_json = request.form.get("custom_words", "[]")
    try:
        data["custom_words"] = json.loads(custom_json)
    except json.JSONDecodeError:
        data["custom_words"] = []

    save_session_data(data)
    return redirect(url_for("bingo_configure"))


# --- BINGO: Step 3 - Configure ---


@app.route("/bingo/configure", methods=["GET", "POST"])
def bingo_configure():
    data = get_session_data()

    if "selected_words" not in data:
        flash("Please complete the previous steps first.", "warning")
        return redirect(url_for("bingo_upload"))

    if request.method == "GET":
        return render_template(
            "bingo/configure.html",
            step=3,
            word_count=len(data.get("selected_words", [])),
            board_size=data.get("board_size", 5),
            card_count=data.get("card_count", 10),
            word_mode=data.get("word_mode", "same_shuffled"),
        )

    # POST - save configuration
    board_size = int(request.form.get("board_size", 5))
    card_count = int(request.form.get("card_count", 10))
    word_mode = request.form.get("word_mode", "same_shuffled")

    # Clamp values
    board_size = 5 if board_size not in (4, 5) else board_size
    card_count = max(1, min(50, card_count))

    # Validate word count
    words = data.get("selected_words", [])
    valid, msg = board_generator.validate_word_count(words, board_size, card_count, word_mode)
    if not valid:
        flash(msg, "warning")
        return render_template(
            "bingo/configure.html",
            step=3,
            word_count=len(words),
            board_size=board_size,
            card_count=card_count,
            word_mode=word_mode,
        )

    data["board_size"] = board_size
    data["card_count"] = card_count
    data["word_mode"] = word_mode
    save_session_data(data)

    return redirect(url_for("bingo_customize"))


# --- BINGO: Step 4 - Customize ---


@app.route("/bingo/customize", methods=["GET", "POST"])
def bingo_customize():
    data = get_session_data()
    saved = load_settings()

    if "board_size" not in data:
        flash("Please complete the previous steps first.", "warning")
        return redirect(url_for("bingo_upload"))

    if request.method == "GET":
        # Use session values if set, otherwise fall back to saved settings
        return render_template(
            "bingo/customize.html",
            step=4,
            title=data.get("title", saved.get("title", "Sermon BINGO")),
            church_name=data.get("church_name", saved.get("church_name", "")),
            header_color=data.get("header_color", saved.get("header_color", "#2c3e50")),
            border_color=data.get("border_color", saved.get("border_color", "#34495e")),
            card_date=data.get("card_date", ""),
            card_occasion=data.get("card_occasion", ""),
            footer_message=data.get("footer_message", saved.get("footer_message", "")),
            has_logo=data.get("logo_path") is not None,
        )

    # POST - save customization
    data["title"] = request.form.get("title", "Sermon BINGO").strip() or "Sermon BINGO"
    data["church_name"] = request.form.get("church_name", "").strip()
    data["header_color"] = request.form.get("header_color", "#2c3e50")
    data["border_color"] = request.form.get("border_color", "#34495e")
    data["card_date"] = request.form.get("card_date", "").strip()
    data["card_occasion"] = request.form.get("card_occasion", "").strip()
    data["footer_message"] = request.form.get("footer_message", "").strip()

    # Persist settings to disk so they carry over between sessions
    save_settings(data)

    # Handle logo removal
    if request.form.get("remove_logo"):
        if data.get("logo_path") and os.path.exists(data["logo_path"]):
            os.remove(data["logo_path"])
        data["logo_path"] = None

    # Handle logo upload
    if "logo" in request.files:
        logo_file = request.files["logo"]
        if logo_file.filename:
            logo_name = secure_filename(logo_file.filename)
            logo_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid.uuid4().hex}_{logo_name}")
            logo_file.save(logo_path)
            # Remove old logo if exists
            if data.get("logo_path") and os.path.exists(data["logo_path"]):
                os.remove(data["logo_path"])
            data["logo_path"] = logo_path

    save_session_data(data)
    return redirect(url_for("bingo_preview"))


# --- BINGO: Step 5 - Preview & Download ---


@app.route("/bingo/preview")
def bingo_preview():
    data = get_session_data()

    if "selected_words" not in data or "board_size" not in data:
        flash("Please complete the previous steps first.", "warning")
        return redirect(url_for("bingo_upload"))

    words = data["selected_words"]
    board_size = data["board_size"]

    # Generate a single preview board
    preview_boards = board_generator.generate_boards(
        words, board_size, 1, data.get("word_mode", "same_shuffled"),
        custom_words=data.get("custom_words", []),
    )
    preview_board = preview_boards[0]

    raw_date = data.get("card_date", "")
    return render_template(
        "bingo/preview.html",
        step=5,
        preview_board=preview_board,
        board_size=board_size,
        card_count=data.get("card_count", 10),
        word_mode=data.get("word_mode", "same_shuffled"),
        words=words,
        title=data.get("title", "Sermon BINGO"),
        church_name=data.get("church_name", ""),
        header_color=data.get("header_color", "#2c3e50"),
        border_color=data.get("border_color", "#34495e"),
        card_date=format_date(raw_date),
        card_occasion=data.get("card_occasion", ""),
        footer_message=data.get("footer_message", ""),
    )


@app.route("/bingo/generate")
def bingo_generate():
    data = get_session_data()

    if "selected_words" not in data or "board_size" not in data:
        flash("Please complete the previous steps first.", "warning")
        return redirect(url_for("bingo_upload"))

    words = data["selected_words"]
    board_size = data["board_size"]
    card_count = data.get("card_count", 10)
    word_mode = data.get("word_mode", "same_shuffled")

    # Generate all boards
    boards = board_generator.generate_boards(
        words, board_size, card_count, word_mode,
        custom_words=data.get("custom_words", []),
    )

    # Generate PDF
    pdf_buffer = pdf_renderer.generate_pdf(
        boards=boards,
        title=data.get("title", "Sermon BINGO"),
        church_name=data.get("church_name", ""),
        logo_path=data.get("logo_path"),
        header_color=data.get("header_color", "#2c3e50"),
        border_color=data.get("border_color", "#34495e"),
        board_size=board_size,
        card_date=data.get("card_date", ""),
        card_occasion=data.get("card_occasion", ""),
        footer_message=data.get("footer_message", ""),
    )

    # Create a safe filename
    safe_title = "".join(c for c in data.get("title", "Sermon_BINGO") if c.isalnum() or c in " _-").strip()
    safe_title = safe_title.replace(" ", "_") or "Sermon_BINGO"

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_title}_{card_count}_cards.pdf",
    )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    app.run(debug=debug, port=5000)
