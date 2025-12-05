from typing import Any, Dict, List
from datetime import date, timedelta

from fastapi import FastAPI, Body
from fastapi.responses import Response, HTMLResponse

from api.poster import build_poster_from_payload
from cities import get_cities_list, build_city_lookup
from make_shabbat_posts import find_next_sequence, get_parsha_from_hebcal


app = FastAPI()

# Load cities once at startup (cached internally)
GEOJSON_CITIES = get_cities_list()
CITY_BY_NAME = build_city_lookup(GEOJSON_CITIES)

@app.get("/", response_class=HTMLResponse)
async def index():
    # Generate city checkboxes dynamically from GeoJSON data with offset input
    city_checkboxes = "\n".join([
        f'        <div class="city-option" data-name="{city["name"]}"><input type="checkbox" name="cityOption" value="{city["name"]}"><span class="city-name">{city["name"]}</span><div class="offset-input"><input type="number" class="candle-offset" value="{city["candle_offset"]}" min="0" max="60" title="דקות לפני השקיעה"><span class="offset-label">ד\'</span></div></div>'
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
    /* Dedication section styling */
    .dedication-add-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
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
    .dedication-add-btn:hover {
      border-color: #5c6bc0;
      background: #ede7f6;
    }
    .dedication-section {
      display: none;
      animation: fadeIn 0.3s ease;
    }
    .dedication-section.show {
      display: block;
    }
    .dedication-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .dedication-header label {
      margin-bottom: 0;
    }
    .dedication-close-btn {
      background: none;
      border: none;
      color: #9e9e9e;
      font-size: 20px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 6px;
      transition: all 0.15s ease;
      line-height: 1;
    }
    .dedication-close-btn:hover {
      background: #ffebee;
      color: #e53935;
    }
    /* Date selection styling */
    /* Advanced options section */
    .advanced-toggle {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid #e0e0e0;
      background: #fafafa;
      color: #666;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s ease;
      font-family: inherit;
      margin-top: 8px;
    }
    .advanced-toggle:hover {
      background: #f5f5f5;
      border-color: #bdbdbd;
      color: #424242;
    }
    .advanced-toggle.open {
      background: #e8eaf6;
      border-color: #5c6bc0;
      color: #3949ab;
    }
    .advanced-toggle .arrow {
      transition: transform 0.2s ease;
    }
    .advanced-toggle.open .arrow {
      transform: rotate(180deg);
    }
    .advanced-section {
      display: none;
      margin-top: 16px;
      padding: 16px;
      border: 2px solid #e8eaf6;
      border-radius: 12px;
      background: #fafafa;
      animation: fadeIn 0.3s ease;
    }
    .advanced-section.show {
      display: block;
    }
    .advanced-title {
      font-size: 14px;
      font-weight: 600;
      color: #3949ab;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .date-selection {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }
    .date-option {
      padding: 10px 14px;
      border-radius: 10px;
      border: 2px solid #e8eaf6;
      background: #fff;
      color: #3949ab;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.15s ease;
      text-align: center;
      flex: 1;
      min-width: 100px;
    }
    .date-option:hover {
      border-color: #c5cae9;
      background: #f5f5ff;
    }
    .date-option.selected {
      border-color: #5c6bc0;
      background: #e8eaf6;
      font-weight: 600;
    }
    .date-option .event-name {
      font-weight: 600;
      display: block;
      margin-bottom: 4px;
      font-size: 12px;
    }
    .date-option .event-date {
      font-size: 11px;
      color: #7986cb;
    }
    .date-option.selected .event-date {
      color: #3949ab;
    }
    .multi-select-info {
      font-size: 12px;
      color: #7986cb;
      margin-bottom: 8px;
    }
    .weeks-selector {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      background: #fff;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
    }
    .weeks-selector label {
      font-size: 13px;
      color: #3949ab;
      margin: 0;
    }
    .weeks-input {
      width: 60px;
      padding: 8px;
      border: 1px solid #c5cae9;
      border-radius: 6px;
      font-size: 14px;
      text-align: center;
      color: #3949ab;
    }
    .weeks-input:focus {
      outline: none;
      border-color: #5c6bc0;
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
    /* City selection - minimal design */
    .cities-section {
      border: 1px solid #e0e0e0;
      border-radius: 10px;
      padding: 12px;
      background: #fff;
    }
    .city-search {
      width: 100%;
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
      font-size: 14px;
      font-family: inherit;
      background: #fafafa;
    }
    .city-search:focus {
      outline: none;
      border-color: #5c6bc0;
      background: #fff;
    }
    /* Selected cities chips */
    .selected-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;
    }
    .selected-chips:empty {
      display: none;
    }
    .city-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #e8eaf6;
      border: 1px solid #c5cae9;
      border-radius: 16px;
      padding: 4px 10px;
      font-size: 13px;
      color: #3949ab;
    }
    .city-chip .chip-name {
      max-width: 100px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .city-chip .chip-remove {
      cursor: pointer;
      font-size: 14px;
      color: #7986cb;
      line-height: 1;
    }
    .city-chip .chip-remove:hover {
      color: #c62828;
    }
    /* Show all toggle */
    .show-all-toggle {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      margin-top: 10px;
      padding: 8px;
      border: none;
      background: none;
      color: #5c6bc0;
      font-size: 13px;
      font-family: inherit;
      cursor: pointer;
      width: 100%;
    }
    .show-all-toggle:hover {
      color: #3949ab;
    }
    .show-all-toggle .arrow {
      transition: transform 0.2s ease;
    }
    .show-all-toggle.open .arrow {
      transform: rotate(180deg);
    }
    /* Cities grid - hidden by default */
    .cities-grid-wrapper {
      display: none;
      margin-top: 10px;
      border-top: 1px solid #eee;
      padding-top: 10px;
    }
    .cities-grid-wrapper.show {
      display: block;
    }
    .cities-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4px;
      max-height: 200px;
      overflow-y: auto;
    }
    .city-option {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 6px 8px;
      border-radius: 6px;
      background: #fafafa;
      cursor: pointer;
      transition: background 0.15s ease;
      font-size: 12px;
    }
    .city-option:hover {
      background: #f0f0f0;
    }
    .city-option.checked {
      background: #e8eaf6;
    }
    .city-option.hidden {
      display: none;
    }
    .city-option.disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .city-option input[type="checkbox"] {
      width: 14px;
      height: 14px;
      accent-color: #3949ab;
      cursor: pointer;
    }
    .city-name {
      color: #333;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      flex: 1;
      font-size: 12px;
    }
    .offset-input {
      display: none;
    }
    .candle-offset {
      width: 32px;
      padding: 2px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 11px;
      text-align: center;
    }
    .offset-label { display: none; }
    .no-results {
      grid-column: 1 / -1;
      text-align: center;
      color: #999;
      padding: 16px;
      font-size: 13px;
    }
    @media (max-width: 400px) {
      .cities-grid {
        grid-template-columns: repeat(2, 1fr);
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
      <h1>יוצר פוסטר לשבת וחג</h1>
      <div class="subtitle">צרו פוסטר יפה עם זמני הדלקת נרות לשבת או לחג</div>
    </div>

    <div class="form-group">
      <label>תמונת רקע <span class="optional">(לא חובה)</span></label>
      <div class="file-upload-wrapper">
        <input type="file" id="imageFile" class="file-input-hidden" accept="image/*" multiple />
        <button type="button" id="fileUploadBtn" class="file-upload-btn">
          <span>📷</span> העלה תמונה או צלם
        </button>
        <div id="fileName" class="file-name">
          <span id="fileNameText"></span>
          <button type="button" class="clear-file" id="clearFileBtn" title="הסר קובץ">✕</button>
        </div>
      </div>
      <div class="hint" id="uploadHint">השאירו ריק לשימוש בתמונת ברירת המחדל</div>
    </div>

    <div class="form-group" id="blessingGroup">
      <button type="button" id="addBlessingBtn" class="dedication-add-btn">
        <span>✨</span> הוסף ברכה אישית
      </button>
      <div id="blessingSection" class="dedication-section">
        <div class="dedication-header">
          <label for="message">ברכה לפוסטר</label>
          <button type="button" id="closeBlessingBtn" class="dedication-close-btn" title="הסר ברכה">✕</button>
        </div>
        <textarea id="message" placeholder="למשל: לחיי שמחות קטנות וגדולות"></textarea>
        <div class="hint">💡 אין צורך לכתוב "שבת שלום" - זו כבר הכותרת הראשית של הפוסטר</div>
      </div>
    </div>

    <div class="form-group" id="dedicationGroup">
      <button type="button" id="addDedicationBtn" class="dedication-add-btn">
        <span>🕯️</span> הוסף הקדשה לעילוי נשמת
      </button>
      <div id="dedicationSection" class="dedication-section">
        <div class="dedication-header">
          <label for="neshama">לעילוי נשמת</label>
          <button type="button" id="closeDedicationBtn" class="dedication-close-btn" title="הסר הקדשה">✕</button>
        </div>
        <input id="neshama" type="text" placeholder="למשל: אורי בורנשטיין הי״ד" />
      </div>
    </div>

    <div class="form-group">
      <label>בחר ערים ויישובים</label>
      <div class="cities-section">
        <input type="text" id="citySearch" class="city-search" placeholder="🔍 חפש עיר או יישוב..." />
        <div id="selectedChips" class="selected-chips"></div>
        <button type="button" id="showAllCitiesBtn" class="show-all-toggle">
          <span>הצג את כל הערים</span>
          <span class="arrow">▼</span>
        </button>
        <div id="citiesGridWrapper" class="cities-grid-wrapper">
          <div class="cities-grid" id="citiesGrid">
CITY_CHECKBOXES_PLACEHOLDER
            <div class="no-results" id="noResults" style="display:none;">לא נמצאו ערים</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Advanced Options Toggle -->
    <button type="button" id="advancedToggle" class="advanced-toggle">
      <span>⚙️ אפשרויות מתקדמות</span>
      <span class="arrow">▼</span>
    </button>

    <div id="advancedSection" class="advanced-section">
      <div class="advanced-title">📅 בחירת תאריך</div>
      <div class="multi-select-info">לחץ על תאריך אחד או יותר ליצירת מספר פוסטרים</div>
      <div id="dateSelection" class="date-selection">
        <div class="date-option selected" data-date="">
          <span class="event-name">⏳ טוען...</span>
          <span class="event-date"></span>
        </div>
      </div>
      <div class="weeks-selector">
        <label>או: צור פוסטרים ל-</label>
        <input type="number" id="weeksAhead" class="weeks-input" min="1" max="12" value="1" />
        <label>שבתות/חגים קדימה</label>
      </div>
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
    const advancedToggle = document.getElementById("advancedToggle");
    const advancedSection = document.getElementById("advancedSection");
    const dateSelection = document.getElementById("dateSelection");
    const weeksAhead = document.getElementById("weeksAhead");
    const citySearch = document.getElementById("citySearch");
    const citiesGrid = document.getElementById("citiesGrid");
    const citiesGridWrapper = document.getElementById("citiesGridWrapper");
    const selectedChips = document.getElementById("selectedChips");
    const showAllCitiesBtn = document.getElementById("showAllCitiesBtn");
    const noResults = document.getElementById("noResults");
    const cityOptions = document.querySelectorAll(".city-option");
    const cityCheckboxes = document.querySelectorAll('input[name="cityOption"]');
    const addDedicationBtn = document.getElementById("addDedicationBtn");
    const dedicationSection = document.getElementById("dedicationSection");
    const closeDedicationBtn = document.getElementById("closeDedicationBtn");
    const neshamaInput = document.getElementById("neshama");
    const addBlessingBtn = document.getElementById("addBlessingBtn");
    const blessingSection = document.getElementById("blessingSection");
    const closeBlessingBtn = document.getElementById("closeBlessingBtn");
    const messageInput = document.getElementById("message");
    const MAX_CITIES = 8;
    let currentBlobUrl = null;
    let dedicationEnabled = false;
    let blessingEnabled = false;
    let selectedDates = []; // Array of selected dates
    let allEvents = []; // Store all events

    // Advanced options toggle
    advancedToggle.addEventListener("click", () => {
      advancedToggle.classList.toggle("open");
      advancedSection.classList.toggle("show");
    });

    // Load upcoming events for date selection
    async function loadUpcomingEvents() {
      try {
        const resp = await fetch("/upcoming-events");
        allEvents = await resp.json();

        dateSelection.innerHTML = allEvents.map((event, i) => `
          <div class="date-option ${i === 0 ? 'selected' : ''}" data-date="${event.startDate}" data-index="${i}">
            <span class="event-name">${event.displayName}</span>
            <span class="event-date">${event.dateStr}</span>
          </div>
        `).join('');

        // First event is selected by default
        selectedDates = [allEvents[0].startDate];

        // Add click handlers for multi-select
        dateSelection.querySelectorAll('.date-option').forEach(opt => {
          opt.addEventListener('click', (e) => {
            const date = opt.dataset.date;
            if (e.ctrlKey || e.metaKey) {
              // Multi-select with Ctrl/Cmd
              opt.classList.toggle('selected');
              if (opt.classList.contains('selected')) {
                if (!selectedDates.includes(date)) selectedDates.push(date);
              } else {
                selectedDates = selectedDates.filter(d => d !== date);
              }
            } else {
              // Single select
              dateSelection.querySelectorAll('.date-option').forEach(o => o.classList.remove('selected'));
              opt.classList.add('selected');
              selectedDates = [date];
            }
            // Reset weeks when manually selecting
            weeksAhead.value = selectedDates.length;
            if (typeof updateUploadHint === 'function') updateUploadHint();
          });
        });
      } catch (err) {
        console.error("Failed to load events:", err);
        dateSelection.innerHTML = '<div class="date-option selected" data-date=""><span class="event-name">שבת/חג הקרוב</span></div>';
        selectedDates = [""];
      }
    }
    loadUpcomingEvents();

    // Weeks selector - auto-select dates
    weeksAhead.addEventListener("change", () => {
      const weeks = parseInt(weeksAhead.value) || 1;
      const options = dateSelection.querySelectorAll('.date-option');
      options.forEach(o => o.classList.remove('selected'));
      selectedDates = [];
      for (let i = 0; i < Math.min(weeks, options.length); i++) {
        options[i].classList.add('selected');
        selectedDates.push(allEvents[i]?.startDate || "");
      }
      if (typeof updateUploadHint === 'function') updateUploadHint();
    });

    // Blessing section toggle
    addBlessingBtn.addEventListener("click", () => {
      blessingEnabled = true;
      addBlessingBtn.style.display = "none";
      blessingSection.classList.add("show");
      messageInput.focus();
    });

    closeBlessingBtn.addEventListener("click", () => {
      blessingEnabled = false;
      messageInput.value = "";
      blessingSection.classList.remove("show");
      addBlessingBtn.style.display = "flex";
    });

    // Dedication section toggle
    addDedicationBtn.addEventListener("click", () => {
      dedicationEnabled = true;
      addDedicationBtn.style.display = "none";
      dedicationSection.classList.add("show");
      neshamaInput.focus();
    });

    closeDedicationBtn.addEventListener("click", () => {
      dedicationEnabled = false;
      neshamaInput.value = "";
      dedicationSection.classList.remove("show");
      addDedicationBtn.style.display = "flex";
    });

    // Render selected cities as chips
    function renderChips() {
      const checked = document.querySelectorAll('input[name="cityOption"]:checked');
      selectedChips.innerHTML = Array.from(checked).map(cb => {
        const name = cb.closest(".city-option").dataset.name;
        return `<span class="city-chip" data-name="${name}"><span class="chip-name">${name}</span><span class="chip-remove">✕</span></span>`;
      }).join('');
      // Add click handlers to remove chips
      selectedChips.querySelectorAll('.chip-remove').forEach(btn => {
        btn.addEventListener('click', () => {
          const name = btn.closest('.city-chip').dataset.name;
          const cb = document.querySelector(`.city-option[data-name="${name}"] input`);
          if (cb) { cb.checked = false; cb.closest('.city-option').classList.remove('checked'); }
          renderChips();
          updateCityLimit();
        });
      });
    }

    // Enforce max limit
    function updateCityLimit() {
      const checked = document.querySelectorAll('input[name="cityOption"]:checked').length;
      cityCheckboxes.forEach(cb => {
        if (!cb.checked) {
          cb.disabled = checked >= MAX_CITIES;
          cb.closest(".city-option").classList.toggle("disabled", checked >= MAX_CITIES);
        }
      });
    }

    // Show all cities toggle
    showAllCitiesBtn.addEventListener("click", () => {
      showAllCitiesBtn.classList.toggle("open");
      citiesGridWrapper.classList.toggle("show");
      showAllCitiesBtn.querySelector("span:first-child").textContent =
        citiesGridWrapper.classList.contains("show") ? "הסתר רשימה" : "הצג את כל הערים";
    });

    // Toggle checked class on city option
    cityCheckboxes.forEach(cb => {
      cb.addEventListener("change", () => {
        cb.closest(".city-option").classList.toggle("checked", cb.checked);
        renderChips();
        updateCityLimit();
      });
    });

    // Make entire city option clickable
    cityOptions.forEach(opt => {
      opt.addEventListener("click", (e) => {
        if (e.target.classList.contains("candle-offset")) return;
        const cb = opt.querySelector('input[name="cityOption"]');
        if (cb.disabled && !cb.checked) return;
        cb.checked = !cb.checked;
        opt.classList.toggle("checked", cb.checked);
        renderChips();
        updateCityLimit();
      });
    });

    // City search - show grid when typing, filter results
    citySearch.addEventListener("input", () => {
      const query = citySearch.value.trim().toLowerCase();
      if (query) {
        citiesGridWrapper.classList.add("show");
        showAllCitiesBtn.classList.add("open");
        showAllCitiesBtn.querySelector("span:first-child").textContent = "הסתר רשימה";
      }
      let visibleCount = 0;
      cityOptions.forEach(opt => {
        const name = opt.querySelector(".city-name").textContent.toLowerCase();
        if (name.includes(query)) { opt.classList.remove("hidden"); visibleCount++; }
        else { opt.classList.add("hidden"); }
      });
      noResults.style.display = visibleCount === 0 ? "block" : "none";
    });

    const uploadHint = document.getElementById("uploadHint");

    // Update upload hint based on selected dates
    function updateUploadHint() {
      const count = selectedDates.length;
      if (count > 1) {
        uploadHint.textContent = `ניתן להעלות עד ${count} תמונות - אחת לכל פוסטר. אם תעלו פחות, התמונה האחרונה תשמש לשאר.`;
        uploadHint.style.color = "#5c6bc0";
      } else {
        uploadHint.textContent = "השאירו ריק לשימוש בתמונת ברירת המחדל";
        uploadHint.style.color = "";
      }
    }

    // File upload button click -> trigger file input (browser shows both gallery and camera on mobile)
    fileUploadBtn.addEventListener("click", () => {
      fileInput.click();
    });

    // When files are selected
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        const count = fileInput.files.length;
        if (count === 1) {
          fileNameText.textContent = fileInput.files[0].name;
        } else {
          fileNameText.textContent = `${count} תמונות נבחרו`;
        }
        fileNameEl.classList.add("show");
        fileUploadBtn.classList.add("has-file");
        fileUploadBtn.innerHTML = count === 1
          ? "<span>✅</span> תמונה נבחרה"
          : `<span>✅</span> ${count} תמונות נבחרו`;
      }
    });

    // Clear selected files
    clearFileBtn.addEventListener("click", () => {
      fileInput.value = "";
      fileNameEl.classList.remove("show");
      fileUploadBtn.classList.remove("has-file");
      fileUploadBtn.innerHTML = "<span>📷</span> העלה תמונה או צלם";
    });

    // Helper function to read file as base64
    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = reader.result.split(",")[1];
          resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }

    // Store generated posters for multi-download
    let generatedPosters = [];

    btn.addEventListener("click", async () => {
      const message = messageInput.value.trim();
      const leiluyNeshama = neshamaInput.value.trim();
      const hideDedication = !dedicationEnabled;
      const hideBlessing = !blessingEnabled;
      const uploadedFiles = fileInput.files;

      // Determine dates to generate
      const datesToGenerate = selectedDates.length > 0 ? selectedDates : [""];
      const isMultiple = datesToGenerate.length > 1;

      statusEl.textContent = isMultiple
        ? `⏳ יוצר ${datesToGenerate.length} פוסטרים...`
        : "⏳ יוצר את הפוסטר שלך...";
      statusEl.className = "status loading show";
      btn.classList.add("loading");
      btn.disabled = true;
      previewEl.classList.remove("show");
      generatedPosters = [];

      try {
        // Convert all uploaded images to base64
        const imagesBase64 = [];
        if (uploadedFiles && uploadedFiles.length > 0) {
          for (let f = 0; f < uploadedFiles.length; f++) {
            const base64 = await readFileAsBase64(uploadedFiles[f]);
            imagesBase64.push(base64);
          }
        }

        // Collect selected cities
        const selectedCities = [];
        document.querySelectorAll('input[name="cityOption"]:checked').forEach(cb => {
          const cityOption = cb.closest(".city-option");
          const cityName = cityOption.dataset.name;
          const offsetInput = cityOption.querySelector(".candle-offset");
          const offset = parseInt(offsetInput.value) || 20;
          selectedCities.push({ name: cityName, candle_offset: offset });
        });

        // Generate poster for each date
        for (let i = 0; i < datesToGenerate.length; i++) {
          const date = datesToGenerate[i];
          const payload = {};

          // Use corresponding image, or last image if fewer images than dates
          if (imagesBase64.length > 0) {
            const imgIndex = Math.min(i, imagesBase64.length - 1);
            payload.imageBase64 = imagesBase64[imgIndex];
          }
          if (message) payload.message = message;
          if (leiluyNeshama) payload.leiluyNeshama = leiluyNeshama;
          if (hideDedication) payload.hideDedication = true;
          if (hideBlessing) payload.hideBlessing = true;
          if (date) payload.startDate = date;
          if (selectedCities.length > 0) payload.cities = selectedCities;

          statusEl.textContent = isMultiple
            ? `⏳ יוצר פוסטר ${i + 1} מתוך ${datesToGenerate.length}...`
            : "⏳ יוצר את הפוסטר שלך...";

          const resp = await fetch("/poster", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });

          if (!resp.ok) {
            throw new Error("שגיאה מהשרת: " + resp.status);
          }

          const blob = await resp.blob();
          generatedPosters.push({ blob, date });
        }

        // Show the first poster (or only poster)
        if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
        currentBlobUrl = URL.createObjectURL(generatedPosters[0].blob);
        posterImg.src = currentBlobUrl;
        previewEl.classList.add("show");

        statusEl.textContent = isMultiple
          ? `✅ נוצרו ${datesToGenerate.length} פוסטרים בהצלחה! לחץ הורד להורדת כולם.`
          : "✅ הפוסטר נוצר בהצלחה!";
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

    downloadBtn.addEventListener("click", async () => {
      if (generatedPosters.length === 0) return;

      if (generatedPosters.length === 1) {
        // Single poster download
        const link = document.createElement("a");
        link.href = URL.createObjectURL(generatedPosters[0].blob);
        link.download = "shabbat-poster.png";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        // Multiple posters - download each
        for (let i = 0; i < generatedPosters.length; i++) {
          const link = document.createElement("a");
          link.href = URL.createObjectURL(generatedPosters[i].blob);
          link.download = `shabbat-poster-${i + 1}.png`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          // Small delay between downloads
          await new Promise(r => setTimeout(r, 300));
        }
      }
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

    If payload contains 'cities' as a list of city objects (with name and candle_offset),
    maps them to full city objects with coordinates from GeoJSON.
    """
    if payload is None:
        payload = {}

    # Map city names to full city objects with coordinates
    if "cities" in payload and isinstance(payload["cities"], list):
        city_items = payload["cities"]
        mapped_cities = []
        for item in city_items:
            # Handle both old format (string) and new format (object with name and candle_offset)
            if isinstance(item, str):
                name = item
                candle_offset = 20
            elif isinstance(item, dict):
                name = item.get("name", "")
                candle_offset = item.get("candle_offset", 20)
            else:
                continue

            if name in CITY_BY_NAME:
                city = CITY_BY_NAME[name].copy()
                city["candle_offset"] = candle_offset  # Override with user's offset
                mapped_cities.append(city)

        # Only use mapped cities if we found at least one
        if mapped_cities:
            payload["cities"] = mapped_cities
        else:
            # Remove invalid cities list to use default
            del payload["cities"]

    poster_bytes = build_poster_from_payload(payload)
    return Response(content=poster_bytes, media_type="image/png")


@app.get("/upcoming-events")
async def get_upcoming_events():
    """Get the next 4 upcoming Shabbat/holiday events for date selection."""
    events = []
    current_date = date.today()

    for i in range(4):
        seq_start, seq_end, event_type, event_name = find_next_sequence(current_date)

        # Get parsha for Shabbat
        parsha = None
        if event_type == "shabbos" or seq_end.weekday() == 5:  # Saturday
            parsha = get_parsha_from_hebcal(seq_end)

        # Format event name in Hebrew
        if event_type == "shabbos":
            display_name = parsha if parsha else "שבת"
        else:
            # Translate common Yom Tov names to Hebrew
            yomtov_translations = {
                "Rosh Hashana": "ראש השנה",
                "Yom Kippur": "יום כיפור",
                "Sukkos": "סוכות",
                "Shmini Atzeres": "שמיני עצרת",
                "Simchas Torah": "שמחת תורה",
                "Pesach": "פסח",
                "Shavuos": "שבועות",
                "Chanukah": "חנוכה",
                "Purim": "פורים",
            }
            display_name = yomtov_translations.get(event_name, event_name)
            if parsha:
                display_name = f"{display_name} | {parsha}"

        # Format date in Hebrew style
        date_str = f"{seq_start.day}/{seq_start.month}"
        if seq_start != seq_end:
            date_str += f" - {seq_end.day}/{seq_end.month}"

        events.append({
            "startDate": seq_start.isoformat(),
            "endDate": seq_end.isoformat(),
            "eventType": event_type,
            "eventName": event_name,
            "displayName": display_name,
            "dateStr": date_str,
            "isNext": i == 0,
        })

        # Move to day after this sequence ends
        current_date = seq_end + timedelta(days=1)

    return events
