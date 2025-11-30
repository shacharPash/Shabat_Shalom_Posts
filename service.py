from typing import Any, Dict
from fastapi import FastAPI, Body
from fastapi.responses import Response, HTMLResponse

from api.poster import build_poster_from_payload


app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def index():
    # UI מעוצב ליצירת פוסטר שבת
    return """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>יוצר פוסטר לשבת ✡</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {
      box-sizing: border-box;
    }
    body {
      font-family: 'Heebo', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #3949ab 100%);
      margin: 0;
      padding: 20px;
      min-height: 100vh;
    }
    .container {
      background: #ffffff;
      margin: 0 auto;
      padding: 32px;
      border-radius: 24px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      max-width: 520px;
      width: 100%;
    }
    .header {
      text-align: center;
      margin-bottom: 28px;
    }
    .logo {
      font-size: 48px;
      margin-bottom: 8px;
    }
    h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 700;
      color: #1a237e;
    }
    .subtitle {
      color: #5c6bc0;
      font-size: 14px;
      margin-top: 6px;
    }
    .form-group {
      margin-bottom: 20px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      color: #1a237e;
      font-size: 15px;
    }
    label .optional {
      font-weight: 400;
      color: #9e9e9e;
      font-size: 13px;
    }
    input[type="text"], textarea {
      width: 100%;
      padding: 14px 16px;
      border-radius: 12px;
      border: 2px solid #e8eaf6;
      font-size: 15px;
      font-family: inherit;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
      background: #fafafa;
    }
    input[type="text"]:focus, textarea:focus {
      outline: none;
      border-color: #5c6bc0;
      box-shadow: 0 0 0 4px rgba(92, 107, 192, 0.15);
      background: #fff;
    }
    textarea {
      resize: vertical;
      min-height: 80px;
    }
    .hint {
      font-size: 12px;
      color: #9e9e9e;
      margin-top: 6px;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .hint::before {
      content: "💡";
      font-size: 11px;
    }
    .btn-generate {
      margin-top: 8px;
      width: 100%;
      padding: 16px 24px;
      border-radius: 14px;
      border: none;
      font-size: 18px;
      font-weight: 700;
      cursor: pointer;
      background: linear-gradient(135deg, #ffd54f 0%, #ffb300 100%);
      color: #1a237e;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      box-shadow: 0 4px 15px rgba(255, 179, 0, 0.4);
    }
    .btn-generate:disabled {
      opacity: 0.7;
      cursor: not-allowed;
      transform: none;
    }
    .btn-generate:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(255, 179, 0, 0.5);
    }
    .btn-generate:active:not(:disabled) {
      transform: translateY(0);
    }
    .spinner {
      width: 20px;
      height: 20px;
      border: 3px solid #1a237e;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      display: none;
    }
    .btn-generate.loading .spinner {
      display: block;
    }
    .btn-generate.loading .btn-text {
      display: none;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .status {
      margin-top: 16px;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 14px;
      text-align: center;
      display: none;
    }
    .status.show {
      display: block;
    }
    .status.error {
      background: #ffebee;
      color: #c62828;
      border: 1px solid #ffcdd2;
    }
    .status.success {
      background: #e8f5e9;
      color: #2e7d32;
      border: 1px solid #c8e6c9;
    }
    .status.loading {
      background: #e8eaf6;
      color: #3949ab;
      border: 1px solid #c5cae9;
    }
    .preview {
      margin-top: 24px;
      display: none;
      animation: fadeIn 0.4s ease;
    }
    .preview.show {
      display: block;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .preview-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }
    .preview-title {
      font-size: 18px;
      font-weight: 600;
      color: #1a237e;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .btn-download {
      padding: 10px 20px;
      border-radius: 10px;
      border: 2px solid #1a237e;
      background: transparent;
      color: #1a237e;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: inherit;
    }
    .btn-download:hover {
      background: #1a237e;
      color: #fff;
    }
    .preview-image-container {
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 10px 40px rgba(0,0,0,0.15);
    }
    .preview img {
      width: 100%;
      display: block;
    }
    .footer {
      margin-top: 28px;
      text-align: center;
      color: #9e9e9e;
      font-size: 12px;
    }
    .footer a {
      color: #5c6bc0;
      text-decoration: none;
    }
    .footer a:hover {
      text-decoration: underline;
    }
    .divider {
      height: 1px;
      background: linear-gradient(90deg, transparent, #e0e0e0, transparent);
      margin: 24px 0;
    }
    @media (max-width: 480px) {
      body {
        padding: 12px;
      }
      .container {
        padding: 24px 20px;
        border-radius: 20px;
      }
      h1 {
        font-size: 24px;
      }
      .logo {
        font-size: 40px;
      }
      .preview-header {
        flex-direction: column;
        gap: 12px;
        align-items: stretch;
      }
      .btn-download {
        justify-content: center;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo">🕯️✡️🕯️</div>
      <h1>יוצר פוסטר לשבת</h1>
      <div class="subtitle">צרו פוסטר יפה עם זמני הדלקת נרות</div>
    </div>

    <div class="form-group">
      <label for="imageUrl">קישור לתמונת רקע <span class="optional">(לא חובה)</span></label>
      <input id="imageUrl" type="text" placeholder="https://example.com/image.jpg" />
      <div class="hint">השאירו ריק לשימוש בתמונת ברירת המחדל</div>
    </div>

    <div class="form-group">
      <label for="message">ברכה לפוסטר <span class="optional">(לא חובה)</span></label>
      <textarea id="message" placeholder="למשל: לחיי שמחות קטנות וגדולות"></textarea>
    </div>

    <div class="form-group">
      <label for="neshama">לעילוי נשמת <span class="optional">(לא חובה)</span></label>
      <input id="neshama" type="text" placeholder="למשל: אורי בורנשטיין הי״ד" />
    </div>

    <button id="generateBtn" class="btn-generate">
      <span class="btn-text">✨ צור פוסטר</span>
      <div class="spinner"></div>
    </button>

    <div id="status" class="status"></div>

    <div class="preview" id="preview">
      <div class="divider"></div>
      <div class="preview-header">
        <h3 class="preview-title">🎉 הפוסטר מוכן!</h3>
        <button id="downloadBtn" class="btn-download">
          <span>⬇️</span> הורד תמונה
        </button>
      </div>
      <div class="preview-image-container">
        <img id="posterImage" alt="פוסטר שבת שנוצר" />
      </div>
    </div>

    <div class="footer">
      לזכר אורי בורנשטיין הי״ד 🕯️
    </div>
  </div>

  <script>
    const btn = document.getElementById("generateBtn");
    const downloadBtn = document.getElementById("downloadBtn");
    const statusEl = document.getElementById("status");
    const previewEl = document.getElementById("preview");
    const posterImg = document.getElementById("posterImage");
    let currentBlobUrl = null;

    btn.addEventListener("click", async () => {
      const imageUrl = document.getElementById("imageUrl").value.trim();
      const message = document.getElementById("message").value.trim();
      const leiluyNeshama = document.getElementById("neshama").value.trim();

      // Show loading state
      statusEl.textContent = "⏳ יוצר את הפוסטר שלך...";
      statusEl.className = "status loading show";
      btn.classList.add("loading");
      btn.disabled = true;
      previewEl.classList.remove("show");

      const payload = {};
      if (imageUrl) payload.imageUrl = imageUrl;
      if (message) payload.message = message;
      if (leiluyNeshama) payload.leiluyNeshama = leiluyNeshama;

      try {
        const resp = await fetch("/poster", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) {
          const text = await resp.text();
          throw new Error("שגיאה מהשרת: " + resp.status);
        }

        const blob = await resp.blob();

        // Clean up previous blob URL
        if (currentBlobUrl) {
          URL.revokeObjectURL(currentBlobUrl);
        }

        currentBlobUrl = URL.createObjectURL(blob);
        posterImg.src = currentBlobUrl;
        previewEl.classList.add("show");
        statusEl.textContent = "✅ הפוסטר נוצר בהצלחה!";
        statusEl.className = "status success show";
      } catch (err) {
        console.error(err);
        statusEl.textContent = "❌ " + err.message;
        statusEl.className = "status error show";
      } finally {
        btn.classList.remove("loading");
        btn.disabled = false;
      }
    });

    downloadBtn.addEventListener("click", () => {
      if (!currentBlobUrl) return;

      const link = document.createElement("a");
      link.href = currentBlobUrl;
      link.download = "shabbat-poster.png";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    });
  </script>
</body>
</html>
    """


@app.post("/poster")
async def create_poster(payload: Dict[str, Any] = Body(default={})):
    """
    FastAPI endpoint that:
    - Receives JSON payload
    - Uses build_poster_from_payload to generate a PNG
    - Returns image/png as response
    """
    if payload is None:
        payload = {}

    poster_bytes = build_poster_from_payload(payload)
    return Response(content=poster_bytes, media_type="image/png")
