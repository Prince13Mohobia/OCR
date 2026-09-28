from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
import pytesseract
import base64
import io
import pymupdf as fitz
import os


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".pdf",
}

DEFAULT_OCR_LANGUAGE = (
    "eng+hin+mar+nep+san+rus+ukr+bel+srp+bos+hrv+spa+por+glg+dan+nor+swe+"
    "ara+fas+urd+chi_sim+chi_tra+jpn+kan+mal+tam+tel"
)


# ==================================================
# FASTAPI APP
# ==================================================

app = FastAPI(
    title="OCR API",
    description="OCR API for Base64 Images and PDF files",
    version="1.0.0"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# TESSERACT PATH
# ==================================================

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ==================================================
# REQUEST MODEL
# ==================================================

class OCRRequest(BaseModel):
    filename: str | None = None
    file: str


# ==================================================
# CLEAN OCR TEXT
# ==================================================

def clean_ocr_text(text: str):
    """
    Clean OCR output.

    Removes:
    - New lines
    - Empty lines
    - Extra spaces
    """

    # Split text into lines
    lines = text.splitlines()

    # Clean each line
    cleaned_lines = []

    for line in lines:

        # Remove extra spaces
        line = " ".join(line.split())

        # Ignore empty lines
        if line:
            cleaned_lines.append(line)

    # Convert everything into one clean string
    clean_text = " ".join(cleaned_lines)

    return clean_text


def detect_text_script_family(text: str):
    """Detect the dominant script family of the OCR text."""
    if not text:
        return None

    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return "devanagari"
    if any("\u0600" <= ch <= "\u06FF" for ch in text):
        return "arabic"
    if any("\u0400" <= ch <= "\u04FF" for ch in text):
        return "cyrillic"
    if any("\u4E00" <= ch <= "\u9FFF" or "\u3040" <= ch <= "\u30FF" for ch in text):
        return "east_asian"
    if any(("a" <= ch.lower() <= "z") or (ch.isascii() and ch.isalpha()) for ch in text):
        return "latin"
    return None


def get_language_script_family(language: str):
    """Return the script family for a requested language, if known."""
    family_map = {
        "hin": "devanagari",
        "mar": "devanagari",
        "mr": "devanagari",
        "nep": "devanagari",
        "san": "devanagari",
        "sa": "devanagari",
        "rus": "cyrillic",
        "ukr": "cyrillic",
        "bel": "cyrillic",
        "srp": "cyrillic",
        "bos": "cyrillic",
        "hrv": "latin",
        "spa": "latin",
        "por": "latin",
        "glg": "latin",
        "dan": "latin",
        "nor": "latin",
        "swe": "latin",
        "ara": "arabic",
        "fas": "arabic",
        "urd": "arabic",
        "chi_sim": "east_asian",
        "chi_tra": "east_asian",
        "jpn": "east_asian",
        "kan": "dravidian",
        "mal": "dravidian",
        "tam": "dravidian",
        "tel": "dravidian",
        "eng": "latin",
        "fra": "latin",
        "deu": "latin",
        "spa": "latin",
        "ita": "latin",
        "nld": "latin",
        "pol": "latin",
        "ron": "latin",
        "ces": "latin",
        "slk": "latin",
        "lav": "latin",
        "lit": "latin",
        "fin": "latin",
        "swe": "latin",
        "nor": "latin",
        "dan": "latin",
        "est": "latin",
        "tur": "latin",
        "hun": "latin",
        "slv": "latin",
        "sqi": "latin",
        "cat": "latin",
        "eus": "latin",
        "gle": "latin",
        "gla": "latin",
        "ceb": "latin",
        "fry": "latin",
        "hat": "latin",
        "glg": "latin",
        "epo": "latin",
        "afr": "latin",
        "deu_latf": "latin",
        "fil": "latin",
        "hye": "latin",
        "arm": "latin",
    }

    return family_map.get(language.lower())


def detect_best_language_from_text(text: str):
    """Best-effort language detection based on the actual script family in the OCR text."""
    family = detect_text_script_family(text)
    default_by_family = {
        "devanagari": "hin",
        "arabic": "ara",
        "cyrillic": "rus",
        "east_asian": "jpn",
        "dravidian": "tam",
        "latin": "eng",
    }
    return default_by_family.get(family, "eng")


def detect_language_from_script(image):
    """Detect a likely OCR language from Tesseract's script detection."""
    script_languages = {
        "latin": "eng",
        "devanagari": "hin",
        "cyrillic": "rus",
        "arabic": "ara",
        "han": "chi_sim",
        "japanese": "jpn",
        "hangul": "kor",
        "bengali": "ben",
        "tamil": "tam",
        "telugu": "tel",
        "malayalam": "mal",
        "kannada": "kan",
    }

    try:
        osd = pytesseract.image_to_osd(image)
        for line in osd.splitlines():
            if line.lower().startswith("script:"):
                script = line.split(":", 1)[1].strip().lower()
                return script_languages.get(script)
    except Exception:
        pass

    return None


def get_ocr_confidence(image, language: str):
    """Return average OCR confidence for the image in the requested language."""
    try:
        data = pytesseract.image_to_data(
            image,
            lang=language,
            output_type=pytesseract.Output.DICT,
            config='--psm 6'
        )
        conf_values = []
        for conf in data.get('conf', []):
            try:
                conf_val = int(float(conf))
                if conf_val >= 0:
                    conf_values.append(conf_val)
            except (ValueError, TypeError):
                continue
        if not conf_values:
            return 0
        return sum(conf_values) / len(conf_values)
    except Exception:
        return 0


def validate_ocr_language_result(text: str, requested_language: str, confidence: float | None = 100):
    """Reject OCR output when the script family or confidence does not match the requested language."""
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text detected in the uploaded file."
        )

    if confidence is not None and confidence < 35:
        raise HTTPException(
            status_code=400,
            detail="OCR confidence is too low. The uploaded file may be unclear or may not contain readable text."
        )

    requested = [lang.strip().lower() for lang in requested_language.split("+") if lang.strip()]
    if not requested:
        return

    text_family = detect_text_script_family(text)

    if len(requested) == 1:
        requested_family = get_language_script_family(requested[0])
        if requested_family and text_family and requested_family != text_family:
            raise HTTPException(
                status_code=400,
                detail=f"Requested OCR language is {requested[0].upper()}, but the document appears to use a different script family."
            )

    # This keeps same-script family languages compatible, while blocking different-script families.
    if len(requested) > 1:
        requested_families = {get_language_script_family(lang) for lang in requested if get_language_script_family(lang) is not None}
        if requested_families and text_family and text_family not in requested_families:
            raise HTTPException(
                status_code=400,
                detail="Requested OCR languages do not match the script family detected in the document."
            )


# ==================================================
# CHECK OCR LANGUAGE
# ==================================================

def validate_language(language: str):

    try:

        installed_languages = pytesseract.get_languages(
            config=""
        )

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Tesseract OCR is not installed or configured correctly."
        )

    requested_languages = language.split("+")

    missing_languages = [
        lang
        for lang in requested_languages
        if lang not in installed_languages
    ]

    if missing_languages:

        raise HTTPException(
            status_code=400,
            detail={
                "message": "Requested OCR language is not installed.",
                "requested": requested_languages,
                "missing": missing_languages,
                "available": installed_languages
            }
        )


# ==================================================
# DECODE BASE64
# ==================================================

def decode_file(base64_data: str):

    """
    Supports:

    Raw Base64:
        /9j/4AAQSkZJRg...

    Data URI:
        data:image/jpeg;base64,/9j/4AAQSkZJRg...
    """

    if not base64_data or not isinstance(base64_data, str):
        raise HTTPException(
            status_code=400,
            detail="Base64 file data is missing or invalid."
        )

    # Handle data URI
    if "," in base64_data:

        base64_data = base64_data.split(
            ",",
            1
        )[1]

    # Remove spaces and new lines from Base64
    base64_data = "".join(
        base64_data.split()
    )

    try:

        return base64.b64decode(
            base64_data,
            validate=True
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid Base64 file data."
        )


# ==================================================
# PROCESS IMAGE
# ==================================================

def process_image(
    file_bytes: bytes,
    language: str | None
):

    try:

        image = Image.open(
            io.BytesIO(file_bytes)
        )

        # Load image completely
        image.load()

    except UnidentifiedImageError:

        raise HTTPException(
            status_code=400,
            detail="Invalid or unsupported image."
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Unable to read image."
        )


    # ----------------------------------------------
    # OCR
    # ----------------------------------------------

    detected_language = language or detect_language_from_script(image) or DEFAULT_OCR_LANGUAGE
    try:
        raw_text = pytesseract.image_to_string(
            image,
            lang=detected_language
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="OCR failed while processing the image. Check Tesseract installation or the image content."
        )


    # ----------------------------------------------
    # Clean OCR text
    # ----------------------------------------------

    clean_text = clean_ocr_text(
        raw_text
    )

    if not language and detected_language == DEFAULT_OCR_LANGUAGE:
        detected_language = detect_best_language_from_text(clean_text)

    confidence = get_ocr_confidence(image, detected_language) if language else None
    validate_ocr_language_result(
        clean_text,
        detected_language,
        confidence=confidence
    )


    # ----------------------------------------------
    # Return result
    # ----------------------------------------------

    return {

        "file_type": "image",

        "format": image.format,

        "pages": 1,

        "text": clean_text,

        "total_characters": len(clean_text),

        "total_words": len(clean_text.split())
    }


# ==================================================
# PROCESS PDF
# ==================================================

def process_pdf(
    file_bytes: bytes,
    language: str | None
):

    try:

        pdf = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file."
        )


    all_text = []
    page_images = []
    detected_language = language


    # ----------------------------------------------
    # Process every PDF page
    # ----------------------------------------------

    for page in pdf:

        # ------------------------------------------
        # Convert PDF page to image
        # ------------------------------------------

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )


        image_bytes = pixmap.tobytes(
            "png"
        )


        image = Image.open(
            io.BytesIO(image_bytes)
        )
        page_images.append(image)


        # ------------------------------------------
        # OCR
        # ------------------------------------------

        page_language = detected_language or detect_language_from_script(image) or DEFAULT_OCR_LANGUAGE
        raw_text = pytesseract.image_to_string(
            image,
            lang=page_language
        )


        # ------------------------------------------
        # Clean OCR text
        # ------------------------------------------

        page_text = clean_ocr_text(
            raw_text
        )


        # ------------------------------------------
        # Store page text
        # ------------------------------------------

        if page_text:

            all_text.append(
                page_text
            )


    # ----------------------------------------------
    # Total pages
    # ----------------------------------------------

    total_pages = len(pdf)

    pdf.close()


    # ----------------------------------------------
    # Combine all pages
    # ----------------------------------------------

    combined_text = " ".join(
        all_text
    )

    if not language:
        detected_language = detect_best_language_from_text(combined_text)

    page_confidences = [get_ocr_confidence(image, detected_language) for image in page_images] if language else []
    sample_confidence = (
        sum(page_confidences) / len(page_confidences)
        if page_confidences
        else 0
    )

    validate_ocr_language_result(
        combined_text,
        detected_language,
        confidence=sample_confidence if language else None
    )


    # ----------------------------------------------
    # Return result
    # ----------------------------------------------

    return {

        "file_type": "pdf",

        "pages": total_pages,

        "text": combined_text,

        "total_characters": len(combined_text),

        "total_words": len(combined_text.split())
    }


def detect_and_process_file(file_bytes: bytes, language: str | None, filename: str | None = None):
    """Route file detection through the correct OCR processor."""
    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="File is empty."
        )

    file_ext = (filename or "").lower()
    lower_name = os.path.splitext(file_ext)[1]

    if file_bytes.startswith(b"%PDF") or lower_name == ".pdf":
        return process_pdf(file_bytes, language)

    if lower_name in SUPPORTED_EXTENSIONS or lower_name in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}:
        return process_image(file_bytes, language)

    # File signature fallback for common image types
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image.load()
        return process_image(file_bytes, language)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported inputs: images and PDF files. Received: {filename or 'unknown'}"
        )


# ==================================================
# OCR ENDPOINT
# ==================================================

@app.post("/ocr")
async def ocr(
    request: Request,
):

    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("multipart/form-data"):
        # Handle actual uploaded file from form-data
        form = await request.form()
        uploaded_file = form.get("uploaded_file") or form.get("file")

        if uploaded_file is None or not hasattr(uploaded_file, "read"):
            raise HTTPException(
                status_code=400,
                detail="A file upload is required in the 'uploaded_file' field."
            )

        file_bytes = await uploaded_file.read()
        resolved_filename = uploaded_file.filename or form.get("filename")
        result = detect_and_process_file(file_bytes, None, resolved_filename)
        return {
            "success": True,
            "filename": resolved_filename,
            **result,
        }

    if not content_type.startswith("application/json"):
        raise HTTPException(
            status_code=400,
            detail="Use application/json with a base64 file or multipart/form-data with an uploaded_file field."
        )

    # Decode Base64 payload
    try:
        payload = await request.json()
        ocr_request = OCRRequest.model_validate(payload)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload. Include a base64 'file' and optional 'filename'."
        )

    file_bytes = decode_file(ocr_request.file)

    result = detect_and_process_file(
        file_bytes,
        None,
        ocr_request.filename,
    )

    return {
        "success": True,
        "filename": ocr_request.filename,
        **result
    }


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/")
def home():

    return {

        "success": True,

        "message": "OCR API is running",

        "endpoint": "POST /ocr",

        "supported_input": [
            "Base64 JSON",
            "Multipart uploaded file"
        ],

        "supported_files": [
            "JPG",
            "JPEG",
            "PNG",
            "WEBP",
            "BMP",
            "TIFF",
            "TIF",
            "GIF",
            "PDF"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
