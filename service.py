from typing import Any, Dict
from fastapi import FastAPI, Body
from fastapi.responses import Response

from api.poster import build_poster_from_payload


app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def index():
    # UI פשוט ונחמד ליצירת פוסטר
    return """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <title>יוצר פוסטר לשבת</title>
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f5f5;
      margin: 0;
      padding: 0;
      display: flex;
      justify-content: center;
      align-items: flex-start;
      min-height: 100vh;
    }
    .container {
      background: #ffffff;
      margin-top: 40px;
      padding: 24px 24px 32px;
      border-radius: 16px;
      box-shadow: 0 8px 20px rgba(0,0,0,0.08);
      max-width: 480px;
      width: 100%;
    }
    h1 {
      margin-top: 0;
      text-align: center;
      font-size: 24px;
    }
    label {
      display: block;
      margin-top: 16px;
      margin-bottom: 4px;
      font-weight: 600;
    }
    input[type="text"], textarea {
      width: 100%;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid #ccc;
      box-sizing: border-box;
      font-size: 14px;
    }
    textarea {
      resize: vertical;
      min-height: 60px;
    }
    button {
      margin-top: 20px;
      width: 100%;
      padding: 10px 0;
      border-radius: 999px;
      border: none;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      background: #0070f3;
      color: white;
      transition: background 0.15s ease, transform 0.05s ease;
    }
    button:disabled {
      opacity: 0.6;
      cursor: default;
    }
    button:hover:not(:disabled) {
      background: #0059c1;
    }
    button:active:not(:disabled) {
      transform: translateY(1px);
    }
    .status {
      margin-top: 12px;
      font-size: 14px;
      text-align: center;
      min-height: 18px;
    }
    .status.error {
      color: #d32f2f;
    }
    .status.success {
      color: #388e3c;
    }
    .preview {
      margin-top: 20px;
      text-align: center;
    }
    .preview img {
      max-width: 100%;
      border-radius: 16px;
      box-shadow: 0 6px 16px rgba(0,0,0,0.12);
    }
    .hint {
      font-size: 12px;
      color: #666;
      margin-top: 4px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>יוצר פוסטר לשבת</h1>

    <label for="imageUrl">קישור לתמונת רקע (לא חובה)</label>
    <input id="imageUrl" type="text" placeholder="https://example.com/image.jpg" />
    <div class="hint">אם תשאיר ריק, תשתמש תמונת הדיפולט שקיימת בשרת</div>

    <label for="message">משפט לפוסטר</label>
    <textarea id="message" placeholder="שבת שלום! לחיי שמחות קטנות וגדולות"></textarea>

    <label for="neshama">לעילוי נשמת</label>
    <input id="neshama" type="text" placeholder="למשל: אורי בורנשטיין הי״ד" />

    <button id="generateBtn">צור פוסטר</button>

    <div id="status" class="status"></div>

    <div class="preview" id="preview" style="display:none;">
      <h3>התוצאה:</h3>
      <img id="posterImage" alt="פוסטר שנוצר" />
    </div>
  </div>

  <script>
    const btn = document.getElementById("generateBtn");
    const statusEl = document.getElementById("status");
    const previewEl = document.getElementById("preview");
    const posterImg = document.getElementById("posterImage");

    btn.addEventListener("click", async () => {
      const imageUrl = document.getElementById("imageUrl").value.trim();
      const message = document.getElementById("message").value.trim();
      const leiluyNeshama = document.getElementById("neshama").value.trim();

      statusEl.textContent = "יוצר פוסטר...";
      statusEl.className = "status";
      btn.disabled = true;
      previewEl.style.display = "none";

      const payload = {};
      if (imageUrl) {
        payload.imageUrl = imageUrl;
      }
      if (message) {
        payload.message = message;
      }
      if (leiluyNeshama) {
        payload.leiluyNeshama = leiluyNeshama;
      }

      try {
        const resp = await fetch("/poster", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) {
          const text = await resp.text();
          throw new Error("שרת החזיר שגיאה: " + resp.status + " " + text);
        }

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);

        posterImg.src = url;
        previewEl.style.display = "block";
        statusEl.textContent = "הפוסטר נוצר בהצלחה!";
        statusEl.className = "status success";
      } catch (err) {
        console.error(err);
        statusEl.textContent = "אירעה שגיאה ביצירת הפוסטר: " + err.message;
        statusEl.className = "status error";
      } finally {
        btn.disabled = false;
      }
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
