# Extracto OCR frontend

Static frontend for the FastAPI OCR service in `../ocr.py`.

## Local use

1. Start the API from the parent folder:

   ```powershell
   python -m uvicorn ocr:app --reload
   ```

2. Serve this folder with any static server, or open `index.html` directly.
3. Set the API endpoint in the Connection panel.

The UI supports:

- Multipart image and PDF uploads
- Raw Base64 and data URI JSON requests
- Automatic language/script detection
- OCR text preview
- Character, word, and page totals
- Raw API response inspection
- Copy and download actions
- API health check and readable error states

## Render deployment

Create a **Static Site** in Render with this repository/folder as the root and configure:

- **Build command:** leave empty
- **Publish directory:** `.`

After deploying the API, replace the value in `config.js` with the public API base URL. The endpoint is display-only in the UI. On the API service, set `CORS_ORIGINS` to the frontend URL, for example:

```text
https://your-ocr-frontend.onrender.com
```
