# Extracto OCR

OCR application with a FastAPI backend and a static browser frontend. The API accepts image and PDF uploads and returns extracted text.

## Run locally

Install the Python dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

Install Tesseract OCR separately. On Windows, install the Tesseract application; on Render, the API build installs the `tesseract-ocr` package.

Start the API:

```powershell
python -m uvicorn ocr:app --reload
```

The API is available at `http://127.0.0.1:8000`. Open `ocr-frontend/index.html` in a browser, or serve the `ocr-frontend` directory with a static file server. The frontend's production API base URL is configured in `ocr-frontend/config.js`.

## API

Health check:

```text
GET /
```

OCR accepts a multipart upload in the `uploaded_file` field:

```powershell
curl.exe --location "http://127.0.0.1:8000/ocr" `
	--form "uploaded_file=@C:\path\to\document.png"
```

It also accepts JSON containing a base64-encoded file and an optional filename.

## Deploy on Render

The repository includes `render.yaml` to define both Render services. Use **New > Blueprint** in Render and connect this GitHub repository. The Blueprint defines:

- **Web Service** `extracto-ocr-api` from the repository root. It installs Python dependencies and Tesseract, then starts with `python ocr.py`.
- **Static Site** `extracto-ocr-frontend` from `ocr-frontend`, published from `.`.

The frontend API URL is set in `ocr-frontend/config.js`. The current production API URL is `https://ocr-0sz5.onrender.com`; the API's `CORS_ORIGINS` setting in `render.yaml` allows the Blueprint frontend URL `https://extracto-ocr-frontend.onrender.com`.

If the API is already deployed separately, create only the Static Site using the settings above and keep its domain aligned with the API's `CORS_ORIGINS` value. Deploy the frontend after changes to the repository are pushed.