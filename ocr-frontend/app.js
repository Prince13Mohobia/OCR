const state = { mode: 'file', file: null, result: null, previewUrl: null };
const $ = (id) => document.getElementById(id);

const apiUrl = $('apiUrl');
const fileInput = $('fileInput');
const dropzone = $('dropzone');
const runButton = $('runButton');

apiUrl.value = `${window.EXTRACTO_API_URL || 'http://127.0.0.1:8000'}/ocr`;

function setStatus(label, online = null) {
  $('statusText').textContent = label;
  $('statusDot').className = `status-dot ${online === true ? 'online' : online === false ? 'offline' : ''}`;
}

function setView(view) {
  ['emptyResult', 'loadingResult', 'errorResult', 'ocrOutput', 'resultFooter'].forEach((id) => $(id).classList.add('hidden'));
  if (view) $(view).classList.remove('hidden');
}

function apiRoot() {
  return apiUrl.value.trim().replace(/\/ocr\/?$/, '').replace(/\/$/, '');
}

function markApiOnline() {
  const healthButton = $('healthButton');
  setStatus('API online', true);
  healthButton.classList.remove('checking', 'offline');
  healthButton.classList.add('online');
  healthButton.innerHTML = '<span>✓</span> API online';
}

function markApiOffline() {
  const healthButton = $('healthButton');
  setStatus('API offline', false);
  healthButton.classList.remove('checking', 'online');
  healthButton.classList.add('offline');
  healthButton.innerHTML = '<span>!</span> API offline';
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function selectFile(file) {
  if (!file) return;
  state.file = file;
  $('fileName').textContent = file.name;
  $('fileSize').textContent = formatSize(file.size);
  $('fileBadge').textContent = file.type === 'application/pdf' ? 'PDF' : 'IMG';
  $('selectedFile').classList.remove('hidden');
  $('dropTitle').textContent = 'File selected';
  $('dropSubtext').textContent = 'Choose another file to replace it';
  $('previewWrap').classList.add('hidden');
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  if (file.type.startsWith('image/')) {
    state.previewUrl = URL.createObjectURL(file);
    $('previewImage').src = state.previewUrl;
    $('previewWrap').classList.remove('hidden');
    $('previewImage').classList.remove('hidden');
    $('previewWrap').querySelector('.pdf-preview').classList.add('hidden');
  } else {
    $('previewWrap').classList.remove('hidden');
    $('previewImage').classList.add('hidden');
    $('previewWrap').querySelector('.pdf-preview').classList.remove('hidden');
  }
}

function clearFile() {
  state.file = null;
  fileInput.value = '';
  $('selectedFile').classList.add('hidden');
  $('previewWrap').classList.add('hidden');
  $('dropTitle').textContent = 'Drop an image or PDF';
  $('dropSubtext').textContent = 'or choose a file from your device';
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = null;
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll('.segment').forEach((button) => button.classList.toggle('active', button.dataset.mode === mode));
  $('fileMode').classList.toggle('hidden', mode !== 'file');
  $('base64Mode').classList.toggle('hidden', mode !== 'base64');
  $('requestNote').textContent = mode === 'file' ? 'Multipart upload · language detected automatically' : 'application/json · language detected automatically';
  $('bodyLabel').textContent = mode === 'file' ? 'multipart/form-data' : 'application/json';
  $('bodyPreview').textContent = mode === 'file' ? 'uploaded_file: File' : '{\n  "filename": "document.png",\n  "file": "<base64>"\n}';
}

async function fileAsDataUri(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function readResponse(response) {
  const data = await response.json().catch(() => ({ detail: 'The API returned an invalid response.' }));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    throw new Error(detail || `Request failed with status ${response.status}.`);
  }
  return data;
}

function displayResult(data, filename) {
  state.result = data;
  setView('ocrOutput');
  $('ocrOutput').textContent = data.text || '';
  $('resultFile').textContent = filename || 'document';
  $('resultPages').textContent = `${data.pages || 1} ${(data.pages || 1) === 1 ? 'page' : 'pages'}`;
  $('charactersMetric').textContent = (data.total_characters ?? data.text?.length ?? 0).toLocaleString();
  $('wordsMetric').textContent = (data.total_words ?? data.text?.trim().split(/\s+/).filter(Boolean).length ?? 0).toLocaleString();
  $('pagesMetric').textContent = (data.pages || 1).toLocaleString();
  $('metricsRow').classList.remove('hidden');
  $('resultActions').classList.remove('hidden');
  $('resultFooter').classList.remove('hidden');
  $('footerStatus').textContent = 'OCR complete';
}

async function runOcr() {
  if (!apiRoot()) return showError('Missing API endpoint', 'Enter the URL where your OCR API is running.');
  runButton.disabled = true;
  $('runIcon').textContent = '◌';
  $('runLabel').textContent = 'Reading...';
  setView('loadingResult');
  $('resultActions').classList.add('hidden');
  $('metricsRow').classList.add('hidden');
  let apiResponded = false;
  try {
    let response;
    let filename = '';
    if (state.mode === 'file') {
      if (!state.file) throw new Error('Choose an image or PDF before running OCR.');
      const form = new FormData();
      form.append('uploaded_file', state.file);
      filename = state.file.name;
      response = await fetch(`${apiRoot()}/ocr`, { method: 'POST', body: form });
    } else {
      const base64 = $('base64Input').value.trim();
      if (!base64) throw new Error('Paste Base64 file data before running OCR.');
      filename = $('filenameInput').value.trim() || 'base64-document';
      response = await fetch(`${apiRoot()}/ocr`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename, file: base64 }) });
    }
    apiResponded = true;
    markApiOnline();
    const data = await readResponse(response);
    displayResult(data, data.filename || filename);
  } catch (error) {
    if (!apiResponded) markApiOffline();
    showError('OCR request failed', error.message || 'Could not reach the API.');
  } finally {
    runButton.disabled = false;
    $('runIcon').textContent = '◎';
    $('runLabel').textContent = 'Run OCR';
  }
}

function showError(title, message) {
  setView('errorResult');
  $('errorTitle').textContent = title;
  $('errorMessage').textContent = message;
  $('footerStatus').textContent = 'Request failed';
}

async function checkHealth() {
  const healthButton = $('healthButton');
  healthButton.disabled = true;
  healthButton.classList.add('checking');
  healthButton.classList.remove('online', 'offline');
  healthButton.innerHTML = '<span>◎</span> Checking...';
  setStatus('Checking...', null);
  try {
    const response = await fetch(`${apiRoot()}/?health_check=${Date.now()}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'API unavailable');
    markApiOnline();
    $('footerStatus').textContent = data.message || 'API online';
  } catch (error) {
    markApiOffline();
    $('footerStatus').textContent = 'Could not connect';
  } finally {
    healthButton.disabled = false;
    healthButton.classList.remove('checking');
  }
}

fileInput.addEventListener('change', () => selectFile(fileInput.files[0]));
$('removeFile').addEventListener('click', clearFile);
$('copyEndpoint').addEventListener('click', async () => { await navigator.clipboard.writeText(`${apiRoot()}/ocr`); $('copyEndpoint').textContent = 'Copied'; setTimeout(() => $('copyEndpoint').textContent = 'Copy', 1200); });
$('healthButton').addEventListener('click', checkHealth);
runButton.addEventListener('click', runOcr);
document.querySelectorAll('.segment').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mode)));

dropzone.addEventListener('dragover', (event) => { event.preventDefault(); dropzone.classList.add('dragging'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragging'));
dropzone.addEventListener('drop', (event) => { event.preventDefault(); dropzone.classList.remove('dragging'); selectFile(event.dataTransfer.files[0]); });
$('copyButton').addEventListener('click', async () => { await navigator.clipboard.writeText(state.result?.text || ''); $('copyButton').textContent = 'Copied'; setTimeout(() => $('copyButton').textContent = 'Copy', 1200); });
$('downloadButton').addEventListener('click', () => { const blob = new Blob([state.result?.text || ''], { type: 'text/plain;charset=utf-8' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${state.result?.filename || 'ocr-result'}.txt`; link.click(); URL.revokeObjectURL(link.href); });
document.addEventListener('keydown', (event) => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') runOcr(); });
