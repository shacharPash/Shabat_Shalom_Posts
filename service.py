import json
from typing import Any, Dict, List

from fastapi import FastAPI, Body
from fastapi.responses import Response, HTMLResponse

from api.poster import build_poster_from_payload


app = FastAPI()

# Load cities from GeoJSON at startup
def load_cities_from_geojson() -> List[Dict[str, Any]]:
    """Load and parse cities from the GeoJSON file."""
    try:
        with open("cities_coordinates.geojson", "r", encoding="utf-8") as f:
            data = json.load(f)

        cities = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])

            name = props.get("MGLSDE_LOC", "").strip()
            if name and len(coords) >= 2:
                cities.append({
                    "name": name,
                    "lat": coords[1],  # GeoJSON is [lon, lat]
                    "lon": coords[0],
                    "candle_offset": 20  # Default offset
                })

        # Sort alphabetically by Hebrew name
        cities.sort(key=lambda c: c["name"])
        return cities
    except Exception as e:
        print(f"Error loading GeoJSON: {e}")
        return []

# Load cities once at startup
GEOJSON_CITIES = load_cities_from_geojson()
CITY_BY_NAME = {c["name"]: c for c in GEOJSON_CITIES}

@app.get("/", response_class=HTMLResponse)
async def index():
    # Generate city checkboxes dynamically from GeoJSON data
    city_checkboxes = "\n".join([
        f'        <label class="city-option"><input type="checkbox" name="cityOption" value="{city["name"]}"><span>{city["name"]}</span></label>'
        for city in GEOJSON_CITIES
    ])
    total_cities = len(GEOJSON_CITIES)

    # UI מעוצב ליצירת פוסטר שבת
    # Using CITY_CHECKBOXES_PLACEHOLDER and TOTAL_CITIES_PLACEHOLDER to avoid f-string issues with CSS braces
    html_template = """
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
    /* File upload styling */
    .file-upload-wrapper {
      position: relative;
    }
    .file-input-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      opacity: 0;
      overflow: hidden;
    }
    .file-upload-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      padding: 14px 16px;
      border-radius: 12px;
      border: 2px dashed #c5cae9;
      background: #f5f5ff;
      color: #3949ab;
      font-size: 15px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      font-family: inherit;
    }
    .file-upload-btn:hover {
      border-color: #5c6bc0;
      background: #ede7f6;
    }
    .file-upload-btn.has-file {
      border-style: solid;
      border-color: #5c6bc0;
      background: #e8eaf6;
    }
    .file-name {
      font-size: 13px;
      color: #5c6bc0;
      margin-top: 8px;
      display: none;
      align-items: center;
      gap: 6px;
    }
    .file-name.show {
      display: flex;
    }
    .file-name .clear-file {
      background: none;
      border: none;
      color: #e53935;
      cursor: pointer;
      font-size: 16px;
      padding: 0 4px;
      line-height: 1;
    }
    .file-name .clear-file:hover {
      color: #c62828;
    }
    /* City selection */
    .cities-section {
      border: 2px solid #e8eaf6;
      border-radius: 12px;
      padding: 16px;
      background: #fafafa;
    }
    .cities-header {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .cities-counter {
      font-size: 13px;
      color: #5c6bc0;
      background: #e8eaf6;
      padding: 4px 10px;
      border-radius: 20px;
      transition: all 0.2s ease;
    }
    .cities-counter.limit-reached {
      background: #fff3e0;
      color: #e65100;
      font-weight: 600;
    }
    .cities-actions {
      display: flex;
      gap: 8px;
    }
    .cities-actions button {
      font-size: 12px;
      padding: 6px 12px;
      border-radius: 6px;
      border: 1px solid #c5cae9;
      background: #fff;
      color: #3949ab;
      cursor: pointer;
      font-family: inherit;
      transition: all 0.15s ease;
    }
    .cities-actions button:hover {
      background: #e8eaf6;
      border-color: #5c6bc0;
    }
    .city-search {
      width: 100%;
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
      font-size: 14px;
      font-family: inherit;
      margin-bottom: 12px;
      background: #fff;
    }
    .city-search:focus {
      outline: none;
      border-color: #5c6bc0;
      box-shadow: 0 0 0 3px rgba(92, 107, 192, 0.1);
    }
    .cities-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      max-height: 250px;
      overflow-y: auto;
      padding-left: 4px;
    }
    .city-option {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid #e8eaf6;
      background: #fff;
      cursor: pointer;
      transition: all 0.15s ease;
      font-size: 13px;
    }
    .city-option:hover {
      border-color: #c5cae9;
      background: #f5f5ff;
    }
    .city-option.checked {
      border-color: #5c6bc0;
      background: #e8eaf6;
    }
    .city-option.hidden {
      display: none;
    }
    .city-option.disabled {
      opacity: 0.5;
      cursor: not-allowed;
      pointer-events: none;
    }
    .city-option input[type="checkbox"] {
      width: 16px;
      height: 16px;
      accent-color: #3949ab;
      cursor: pointer;
      flex-shrink: 0;
    }
    .city-option span {
      color: #1a237e;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .no-results {
      grid-column: 1 / -1;
      text-align: center;
      color: #9e9e9e;
      padding: 20px;
      font-size: 14px;
    }
    @media (max-width: 400px) {
      .cities-grid {
        grid-template-columns: 1fr;
      }
      .cities-header {
        flex-direction: column;
        align-items: stretch;
      }
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
      <label>תמונת רקע <span class="optional">(לא חובה)</span></label>
      <div class="file-upload-wrapper">
        <input type="file" id="imageFile" class="file-input-hidden" accept="image/*" />
        <button type="button" id="fileUploadBtn" class="file-upload-btn">
          <span>📷</span> העלה תמונה מהמכשיר
        </button>
        <div id="fileName" class="file-name">
          <span id="fileNameText"></span>
          <button type="button" class="clear-file" id="clearFileBtn" title="הסר קובץ">✕</button>
        </div>
      </div>
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

    <div class="form-group">
      <label>בחר ערים שיופיעו בפוסטר <span class="optional">(לא חובה)</span></label>
      <div class="cities-section">
        <div class="cities-header">
          <span id="citiesCounter" class="cities-counter">נבחרו: 0 מתוך 8</span>
          <div class="cities-actions">
            <button type="button" id="deselectAllBtn">נקה הכל</button>
          </div>
        </div>
        <input type="text" id="citySearch" class="city-search" placeholder="🔍 חפש עיר..." />
        <div class="cities-grid" id="citiesGrid">
CITY_CHECKBOXES_PLACEHOLDER
          <div class="no-results" id="noResults" style="display:none;">לא נמצאו ערים</div>
        </div>
      </div>
      <div class="hint">אם לא תבחר ערים, יוצגו ערי ברירת המחדל</div>
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
    const fileInput = document.getElementById("imageFile");
    const fileUploadBtn = document.getElementById("fileUploadBtn");
    const fileNameEl = document.getElementById("fileName");
    const fileNameText = document.getElementById("fileNameText");
    const clearFileBtn = document.getElementById("clearFileBtn");
    const citySearch = document.getElementById("citySearch");
    const citiesGrid = document.getElementById("citiesGrid");
    const citiesCounter = document.getElementById("citiesCounter");
    const deselectAllBtn = document.getElementById("deselectAllBtn");
    const noResults = document.getElementById("noResults");
    const cityOptions = document.querySelectorAll(".city-option");
    const cityCheckboxes = document.querySelectorAll('input[name="cityOption"]');
    const MAX_CITIES = 8;
    let currentBlobUrl = null;

    // Update city counter and enforce max limit
    function updateCityCounter() {
      const checked = document.querySelectorAll('input[name="cityOption"]:checked').length;
      citiesCounter.textContent = "נבחרו: " + checked + " מתוך " + MAX_CITIES;

      // Add/remove limit-reached class for visual feedback
      if (checked >= MAX_CITIES) {
        citiesCounter.classList.add("limit-reached");
      } else {
        citiesCounter.classList.remove("limit-reached");
      }

      // Disable/enable unchecked checkboxes based on limit
      cityCheckboxes.forEach(cb => {
        if (!cb.checked) {
          cb.disabled = checked >= MAX_CITIES;
          cb.closest(".city-option").classList.toggle("disabled", checked >= MAX_CITIES);
        }
      });
    }

    // Toggle checked class on city option
    cityCheckboxes.forEach(cb => {
      cb.addEventListener("change", () => {
        cb.closest(".city-option").classList.toggle("checked", cb.checked);
        updateCityCounter();
      });
    });

    // City search filter
    citySearch.addEventListener("input", () => {
      const query = citySearch.value.trim().toLowerCase();
      let visibleCount = 0;
      cityOptions.forEach(opt => {
        const name = opt.querySelector("span").textContent.toLowerCase();
        if (name.includes(query)) {
          opt.classList.remove("hidden");
          visibleCount++;
        } else {
          opt.classList.add("hidden");
        }
      });
      noResults.style.display = visibleCount === 0 ? "block" : "none";
    });

    // Deselect all cities
    deselectAllBtn.addEventListener("click", () => {
      cityCheckboxes.forEach(cb => {
        cb.checked = false;
        cb.disabled = false;
        cb.closest(".city-option").classList.remove("checked", "disabled");
      });
      updateCityCounter();
    });

    // File upload button click -> trigger hidden file input
    fileUploadBtn.addEventListener("click", () => {
      fileInput.click();
    });

    // When file is selected, show filename
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];
        fileNameText.textContent = file.name;
        fileNameEl.classList.add("show");
        fileUploadBtn.classList.add("has-file");
        fileUploadBtn.innerHTML = "<span>✅</span> תמונה נבחרה";
      }
    });

    // Clear selected file
    clearFileBtn.addEventListener("click", () => {
      fileInput.value = "";
      fileNameEl.classList.remove("show");
      fileUploadBtn.classList.remove("has-file");
      fileUploadBtn.innerHTML = "<span>📷</span> העלה תמונה מהמכשיר";
    });

    // Helper function to read file as base64
    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          // Remove the data URL prefix (e.g., "data:image/png;base64,")
          const base64 = reader.result.split(",")[1];
          resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }

    btn.addEventListener("click", async () => {
      const message = document.getElementById("message").value.trim();
      const leiluyNeshama = document.getElementById("neshama").value.trim();
      const selectedFile = fileInput.files && fileInput.files[0];

      // Show loading state
      statusEl.textContent = "⏳ יוצר את הפוסטר שלך...";
      statusEl.className = "status loading show";
      btn.classList.add("loading");
      btn.disabled = true;
      previewEl.classList.remove("show");

      const payload = {};

      try {
        if (selectedFile) {
          // Convert file to base64 and add to payload
          const base64 = await readFileAsBase64(selectedFile);
          payload.imageBase64 = base64;
        }

        if (message) payload.message = message;
        if (leiluyNeshama) payload.leiluyNeshama = leiluyNeshama;

        // Collect selected cities
        const selectedCities = [];
        document.querySelectorAll('input[name="cityOption"]:checked').forEach(cb => {
          selectedCities.push(cb.value);
        });
        if (selectedCities.length > 0) {
          payload.cities = selectedCities;
        }

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

    # Replace placeholders with actual values
    return html_template.replace("CITY_CHECKBOXES_PLACEHOLDER", city_checkboxes).replace("TOTAL_CITIES_PLACEHOLDER", str(total_cities))


@app.post("/poster")
async def create_poster(payload: Dict[str, Any] = Body(default={})):
    """
    FastAPI endpoint that:
    - Receives JSON payload
    - Uses build_poster_from_payload to generate a PNG
    - Returns image/png as response

    If payload contains 'cities' as a list of city names (strings),
    maps them to full city objects with coordinates from GeoJSON.
    """
    if payload is None:
        payload = {}

    # Map city names to full city objects with coordinates
    if "cities" in payload and isinstance(payload["cities"], list):
        city_names = payload["cities"]
        mapped_cities = []
        for name in city_names:
            if name in CITY_BY_NAME:
                mapped_cities.append(CITY_BY_NAME[name])
        # Only use mapped cities if we found at least one
        if mapped_cities:
            payload["cities"] = mapped_cities
        else:
            # Remove invalid cities list to use default
            del payload["cities"]

    poster_bytes = build_poster_from_payload(payload)
    return Response(content=poster_bytes, media_type="image/png")
