import html
import os
from typing import Any, Dict, List
from datetime import date, timedelta

from fastapi import FastAPI, Body
from fastapi.responses import Response, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from api.poster import build_poster_from_payload
from cities import get_cities_list, build_city_lookup
from make_shabbat_posts import find_next_sequence, get_parsha_from_hebcal


app = FastAPI()

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "public", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Favicon route at root level (browsers look for /favicon.ico)
@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(static_dir, "favicon.ico")
    if os.path.isfile(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    return Response(status_code=404)


# Load cities once at startup (cached internally)
GEOJSON_CITIES = get_cities_list()
CITY_BY_NAME = build_city_lookup(GEOJSON_CITIES)

@app.get("/", response_class=HTMLResponse)
async def index():
    # Generate city checkboxes dynamically from GeoJSON data with offset input
    # Use html.escape to handle city names with quotes (e.g., עין הנצי"ב)
    city_checkboxes = "\n".join([
        f'        <div class="city-option" data-name="{html.escape(city["name"], quote=True)}" data-selected="false"><span class="city-check-icon">✓</span><span class="city-name">{html.escape(city["name"])}</span><div class="offset-input"><input type="number" class="candle-offset" value="{city["candle_offset"]}" min="0" max="60" title="דקות לפני השקיעה"><span class="offset-label">ד\'</span></div></div>'
        for city in GEOJSON_CITIES
    ])
    total_cities = len(GEOJSON_CITIES)

    # UI מעוצב ליצירת זְמוּנָה שבת
    # Using CITY_CHECKBOXES_PLACEHOLDER and TOTAL_CITIES_PLACEHOLDER to avoid f-string issues with CSS braces
    html_template = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>יוצר זְמוּנָה לשבת ✡</title>

  <!-- Favicons -->
  <link rel="icon" type="image/x-icon" href="/static/favicon.ico" />
  <link rel="icon" type="image/png" sizes="32x32" href="/static/favicon-32x32.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png" />

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
      padding: 20px 32px 32px 32px;
      border-radius: 24px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      max-width: 520px;
      width: 100%;
    }
    .header {
      text-align: center;
    }
    .logo {
      font-size: 0px;
      margin-bottom: -8px;
    }
    .logo-img {
      width: 200px;
      //height: auto;
      max-width: 100%;
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
    .optional-hint {
      font-size: 12px;
      color: #9e9e9e;
      font-weight: normal;
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
    /* Searchable date dropdown */
    .date-dropdown-container {
      position: relative;
      margin-bottom: 16px;
    }
    .date-dropdown-trigger {
      width: 100%;
      padding: 12px 16px;
      border-radius: 10px;
      border: 2px solid #e8eaf6;
      background: #fff;
      color: #3949ab;
      font-size: 14px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      transition: all 0.2s ease;
      font-family: inherit;
    }
    .date-dropdown-trigger:hover {
      border-color: #c5cae9;
      background: #f5f5ff;
    }
    .date-dropdown-trigger.open {
      border-color: #5c6bc0;
      border-bottom-left-radius: 0;
      border-bottom-right-radius: 0;
    }
    .date-dropdown-trigger .selected-date-info {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
    }
    .date-dropdown-trigger .selected-event-name {
      font-weight: 600;
    }
    .date-dropdown-trigger .selected-event-date {
      font-size: 12px;
      color: #7986cb;
    }
    .date-dropdown-trigger .dropdown-arrow {
      transition: transform 0.2s ease;
    }
    .date-dropdown-trigger.open .dropdown-arrow {
      transform: rotate(180deg);
    }
    .date-dropdown-menu {
      display: none;
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      background: #fff;
      border: 2px solid #5c6bc0;
      border-top: none;
      border-bottom-left-radius: 10px;
      border-bottom-right-radius: 10px;
      max-height: 300px;
      overflow-y: auto;
      z-index: 100;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .date-dropdown-menu.show {
      display: block;
    }
    .date-search-input {
      width: 100%;
      padding: 10px 14px;
      border: none;
      border-bottom: 1px solid #e8eaf6;
      font-size: 14px;
      font-family: inherit;
      background: #fafafa;
    }
    .date-search-input:focus {
      outline: none;
      background: #fff;
    }
    .date-dropdown-list {
      max-height: 240px;
      overflow-y: auto;
    }
    .date-dropdown-item {
      padding: 10px 14px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: background 0.15s ease;
      border-bottom: 1px solid #f5f5f5;
    }
    .date-dropdown-item:hover {
      background: #f5f5ff;
    }
    .date-dropdown-item.selected {
      background: #e8eaf6;
    }
    .date-dropdown-item.hidden {
      display: none;
    }
    .date-dropdown-item .item-name {
      font-weight: 600;
      font-size: 13px;
      color: #3949ab;
    }
    .date-dropdown-item .item-date {
      font-size: 12px;
      color: #7986cb;
    }
    .date-no-results {
      padding: 16px;
      text-align: center;
      color: #999;
      font-size: 13px;
      display: none;
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
    .selected-range-info {
      margin-top: 12px;
      padding: 10px 14px;
      background: #e8f5e9;
      border-radius: 8px;
      font-size: 13px;
      color: #2e7d32;
      display: none;
    }
    .selected-range-info.show {
      display: block;
    }
    /* Date format selector */
    .date-format-section {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid #e0e0e0;
    }
    .date-format-selector {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .date-format-option {
      padding: 8px 16px;
      border-radius: 8px;
      border: 2px solid #e8eaf6;
      background: #fff;
      color: #3949ab;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .date-format-option:hover {
      border-color: #c5cae9;
      background: #f5f5ff;
    }
    .date-format-option.selected {
      border-color: #5c6bc0;
      background: #e8eaf6;
      font-weight: 600;
    }
    /* Manual override section */
    .override-section {
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid #e0e0e0;
    }
    .override-title {
      font-size: 14px;
      font-weight: 600;
      color: #e53935;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .override-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .override-field {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .override-field.full-width {
      grid-column: 1 / -1;
    }
    .override-label {
      font-size: 12px;
      color: #666;
      font-weight: 500;
    }
    .override-input {
      padding: 10px 12px;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      font-size: 14px;
      font-family: inherit;
      direction: rtl;
      transition: border-color 0.15s ease;
    }
    .override-input:focus {
      outline: none;
      border-color: #5c6bc0;
    }
    .override-input::placeholder {
      color: #bbb;
    }
    .override-note {
      font-size: 11px;
      color: #999;
      margin-top: 8px;
      text-align: center;
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
    /* Crop preview */
    .crop-toggle-btn {
      display: none;
      margin-top: 8px;
      background: none;
      border: 1px dashed #7986cb;
      color: #5c6bc0;
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
      width: 100%;
      transition: all 0.2s;
    }
    .crop-toggle-btn:hover {
      background: #e8eaf6;
      border-style: solid;
    }
    .crop-toggle-btn.show {
      display: block;
    }
    .crop-preview-container {
      display: none;
      margin-top: 12px;
      padding: 12px;
      background: #f5f5f5;
      border-radius: 12px;
      border: 2px solid #e8eaf6;
    }
    .crop-preview-container.show {
      display: block;
    }
    .crop-preview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-size: 14px;
      color: #3949ab;
      font-weight: 500;
    }
    .crop-close-btn {
      background: none;
      border: none;
      color: #999;
      cursor: pointer;
      font-size: 18px;
      padding: 0 4px;
      line-height: 1;
    }
    .crop-close-btn:hover {
      color: #666;
    }
    .crop-hint {
      font-size: 12px;
      color: #7986cb;
      font-weight: 400;
    }
    .crop-area-wrapper {
      display: flex;
      justify-content: center;
    }
    .crop-area {
      position: relative;
      width: 200px;
      height: 200px;
      overflow: hidden;
      border-radius: 8px;
      background: #e0e0e0;
      cursor: grab;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .crop-area.no-crop-needed {
      cursor: default;
    }
    .crop-area:active {
      cursor: grabbing;
    }
    .crop-image-wrapper {
      position: absolute;
      top: 0;
      left: 0;
    }
    .crop-image-wrapper img {
      display: block;
      user-select: none;
      -webkit-user-drag: none;
    }
    .crop-overlay {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      pointer-events: none;
      border-radius: 8px;
    }
    /* Poster preview overlay */
    .crop-poster-preview {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      pointer-events: none;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 8px;
      font-family: Arial, sans-serif;
      direction: rtl;
    }
    .crop-poster-top {
      text-align: center;
      text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    }
    .crop-poster-title {
      color: white;
      font-size: 14px;
      font-weight: bold;
      margin-bottom: 2px;
    }
    .crop-poster-subtitle {
      color: rgba(255,255,255,0.9);
      font-size: 8px;
    }
    .crop-poster-bottom {
      text-align: center;
      text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    }
    .crop-poster-city {
      background: rgba(0,0,0,0.4);
      border-radius: 4px;
      padding: 4px 8px;
      margin-bottom: 4px;
      display: inline-block;
    }
    .crop-poster-city-name {
      color: white;
      font-size: 10px;
      font-weight: bold;
    }
    .crop-poster-times {
      color: rgba(255,255,255,0.9);
      font-size: 7px;
    }
    .crop-poster-blessing {
      color: rgba(255,255,255,0.85);
      font-size: 6px;
      margin-top: 4px;
    }
    .crop-area.unsupported {
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: default;
    }
    .crop-area.unsupported .crop-image-wrapper,
    .crop-area.unsupported .crop-overlay,
    .crop-area.unsupported .crop-poster-preview {
      display: none;
    }
    .crop-area.unsupported::after {
      content: "פורמט לא נתמך לתצוגה";
      color: #666;
      font-size: 11px;
      text-align: center;
      padding: 10px;
    }
    .crop-area.no-crop-needed .crop-overlay {
      border: 2px solid #4caf50;
    }
    .crop-no-need-msg {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: rgba(76, 175, 80, 0.9);
      color: white;
      padding: 4px 10px;
      border-radius: 10px;
      font-size: 10px;
      white-space: nowrap;
      z-index: 10;
    }
    .crop-image-nav {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      margin-top: 10px;
    }
    .crop-image-nav button {
      background: #3949ab;
      color: white;
      border: none;
      border-radius: 6px;
      padding: 5px 10px;
      cursor: pointer;
      font-size: 12px;
      transition: background 0.2s;
    }
    .crop-image-nav button:hover:not(:disabled) {
      background: #303f9f;
    }
    .crop-image-nav button:disabled {
      background: #ccc;
      cursor: default;
    }
    .crop-image-nav .nav-indicator {
      font-size: 12px;
      color: #666;
    }
    .crop-actions {
      display: flex;
      justify-content: center;
      gap: 12px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #e0e0e0;
    }
    .crop-done-btn {
      background: #4caf50;
      color: white;
      border: none;
      border-radius: 8px;
      padding: 8px 20px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: background 0.2s;
    }
    .crop-done-btn:hover {
      background: #43a047;
    }
    .crop-remove-btn {
      background: none;
      color: #e53935;
      border: 1px solid #e53935;
      border-radius: 8px;
      padding: 8px 16px;
      cursor: pointer;
      font-size: 13px;
      transition: all 0.2s;
    }
    .crop-remove-btn:hover {
      background: #ffebee;
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
      gap: 4px;
      background: #e8eaf6;
      border: 1px solid #c5cae9;
      border-radius: 16px;
      padding: 4px 8px;
      font-size: 13px;
      color: #3949ab;
    }
    .city-chip .chip-order {
      display: flex;
      flex-direction: column;
      gap: 0;
      margin-left: 2px;
    }
    .city-chip .chip-order-btn {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 8px;
      color: #7986cb;
      padding: 0;
      line-height: 1;
      transition: color 0.15s ease;
    }
    .city-chip .chip-order-btn:hover {
      color: #3949ab;
    }
    .city-chip .chip-order-btn:disabled {
      color: #ccc;
      cursor: default;
    }
    .city-chip .chip-name {
      max-width: 90px;
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
    .city-option .city-check-icon {
      width: 16px;
      height: 16px;
      border-radius: 4px;
      border: 2px solid #c5cae9;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      color: transparent;
      transition: all 0.15s ease;
      flex-shrink: 0;
    }
    .city-option.checked .city-check-icon {
      background: #3949ab;
      border-color: #3949ab;
      color: #fff;
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
      align-items: center;
      gap: 2px;
      margin-right: auto;
    }
    .city-option.checked .offset-input {
      display: flex;
    }
    .candle-offset {
      width: 36px;
      padding: 3px 2px;
      border: 1px solid #c5cae9;
      border-radius: 4px;
      font-size: 11px;
      text-align: center;
      background: #fff;
    }
    .candle-offset:focus {
      outline: none;
      border-color: #5c6bc0;
    }
    .offset-label {
      font-size: 10px;
      color: #7986cb;
    }
    .no-results {
      grid-column: 1 / -1;
      text-align: center;
      color: #999;
      padding: 16px;
      font-size: 13px;
    }
    .city-counter {
      font-weight: 400;
      font-size: 13px;
      color: #7986cb;
    }
    .city-counter.at-limit {
      color: #e53935;
      font-weight: 600;
    }
    /* Custom city section */
    .custom-city-section {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid #eee;
    }
    .custom-city-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .custom-city-title {
      font-size: 13px;
      font-weight: 600;
      color: #e53935;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .add-custom-city-btn {
      padding: 6px 12px;
      border-radius: 6px;
      border: 1px dashed #c5cae9;
      background: #f5f5ff;
      color: #3949ab;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.15s ease;
      font-family: inherit;
    }
    .add-custom-city-btn:hover {
      border-color: #5c6bc0;
      background: #ede7f6;
    }
    .custom-cities-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .custom-city-entry {
      display: grid;
      grid-template-columns: 1fr 80px 80px auto;
      gap: 8px;
      align-items: center;
      padding: 8px;
      background: #fff5f5;
      border-radius: 8px;
      border: 1px solid #ffcdd2;
    }
    .custom-city-input {
      padding: 8px;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      font-size: 13px;
      font-family: inherit;
      direction: rtl;
    }
    .custom-city-input:focus {
      outline: none;
      border-color: #5c6bc0;
    }
    .custom-city-input::placeholder {
      color: #bbb;
    }
    .remove-custom-city-btn {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      border: none;
      background: #ffebee;
      color: #e53935;
      font-size: 16px;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .remove-custom-city-btn:hover {
      background: #e53935;
      color: #fff;
    }
    @media (max-width: 500px) {
      .custom-city-entry {
        grid-template-columns: 1fr auto;
      }
      .custom-city-entry .custom-city-input:nth-child(2),
      .custom-city-entry .custom-city-input:nth-child(3) {
        grid-column: 1 / 2;
      }
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
      font-family: inherit;
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
    .preview-gallery {
      display: grid;
      gap: 16px;
    }
    .preview-gallery.single {
      grid-template-columns: 1fr;
    }
    .preview-gallery.multiple {
      grid-template-columns: repeat(2, 1fr);
    }
    .preview-gallery-item {
      position: relative;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 6px 20px rgba(0,0,0,0.12);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .preview-gallery-item:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(0,0,0,0.18);
    }
    .preview-gallery-item img {
      width: 100%;
      height: auto;
      display: block;
    }
    .preview-gallery-item .poster-label {
      position: absolute;
      bottom: 8px;
      right: 8px;
      background: rgba(0,0,0,0.7);
      color: #fff;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
    }
    .preview-gallery.single .poster-label {
      display: none;
    }
    @media (max-width: 480px) {
      .preview-gallery.multiple {
        grid-template-columns: 1fr;
      }
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
    /* Copy link button */
    .btn-copy-link {
      margin-top: 12px;
      width: 100%;
      padding: 12px 16px;
      border-radius: 10px;
      border: 2px solid #c5cae9;
      background: #f5f5ff;
      color: #3949ab;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-family: inherit;
    }
    .btn-copy-link:hover {
      border-color: #5c6bc0;
      background: #ede7f6;
    }
    .btn-copy-link.copied {
      border-color: #4caf50;
      background: #e8f5e9;
      color: #2e7d32;
    }
    .copy-link-hint {
      margin-top: 8px;
      font-size: 12px;
      color: #7986cb;
      text-align: center;
    }
    .url-params-notice {
      margin-top: 16px;
      padding: 12px 16px;
      border-radius: 10px;
      background: #fff3e0;
      border: 1px solid #ffe0b2;
      font-size: 13px;
      color: #e65100;
      display: none;
    }
    .url-params-notice.show {
      display: block;
    }
    .url-params-notice .clear-params {
      color: #e65100;
      text-decoration: underline;
      cursor: pointer;
      margin-right: 8px;
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
      <div class="logo"><img src="/static/watermark.png" alt="לוגו" class="logo-img" /></div>
      <h1>יוצר זְמוּנָה לשבת וחג</h1>
      <div class="subtitle">צרי זְמוּנָה יפה עם זמני הדלקת נרות לשבת או לחג</div>
      <div class="subtitle" style="font-size: 11px; opacity: 0.7;">זְמוּנָה = זְמַן + תְּמוּנָה 🕐🖼️</div>
    </div>

    <div class="form-group">
      <label>תמונת רקע <span class="optional">(לא חובה)</span></label>
      <div class="file-upload-wrapper">
        <input type="file" id="imageFile" class="file-input-hidden" accept="image/*" multiple />
        <button type="button" id="fileUploadBtn" class="file-upload-btn">
          <span>📷</span> העלה תמונה
        </button>
        <div id="fileName" class="file-name">
          <span id="fileNameText"></span>
          <button type="button" class="clear-file" id="clearFileBtn" title="הסר קובץ">✕</button>
        </div>
      </div>
      <!-- Image crop toggle button -->
      <button type="button" id="cropToggleBtn" class="crop-toggle-btn">✂️ התאם חיתוך תמונה</button>
      <!-- Image crop preview -->
      <div id="cropPreviewContainer" class="crop-preview-container">
        <div class="crop-preview-header">
          <div>
            <span>📐 כיוון החיתוך</span>
            <span class="crop-hint" id="cropHintText">גרור את התמונה לבחירת האזור</span>
          </div>
          <button type="button" id="cropCloseBtn" class="crop-close-btn" title="סגור">✕</button>
        </div>
        <div class="crop-area-wrapper">
          <div id="cropArea" class="crop-area">
            <div id="cropImageWrapper" class="crop-image-wrapper">
              <img id="cropPreviewImage" alt="תצוגה מקדימה" />
            </div>
            <div class="crop-overlay"></div>
            <!-- Poster preview overlay -->
            <div class="crop-poster-preview">
              <div class="crop-poster-top">
                <div class="crop-poster-title">שבת שלום</div>
                <div class="crop-poster-subtitle">פרשת ... | תאריך</div>
              </div>
              <div class="crop-poster-bottom">
                <div class="crop-poster-city">
                  <div class="crop-poster-city-name">🏙️ עיר</div>
                  <div class="crop-poster-times">🕯️ 00:00 &nbsp; ✨ 00:00</div>
                </div>
                <div class="crop-poster-blessing">שבת שלום ומבורך</div>
              </div>
            </div>
            <div id="noCropMsg" class="crop-no-need-msg" style="display: none;">✓ מרובעת</div>
          </div>
        </div>
        <div id="cropImageNav" class="crop-image-nav" style="display: none;">
          <button type="button" id="cropPrevBtn">◀ הקודם</button>
          <span class="nav-indicator"><span id="cropCurrentNum">1</span> / <span id="cropTotalNum">1</span></span>
          <button type="button" id="cropNextBtn">הבא ▶</button>
        </div>
        <div class="crop-actions">
          <button type="button" id="cropDoneBtn" class="crop-done-btn">✓ סיימתי</button>
          <button type="button" id="cropRemoveBtn" class="crop-remove-btn">🗑️ הסר תמונה</button>
        </div>
      </div>
      <div class="hint" id="uploadHint">השאר ריק לשימוש בתמונת ברירת המחדל</div>
    </div>

    <div class="form-group" id="blessingGroup">
      <div id="blessingSection" class="dedication-section show">
        <div class="dedication-header">
          <label for="message">✨ ברכה לזְמוּנָה <span class="optional-hint">(לא חובה)</span></label>
        </div>
        <textarea id="message" placeholder="למשל: לחיי שמחות קטנות וגדולות"></textarea>
        <div class="hint">💡 אין צורך לכתוב "שבת שלום" - זו כבר הכותרת הראשית של הזְמוּנָה</div>
      </div>
    </div>

    <div class="form-group" id="dedicationGroup">
      <div id="dedicationSection" class="dedication-section show">
        <div class="dedication-header">
          <label for="neshama">🕯️ לעילוי נשמת <span class="optional-hint">(לא חובה)</span></label>
        </div>
        <input id="neshama" type="text" placeholder="למשל: אורי בורנשטיין הי״ד" />
      </div>
    </div>

    <div class="form-group">
      <label>בחר ערים ויישובים <span id="cityCounter" class="city-counter">(0/8)</span></label>
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

        <!-- Custom City Section -->
        <div class="custom-city-section">
          <div class="custom-city-header">
            <span class="custom-city-title">✏️ ערים מותאמות אישית</span>
            <button type="button" id="addCustomCityBtn" class="add-custom-city-btn">+ הוסף עיר</button>
          </div>
          <div id="customCitiesList" class="custom-cities-list"></div>
        </div>
      </div>
    </div>

    <!-- Date Format Selector (Main Menu) -->
    <div class="form-group">
      <label>🗓️ פורמט תאריך בזְמוּנָה</label>
      <div id="dateFormatSelector" class="date-format-selector">
        <div class="date-format-option" data-format="gregorian">לועזי</div>
        <div class="date-format-option" data-format="hebrew">עברי</div>
        <div class="date-format-option selected" data-format="both">לועזי + עברי</div>
      </div>
    </div>

    <!-- Advanced Options Toggle -->
    <button type="button" id="advancedToggle" class="advanced-toggle">
      <span>⚙️ אפשרויות מתקדמות</span>
      <span class="arrow">▼</span>
    </button>

    <div id="advancedSection" class="advanced-section">
      <div class="advanced-title">📅 בחירת תאריך התחלה</div>

      <!-- Searchable Date Dropdown -->
      <div class="date-dropdown-container">
        <button type="button" id="dateDropdownTrigger" class="date-dropdown-trigger">
          <div class="selected-date-info">
            <span class="selected-event-name" id="selectedEventName">⏳ טוען...</span>
            <span class="selected-event-date" id="selectedEventDate"></span>
          </div>
          <span class="dropdown-arrow">▼</span>
        </button>
        <div id="dateDropdownMenu" class="date-dropdown-menu">
          <input type="text" id="dateSearchInput" class="date-search-input" placeholder="🔍 חפש לפי פרשה או תאריך..." />
          <div id="dateDropdownList" class="date-dropdown-list">
            <!-- Items will be populated by JavaScript -->
          </div>
          <div id="dateNoResults" class="date-no-results">לא נמצאו תוצאות</div>
        </div>
      </div>

      <div class="weeks-selector">
        <label>מספר שבתות/חגים קדימה:</label>
        <input type="number" id="weeksAhead" class="weeks-input" min="1" max="20" value="1" />
      </div>

      <div id="selectedRangeInfo" class="selected-range-info"></div>

      <!-- Manual Override Section -->
      <div class="override-section">
        <div class="override-title">✏️ דריסה ידנית (אופציונלי)</div>
        <div class="override-grid">
          <div class="override-field full-width">
            <label class="override-label">כותרת ראשית</label>
            <input type="text" id="overrideMainTitle" class="override-input" placeholder="לדוגמה: שבת שלום, חג שמח, שנה טובה" />
          </div>
          <div class="override-field full-width">
            <label class="override-label">כותרת משנית (פרשה + תאריך)</label>
            <input type="text" id="overrideSubtitle" class="override-input" placeholder="לדוגמה: פרשת וישלח | 13-14.12.2025" />
          </div>
        </div>
        <div class="override-note">💡 שדות ריקים ישתמשו בערכים האוטומטיים</div>
      </div>
    </div>

    <button id="generateBtn" class="btn-generate">
      <span class="btn-text">✨ צור זְמוּנָה</span>
      <div class="spinner"></div>
    </button>

    <button id="copyLinkBtn" class="btn-copy-link">
      <span id="copyLinkIcon">📋</span>
      <span id="copyLinkText">העתק קישור אישי</span>
    </button>
    <div class="copy-link-hint">🔗 יוצר קישור עם הערים והברכות שבחרת - שלח לאחרים או שמור לעצמך לשימוש חוזר</div>

    <div id="urlParamsNotice" class="url-params-notice">
      ⚠️ הטופס מולא אוטומטית מהקישור
      <span class="clear-params" id="clearParamsBtn">נקה והתחל מחדש</span>
    </div>

    <div id="status" class="status"></div>

    <div class="preview" id="preview">
      <div class="divider"></div>
      <div class="preview-header">
        <h3 class="preview-title" id="previewTitle">🎉 הזְמוּנָה מוכנה!</h3>
        <button id="downloadBtn" class="btn-download">
          <span>⬇️</span> <span id="downloadBtnText">הורד תמונה</span>
        </button>
      </div>
      <div class="preview-gallery" id="previewGallery">
        <!-- Gallery items will be added dynamically -->
      </div>
    </div>

    <div class="footer">
      לזכר אורי בורנשטיין הי״ד 🕯️
    </div>
  </div>

  <script>
    const btn = document.getElementById("generateBtn");
    const downloadBtn = document.getElementById("downloadBtn");
    const downloadBtnText = document.getElementById("downloadBtnText");
    const statusEl = document.getElementById("status");
    const previewEl = document.getElementById("preview");
    const previewTitle = document.getElementById("previewTitle");
    const previewGallery = document.getElementById("previewGallery");
    const fileInput = document.getElementById("imageFile");
    const fileUploadBtn = document.getElementById("fileUploadBtn");
    const fileNameEl = document.getElementById("fileName");
    const fileNameText = document.getElementById("fileNameText");
    const clearFileBtn = document.getElementById("clearFileBtn");
    const advancedToggle = document.getElementById("advancedToggle");
    const advancedSection = document.getElementById("advancedSection");
    const weeksAhead = document.getElementById("weeksAhead");
    const citySearch = document.getElementById("citySearch");
    const citiesGrid = document.getElementById("citiesGrid");
    const citiesGridWrapper = document.getElementById("citiesGridWrapper");
    const selectedChips = document.getElementById("selectedChips");
    const showAllCitiesBtn = document.getElementById("showAllCitiesBtn");
    const noResults = document.getElementById("noResults");
    const cityOptions = document.querySelectorAll(".city-option");
    const neshamaInput = document.getElementById("neshama");
    const messageInput = document.getElementById("message");
    const MAX_CITIES = 8;
    const dateFormatSelector = document.getElementById("dateFormatSelector");
    const copyLinkBtn = document.getElementById("copyLinkBtn");
    const copyLinkIcon = document.getElementById("copyLinkIcon");
    const copyLinkText = document.getElementById("copyLinkText");
    const urlParamsNotice = document.getElementById("urlParamsNotice");
    const clearParamsBtn = document.getElementById("clearParamsBtn");

    // Date dropdown elements
    const dateDropdownTrigger = document.getElementById("dateDropdownTrigger");
    const dateDropdownMenu = document.getElementById("dateDropdownMenu");
    const dateSearchInput = document.getElementById("dateSearchInput");
    const dateDropdownList = document.getElementById("dateDropdownList");
    const dateNoResults = document.getElementById("dateNoResults");

    // Manual override elements
    const overrideMainTitle = document.getElementById("overrideMainTitle");
    const overrideSubtitle = document.getElementById("overrideSubtitle");
    const selectedEventName = document.getElementById("selectedEventName");
    const selectedEventDate = document.getElementById("selectedEventDate");
    const selectedRangeInfo = document.getElementById("selectedRangeInfo");

    // Custom city elements
    const addCustomCityBtn = document.getElementById("addCustomCityBtn");
    const customCitiesList = document.getElementById("customCitiesList");

    // Crop preview elements
    const cropToggleBtn = document.getElementById("cropToggleBtn");
    const cropCloseBtn = document.getElementById("cropCloseBtn");
    const cropDoneBtn = document.getElementById("cropDoneBtn");
    const cropRemoveBtn = document.getElementById("cropRemoveBtn");
    const cropPreviewContainer = document.getElementById("cropPreviewContainer");
    const cropArea = document.getElementById("cropArea");
    const cropImageWrapper = document.getElementById("cropImageWrapper");
    const cropPreviewImage = document.getElementById("cropPreviewImage");
    const cropHintText = document.getElementById("cropHintText");
    const noCropMsg = document.getElementById("noCropMsg");
    const cropImageNav = document.getElementById("cropImageNav");
    const cropPrevBtn = document.getElementById("cropPrevBtn");
    const cropNextBtn = document.getElementById("cropNextBtn");
    const cropCurrentNum = document.getElementById("cropCurrentNum");
    const cropTotalNum = document.getElementById("cropTotalNum");

    let currentBlobUrls = []; // Array of blob URLs to revoke
    let selectedDates = []; // Array of selected dates
    let allEvents = []; // Store all events
    let selectedStartIndex = 0; // Index of the selected start date
    let selectedDateFormat = "both"; // "gregorian", "hebrew", or "both" - default is both
    let loadedFromUrl = false; // Track if form was pre-filled from URL

    // Crop state - stores crop position (0-1) for each image
    let imageCropPositions = []; // Array of { x: 0.5, y: 0.5 } for each image
    let currentCropIndex = 0; // Which image is currently being cropped
    let uploadedFiles = []; // Store references to uploaded files for navigation

    // Ordered list of selected cities (maintains user-defined order)
    let orderedSelectedCities = []; // Array of city names in user's preferred order

    // Date format selector
    dateFormatSelector.querySelectorAll('.date-format-option').forEach(opt => {
      opt.addEventListener('click', () => {
        dateFormatSelector.querySelectorAll('.date-format-option').forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        selectedDateFormat = opt.dataset.format;
      });
    });

    // Advanced options toggle
    advancedToggle.addEventListener("click", () => {
      advancedToggle.classList.toggle("open");
      advancedSection.classList.toggle("show");
    });

    // ===== Date Dropdown Functionality =====

    // Toggle dropdown
    dateDropdownTrigger.addEventListener("click", () => {
      dateDropdownTrigger.classList.toggle("open");
      dateDropdownMenu.classList.toggle("show");
      if (dateDropdownMenu.classList.contains("show")) {
        dateSearchInput.focus();
      }
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".date-dropdown-container")) {
        dateDropdownTrigger.classList.remove("open");
        dateDropdownMenu.classList.remove("show");
      }
    });

    // Search functionality
    dateSearchInput.addEventListener("input", () => {
      const query = dateSearchInput.value.trim().toLowerCase();
      let hasResults = false;

      dateDropdownList.querySelectorAll(".date-dropdown-item").forEach(item => {
        const name = (item.dataset.name || "").toLowerCase();
        const parsha = (item.dataset.parsha || "").toLowerCase();
        const dateStr = (item.dataset.datestr || "").toLowerCase();

        if (name.includes(query) || parsha.includes(query) || dateStr.includes(query)) {
          item.classList.remove("hidden");
          hasResults = true;
        } else {
          item.classList.add("hidden");
        }
      });

      dateNoResults.style.display = hasResults ? "none" : "block";
    });

    // Update selected dates based on start index and weeks
    function updateSelectedDates() {
      const weeks = parseInt(weeksAhead.value) || 1;
      selectedDates = [];

      for (let i = 0; i < weeks && (selectedStartIndex + i) < allEvents.length; i++) {
        selectedDates.push(allEvents[selectedStartIndex + i].startDate);
      }

      // Update the range info display
      if (selectedDates.length > 1) {
        const startEvent = allEvents[selectedStartIndex];
        const endEvent = allEvents[selectedStartIndex + selectedDates.length - 1];
        selectedRangeInfo.textContent = `📋 ייווצרו ${selectedDates.length} זְמוּנוֹת: מ-${startEvent.displayName} (${startEvent.dateStr}) עד ${endEvent.displayName} (${endEvent.dateStr})`;
        selectedRangeInfo.classList.add("show");
      } else {
        selectedRangeInfo.classList.remove("show");
      }

      // Update dropdown item selection visual
      dateDropdownList.querySelectorAll(".date-dropdown-item").forEach((item, idx) => {
        item.classList.toggle("selected", idx === selectedStartIndex);
      });

      if (typeof updateUploadHint === 'function') updateUploadHint();
    }

    // Select a date from dropdown
    function selectDate(index) {
      selectedStartIndex = index;
      const event = allEvents[index];

      // Update trigger display
      selectedEventName.textContent = event.displayName;
      selectedEventDate.textContent = event.dateStr;

      // Close dropdown
      dateDropdownTrigger.classList.remove("open");
      dateDropdownMenu.classList.remove("show");
      dateSearchInput.value = "";

      // Show all items again
      dateDropdownList.querySelectorAll(".date-dropdown-item").forEach(item => {
        item.classList.remove("hidden");
      });
      dateNoResults.style.display = "none";

      updateSelectedDates();
    }

    // Load upcoming events for date selection
    async function loadUpcomingEvents() {
      try {
        const resp = await fetch("/upcoming-events");
        allEvents = await resp.json();

        // Populate dropdown list
        dateDropdownList.innerHTML = allEvents.map((event, i) => `
          <div class="date-dropdown-item ${i === 0 ? 'selected' : ''}"
               data-index="${i}"
               data-date="${event.startDate}"
               data-name="${event.displayName}"
               data-parsha="${event.parsha || ''}"
               data-datestr="${event.dateStr}">
            <span class="item-name">${event.displayName}</span>
            <span class="item-date">${event.dateStr}</span>
          </div>
        `).join('');

        // Update trigger with first event
        if (allEvents.length > 0) {
          selectedEventName.textContent = allEvents[0].displayName;
          selectedEventDate.textContent = allEvents[0].dateStr;
        }

        // First event is selected by default
        selectedStartIndex = 0;
        selectedDates = [allEvents[0].startDate];

        // Add click handlers for dropdown items
        dateDropdownList.querySelectorAll('.date-dropdown-item').forEach((item, index) => {
          item.addEventListener('click', () => selectDate(index));
        });

      } catch (err) {
        console.error("Failed to load events:", err);
        selectedEventName.textContent = "שבת/חג הקרוב";
        selectedEventDate.textContent = "";
        selectedDates = [""];
      }
    }
    loadUpcomingEvents();

    // Weeks selector - update dates from selected start
    weeksAhead.addEventListener("change", () => {
      updateSelectedDates();
    });

    // Helper to escape attribute value for CSS selector
    function escapeAttrForSelector(val) {
      return val.replace(/"/g, '\\"');
    }

    // Render selected cities as chips (using ordered list)
    function renderChips() {
      // Sync orderedSelectedCities with currently checked cities
      const checkedCities = Array.from(document.querySelectorAll('.city-option.checked')).map(opt => opt.dataset.name);

      // Add any newly checked cities that aren't in the ordered list
      checkedCities.forEach(name => {
        if (!orderedSelectedCities.includes(name)) {
          orderedSelectedCities.push(name);
        }
      });

      // Remove any cities from ordered list that are no longer checked
      orderedSelectedCities = orderedSelectedCities.filter(name => checkedCities.includes(name));

      // Render chips in the user's preferred order
      selectedChips.innerHTML = orderedSelectedCities.map((name, index) => {
        const opt = document.querySelector(`.city-option[data-name="${escapeAttrForSelector(name)}"]`);
        const displayName = opt ? opt.querySelector('.city-name').textContent : name;
        const isFirst = index === 0;
        const isLast = index === orderedSelectedCities.length - 1;

        return `<span class="city-chip" data-name="${name}">
          <span class="chip-order">
            <button type="button" class="chip-order-btn chip-move-up" title="הזז למעלה" ${isFirst ? 'disabled' : ''}>▲</button>
            <button type="button" class="chip-order-btn chip-move-down" title="הזז למטה" ${isLast ? 'disabled' : ''}>▼</button>
          </span>
          <span class="chip-name">${displayName}</span>
          <span class="chip-remove">✕</span>
        </span>`;
      }).join('');

      // Add click handlers for move up/down
      selectedChips.querySelectorAll('.chip-move-up').forEach(btn => {
        btn.addEventListener('click', () => {
          const chip = btn.closest('.city-chip');
          const name = chip.dataset.name;
          const index = orderedSelectedCities.indexOf(name);
          if (index > 0) {
            // Swap with previous
            [orderedSelectedCities[index - 1], orderedSelectedCities[index]] =
              [orderedSelectedCities[index], orderedSelectedCities[index - 1]];
            renderChips();
          }
        });
      });

      selectedChips.querySelectorAll('.chip-move-down').forEach(btn => {
        btn.addEventListener('click', () => {
          const chip = btn.closest('.city-chip');
          const name = chip.dataset.name;
          const index = orderedSelectedCities.indexOf(name);
          if (index < orderedSelectedCities.length - 1) {
            // Swap with next
            [orderedSelectedCities[index], orderedSelectedCities[index + 1]] =
              [orderedSelectedCities[index + 1], orderedSelectedCities[index]];
            renderChips();
          }
        });
      });

      // Add click handlers to remove chips
      selectedChips.querySelectorAll('.chip-remove').forEach(btn => {
        btn.addEventListener('click', () => {
          const name = btn.closest('.city-chip').dataset.name;
          // Remove from ordered list
          orderedSelectedCities = orderedSelectedCities.filter(n => n !== name);
          // Uncheck the option
          const opt = document.querySelector(`.city-option[data-name="${escapeAttrForSelector(name)}"]`);
          if (opt) { opt.classList.remove('checked'); opt.dataset.selected = 'false'; }
          renderChips();
          updateCityLimit();
        });
      });
    }

    // Get total cities count (predefined + custom)
    function getTotalCitiesCount() {
      const predefinedCount = document.querySelectorAll('.city-option.checked').length;
      const customCount = customCitiesList.querySelectorAll('.custom-city-entry').length;
      return predefinedCount + customCount;
    }

    // City counter element
    const cityCounter = document.getElementById("cityCounter");

    // Enforce max limit
    function updateCityLimit() {
      const total = getTotalCitiesCount();
      const atLimit = total >= MAX_CITIES;

      // Update counter display
      cityCounter.textContent = `(${total}/${MAX_CITIES})`;
      cityCounter.classList.toggle("at-limit", atLimit);

      // Disable unchecked predefined cities
      cityOptions.forEach(opt => {
        if (!opt.classList.contains('checked')) {
          opt.classList.toggle("disabled", atLimit);
        }
      });

      // Disable/enable add custom city button
      addCustomCityBtn.disabled = atLimit;
      addCustomCityBtn.style.opacity = atLimit ? "0.5" : "1";
      addCustomCityBtn.style.cursor = atLimit ? "not-allowed" : "pointer";
    }

    // ===== URL Query Parameters Support =====

    // Generate shareable URL with current form values
    function generateShareableUrl() {
      const params = new URLSearchParams();

      // Add selected cities
      const selectedCityNames = Array.from(document.querySelectorAll('.city-option.checked'))
        .map(opt => opt.dataset.name);
      if (selectedCityNames.length > 0) {
        params.set('cities', selectedCityNames.join(','));
      }

      // Add message if present
      if (messageInput.value.trim()) {
        params.set('message', messageInput.value.trim());
      }

      // Add neshama if present
      if (neshamaInput.value.trim()) {
        params.set('neshama', neshamaInput.value.trim());
      }

      // Add date format if not default (default is now "both")
      if (selectedDateFormat !== 'both') {
        params.set('dateFormat', selectedDateFormat);
      }

      const url = window.location.origin + window.location.pathname;
      const queryString = params.toString();
      return queryString ? `${url}?${queryString}` : url;
    }

    // Copy link button handler
    copyLinkBtn.addEventListener("click", async () => {
      const url = generateShareableUrl();
      try {
        await navigator.clipboard.writeText(url);
        copyLinkBtn.classList.add("copied");
        copyLinkIcon.textContent = "✅";
        copyLinkText.textContent = "הקישור הועתק!";
        setTimeout(() => {
          copyLinkBtn.classList.remove("copied");
          copyLinkIcon.textContent = "📋";
          copyLinkText.textContent = "העתק קישור אישי";
        }, 2000);
      } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement("textarea");
        textArea.value = url;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        copyLinkBtn.classList.add("copied");
        copyLinkIcon.textContent = "✅";
        copyLinkText.textContent = "הקישור הועתק!";
        setTimeout(() => {
          copyLinkBtn.classList.remove("copied");
          copyLinkIcon.textContent = "📋";
          copyLinkText.textContent = "העתק קישור אישי";
        }, 2000);
      }
    });

    // Read URL params and pre-fill form on page load
    // Default cities to pre-select when no URL params
    const DEFAULT_CITIES = ['ירושלים', 'תל אביב -יפו', 'חיפה', 'באר שבע'];

    function loadFromUrlParams() {
      const urlParams = new URLSearchParams(window.location.search);
      let hasParams = false;

      // Pre-select cities from URL, or use defaults if no cities param
      const citiesParam = urlParams.get('cities');
      const cityNames = citiesParam
        ? citiesParam.split(',').map(c => decodeURIComponent(c.trim()))
        : DEFAULT_CITIES;

      cityNames.forEach(name => {
        const opt = document.querySelector(`.city-option[data-name="${escapeAttrForSelector(name)}"]`);
        if (opt) {
          opt.classList.add('checked');
          opt.dataset.selected = 'true';
          if (citiesParam) hasParams = true; // Only mark as URL param if explicitly set
        }
      });
      renderChips();
      updateCityLimit();

      // Pre-fill message
      const messageParam = urlParams.get('message');
      if (messageParam) {
        messageInput.value = decodeURIComponent(messageParam);
        hasParams = true;
      }

      // Pre-fill leiluy neshama
      const neshamaParam = urlParams.get('neshama');
      if (neshamaParam) {
        neshamaInput.value = decodeURIComponent(neshamaParam);
        hasParams = true;
      }

      // Set date format
      const dateFormatParam = urlParams.get('dateFormat');
      if (dateFormatParam && ['gregorian', 'hebrew', 'both'].includes(dateFormatParam)) {
        selectedDateFormat = dateFormatParam;
        dateFormatSelector.querySelectorAll('.date-format-option').forEach(opt => {
          opt.classList.toggle('selected', opt.dataset.format === dateFormatParam);
        });
        hasParams = true;
      }

      // Show notice if form was pre-filled
      if (hasParams) {
        loadedFromUrl = true;
        urlParamsNotice.classList.add("show");
      }
    }

    // Clear URL params and reset form
    clearParamsBtn.addEventListener("click", () => {
      // Clear URL without reloading
      window.history.replaceState({}, document.title, window.location.pathname);

      // Reset cities to defaults
      document.querySelectorAll('.city-option.checked').forEach(opt => {
        opt.classList.remove('checked');
        opt.dataset.selected = 'false';
      });
      // Re-select default cities
      DEFAULT_CITIES.forEach(name => {
        const opt = document.querySelector(`.city-option[data-name="${escapeAttrForSelector(name)}"]`);
        if (opt) {
          opt.classList.add('checked');
          opt.dataset.selected = 'true';
        }
      });
      renderChips();
      updateCityLimit();

      // Reset message and neshama
      messageInput.value = "";
      neshamaInput.value = "";

      // Reset date format to default (both)
      selectedDateFormat = "both";
      dateFormatSelector.querySelectorAll('.date-format-option').forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.format === 'both');
      });

      // Hide notice
      urlParamsNotice.classList.remove("show");
      loadedFromUrl = false;
    });

    // Load from URL params on page load
    loadFromUrlParams();

    // ===== End URL Query Parameters Support =====

    // Show all cities toggle
    showAllCitiesBtn.addEventListener("click", () => {
      showAllCitiesBtn.classList.toggle("open");
      citiesGridWrapper.classList.toggle("show");
      showAllCitiesBtn.querySelector("span:first-child").textContent =
        citiesGridWrapper.classList.contains("show") ? "הסתר רשימה" : "הצג את כל הערים";
    });

    // Make entire city option clickable
    cityOptions.forEach(opt => {
      opt.addEventListener("click", (e) => {
        if (e.target.classList.contains("candle-offset")) return;
        if (opt.classList.contains('disabled') && !opt.classList.contains('checked')) return;
        const isChecked = opt.classList.toggle("checked");
        opt.dataset.selected = isChecked ? 'true' : 'false';
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

    // Custom city functionality
    let customCityCounter = 0;

    function addCustomCityEntry() {
      // Check limit before adding
      if (getTotalCitiesCount() >= MAX_CITIES) return;

      customCityCounter++;
      const entry = document.createElement("div");
      entry.className = "custom-city-entry";
      entry.dataset.customId = customCityCounter;
      entry.innerHTML = `
        <input type="text" class="custom-city-input custom-city-name" placeholder="שם העיר" />
        <input type="text" class="custom-city-input custom-city-candle" placeholder="הדלקה" dir="ltr" />
        <input type="text" class="custom-city-input custom-city-havdalah" placeholder="הבדלה" dir="ltr" />
        <button type="button" class="remove-custom-city-btn" title="הסר עיר">×</button>
      `;
      customCitiesList.appendChild(entry);

      // Add remove handler
      entry.querySelector(".remove-custom-city-btn").addEventListener("click", () => {
        entry.remove();
        updateCityLimit(); // Re-check limit after removal
      });

      updateCityLimit(); // Check limit after adding
    }

    addCustomCityBtn.addEventListener("click", addCustomCityEntry);

    // Get custom cities data
    function getCustomCities() {
      const entries = customCitiesList.querySelectorAll(".custom-city-entry");
      const customCities = [];
      entries.forEach(entry => {
        const name = entry.querySelector(".custom-city-name").value.trim();
        const candle = entry.querySelector(".custom-city-candle").value.trim();
        const havdalah = entry.querySelector(".custom-city-havdalah").value.trim();
        if (name) {
          customCities.push({ name, candle, havdalah });
        }
      });
      return customCities;
    }

    const uploadHint = document.getElementById("uploadHint");

    // Update upload hint based on selected dates
    function updateUploadHint() {
      const count = selectedDates.length;
      if (count > 1) {
        uploadHint.textContent = `ניתן להעלות עד ${count} תמונות - אחת לכל זְמוּנָה. אם תעלי פחות, התמונה האחרונה תשמש לשאר.`;
        uploadHint.style.color = "#5c6bc0";
      } else {
        uploadHint.textContent = "השאר ריק לשימוש בתמונת ברירת המחדל";
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
        uploadedFiles = Array.from(fileInput.files);

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

        // Initialize crop positions for all images (centered by default)
        imageCropPositions = Array(count).fill(null).map(() => ({ x: 0.5, y: 0.5 }));
        currentCropIndex = 0;

        // Auto-set weeks ahead to match number of images
        if (count > 1) {
          weeksAhead.value = count;
          updateSelectedDates();
        }

        // Show/hide navigation
        if (count > 1) {
          cropImageNav.style.display = 'flex';
          cropTotalNum.textContent = count;
          updateCropNavButtons();
        } else {
          cropImageNav.style.display = 'none';
        }

        // Show toggle button (not the preview itself)
        cropToggleBtn.classList.add("show");
        cropPreviewContainer.classList.remove("show");

        // Pre-load the first image for crop preview
        preloadCropPreview(fileInput.files[0], 0);
      }
    });

    // Clear selected files
    clearFileBtn.addEventListener("click", () => {
      fileInput.value = "";
      fileNameEl.classList.remove("show");
      fileUploadBtn.classList.remove("has-file");
      fileUploadBtn.innerHTML = "<span>📷</span> העלה תמונה";
      cropPreviewContainer.classList.remove("show");
      cropToggleBtn.classList.remove("show");
      cropImageNav.style.display = 'none';
      imageCropPositions = [];
      uploadedFiles = [];
    });

    // Crop toggle/close buttons
    cropToggleBtn.addEventListener('click', () => {
      cropPreviewContainer.classList.add("show");
      cropToggleBtn.classList.remove("show");
      // Show the first image
      if (uploadedFiles.length > 0) {
        showCropPreview(uploadedFiles[0], 0);
      }
    });

    // Close button (X) - just hides the panel
    cropCloseBtn.addEventListener('click', () => {
      cropPreviewContainer.classList.remove("show");
      cropToggleBtn.classList.add("show");
    });

    // Done button - confirms and closes
    cropDoneBtn.addEventListener('click', () => {
      cropPreviewContainer.classList.remove("show");
      cropToggleBtn.textContent = '✓ חיתוך הוגדר';
      cropToggleBtn.style.borderColor = '#4caf50';
      cropToggleBtn.style.color = '#4caf50';
      cropToggleBtn.classList.add("show");
    });

    // Remove image button - removes only the current image
    cropRemoveBtn.addEventListener('click', () => {
      if (uploadedFiles.length <= 1) {
        // Last image - clear everything
        fileInput.value = "";
        fileNameEl.classList.remove("show");
        fileUploadBtn.classList.remove("has-file");
        fileUploadBtn.innerHTML = "<span>📷</span> העלה תמונה";
        cropPreviewContainer.classList.remove("show");
        cropToggleBtn.classList.remove("show");
        cropImageNav.style.display = 'none';
        imageCropPositions = [];
        uploadedFiles = [];
        weeksAhead.value = 1;
        updateSelectedDates();
      } else {
        // Remove current image from array
        uploadedFiles.splice(currentCropIndex, 1);
        imageCropPositions.splice(currentCropIndex, 1);

        // Update weeks to match remaining images
        weeksAhead.value = uploadedFiles.length;
        updateSelectedDates();

        // Adjust current index if needed
        if (currentCropIndex >= uploadedFiles.length) {
          currentCropIndex = uploadedFiles.length - 1;
        }

        // Update UI
        const count = uploadedFiles.length;
        if (count === 1) {
          fileNameText.textContent = uploadedFiles[0].name;
          fileUploadBtn.innerHTML = "<span>✅</span> תמונה נבחרה";
          cropImageNav.style.display = 'none';
        } else {
          fileNameText.textContent = `${count} תמונות נבחרו`;
          fileUploadBtn.innerHTML = `<span>✅</span> ${count} תמונות נבחרו`;
          cropTotalNum.textContent = count;
          updateCropNavButtons();
        }

        // Show the current (or previous) image
        showCropPreview(uploadedFiles[currentCropIndex], currentCropIndex);
      }
    });

    // Crop navigation buttons
    function updateCropNavButtons() {
      cropCurrentNum.textContent = currentCropIndex + 1;
      cropPrevBtn.disabled = currentCropIndex === 0;
      cropNextBtn.disabled = currentCropIndex >= uploadedFiles.length - 1;
    }

    cropPrevBtn.addEventListener('click', () => {
      if (currentCropIndex > 0) {
        currentCropIndex--;
        showCropPreview(uploadedFiles[currentCropIndex], currentCropIndex);
        updateCropNavButtons();
      }
    });

    cropNextBtn.addEventListener('click', () => {
      if (currentCropIndex < uploadedFiles.length - 1) {
        currentCropIndex++;
        showCropPreview(uploadedFiles[currentCropIndex], currentCropIndex);
        updateCropNavButtons();
      }
    });

    // Pre-load image dimensions to check if square (without showing preview)
    function preloadCropPreview(file, index) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          // Check if image is already square
          const aspectRatio = img.width / img.height;
          const isSquare = Math.abs(aspectRatio - 1) < 0.02;

          if (isSquare) {
            // Hide the toggle button for square images
            cropToggleBtn.textContent = '✓ התמונה מרובעת';
            cropToggleBtn.style.borderColor = '#4caf50';
            cropToggleBtn.style.color = '#4caf50';
          } else {
            cropToggleBtn.textContent = '✂️ התאם חיתוך תמונה';
            cropToggleBtn.style.borderColor = '';
            cropToggleBtn.style.color = '';
          }
        };
        img.src = e.target.result;
      };
      reader.readAsDataURL(file);
    }

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

    // ===== Crop Preview Functionality =====
    let cropDragging = false;
    let cropStartX = 0, cropStartY = 0;
    let cropImgStartX = 0, cropImgStartY = 0;
    let cropImgWidth = 0, cropImgHeight = 0;
    let cropAreaWidth = 0, cropAreaHeight = 0;

    // Show crop preview for a file
    function showCropPreview(file, index) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          cropArea.classList.remove("unsupported");
          cropArea.classList.remove("no-crop-needed");
          noCropMsg.style.display = 'none';

          // Fixed size for crop area (200x200)
          cropAreaWidth = 200;
          cropAreaHeight = 200;

          // Check if image is already square (within 2% tolerance)
          const aspectRatio = img.width / img.height;
          const isSquare = Math.abs(aspectRatio - 1) < 0.02;

          // Scale image to cover the crop area (same as server-side fit_background)
          const scale = Math.max(cropAreaWidth / img.width, cropAreaHeight / img.height);
          cropImgWidth = img.width * scale;
          cropImgHeight = img.height * scale;

          cropPreviewImage.src = e.target.result;
          cropPreviewImage.style.width = cropImgWidth + 'px';
          cropPreviewImage.style.height = cropImgHeight + 'px';

          // Position based on saved crop position
          const cropPos = imageCropPositions[index] || { x: 0.5, y: 0.5 };
          updateCropImagePosition(cropPos.x, cropPos.y);

          // Show appropriate message
          if (isSquare) {
            cropArea.classList.add("no-crop-needed");
            noCropMsg.style.display = 'block';
            cropHintText.textContent = 'אין צורך בחיתוך';
          } else {
            cropHintText.textContent = 'גרור את התמונה לבחירת האזור';
          }

          currentCropIndex = index;
        };
        img.onerror = () => {
          // Image format not supported for preview (e.g., HEIC)
          cropArea.classList.add("unsupported");
          cropArea.classList.remove("no-crop-needed");
          noCropMsg.style.display = 'none';
          currentCropIndex = index;
        };
        img.src = e.target.result;
      };
      reader.readAsDataURL(file);
    }

    // Update image position based on crop percentages
    function updateCropImagePosition(cropX, cropY) {
      const maxOffsetX = cropImgWidth - cropAreaWidth;
      const maxOffsetY = cropImgHeight - cropAreaHeight;

      const offsetX = -maxOffsetX * cropX;
      const offsetY = -maxOffsetY * cropY;

      cropImageWrapper.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    }

    // Get crop position from current image offset
    function getCropPositionFromOffset() {
      const transform = cropImageWrapper.style.transform;
      const match = transform.match(/translate\(([^,]+)px,\s*([^)]+)px\)/);
      if (!match) return { x: 0.5, y: 0.5 };

      const offsetX = parseFloat(match[1]);
      const offsetY = parseFloat(match[2]);

      const maxOffsetX = cropImgWidth - cropAreaWidth;
      const maxOffsetY = cropImgHeight - cropAreaHeight;

      const cropX = maxOffsetX > 0 ? -offsetX / maxOffsetX : 0.5;
      const cropY = maxOffsetY > 0 ? -offsetY / maxOffsetY : 0.5;

      return {
        x: Math.max(0, Math.min(1, cropX)),
        y: Math.max(0, Math.min(1, cropY))
      };
    }

    // Drag handlers for crop
    cropArea.addEventListener('mousedown', (e) => {
      cropDragging = true;
      cropStartX = e.clientX;
      cropStartY = e.clientY;
      const transform = cropImageWrapper.style.transform;
      const match = transform.match(/translate\(([^,]+)px,\s*([^)]+)px\)/);
      cropImgStartX = match ? parseFloat(match[1]) : 0;
      cropImgStartY = match ? parseFloat(match[2]) : 0;
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!cropDragging) return;

      const deltaX = e.clientX - cropStartX;
      const deltaY = e.clientY - cropStartY;

      let newX = cropImgStartX + deltaX;
      let newY = cropImgStartY + deltaY;

      // Clamp to valid range
      const maxOffsetX = cropImgWidth - cropAreaWidth;
      const maxOffsetY = cropImgHeight - cropAreaHeight;

      newX = Math.max(-maxOffsetX, Math.min(0, newX));
      newY = Math.max(-maxOffsetY, Math.min(0, newY));

      cropImageWrapper.style.transform = `translate(${newX}px, ${newY}px)`;
    });

    document.addEventListener('mouseup', () => {
      if (cropDragging) {
        cropDragging = false;
        // Save current crop position
        imageCropPositions[currentCropIndex] = getCropPositionFromOffset();
      }
    });

    // Touch support for mobile
    cropArea.addEventListener('touchstart', (e) => {
      if (e.touches.length !== 1) return;
      const touch = e.touches[0];
      cropDragging = true;
      cropStartX = touch.clientX;
      cropStartY = touch.clientY;
      const transform = cropImageWrapper.style.transform;
      const match = transform.match(/translate\(([^,]+)px,\s*([^)]+)px\)/);
      cropImgStartX = match ? parseFloat(match[1]) : 0;
      cropImgStartY = match ? parseFloat(match[2]) : 0;
      e.preventDefault();
    }, { passive: false });

    document.addEventListener('touchmove', (e) => {
      if (!cropDragging || e.touches.length !== 1) return;
      const touch = e.touches[0];

      const deltaX = touch.clientX - cropStartX;
      const deltaY = touch.clientY - cropStartY;

      let newX = cropImgStartX + deltaX;
      let newY = cropImgStartY + deltaY;

      const maxOffsetX = cropImgWidth - cropAreaWidth;
      const maxOffsetY = cropImgHeight - cropAreaHeight;

      newX = Math.max(-maxOffsetX, Math.min(0, newX));
      newY = Math.max(-maxOffsetY, Math.min(0, newY));

      cropImageWrapper.style.transform = `translate(${newX}px, ${newY}px)`;
    }, { passive: true });

    document.addEventListener('touchend', () => {
      if (cropDragging) {
        cropDragging = false;
        imageCropPositions[currentCropIndex] = getCropPositionFromOffset();
      }
    });

    // Store generated posters for multi-download
    let generatedPosters = [];

    btn.addEventListener("click", async () => {
      const message = messageInput.value.trim();
      const leiluyNeshama = neshamaInput.value.trim();
      // Hide if empty - no need for enabled flags anymore
      const hideDedication = !leiluyNeshama;
      const hideBlessing = !message;
      const uploadedFiles = fileInput.files;

      // Determine dates to generate
      const datesToGenerate = selectedDates.length > 0 ? selectedDates : [""];
      const isMultiple = datesToGenerate.length > 1;

      statusEl.textContent = isMultiple
        ? `⏳ יוצרת ${datesToGenerate.length} זְמוּנוֹת...`
        : "⏳ יוצרת את הזְמוּנָה שלך...";
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

        // Collect selected cities in user's preferred order
        const selectedCities = [];
        orderedSelectedCities.forEach(cityName => {
          const opt = document.querySelector(`.city-option[data-name="${escapeAttrForSelector(cityName)}"]`);
          if (opt && opt.classList.contains('checked')) {
            const offsetInput = opt.querySelector(".candle-offset");
            const offset = parseInt(offsetInput.value) || 20;
            selectedCities.push({ name: cityName, candle_offset: offset });
          }
        });

        // Generate poster for each date
        for (let i = 0; i < datesToGenerate.length; i++) {
          const date = datesToGenerate[i];
          const payload = {};

          // Use corresponding image, or last image if fewer images than dates
          if (imagesBase64.length > 0) {
            const imgIndex = Math.min(i, imagesBase64.length - 1);
            payload.imageBase64 = imagesBase64[imgIndex];

            // Add crop position for this image
            if (imageCropPositions[imgIndex]) {
              payload.cropX = imageCropPositions[imgIndex].x;
              payload.cropY = imageCropPositions[imgIndex].y;
            }
          }
          if (message) payload.message = message;
          if (leiluyNeshama) payload.leiluyNeshama = leiluyNeshama;
          if (hideDedication) payload.hideDedication = true;
          if (hideBlessing) payload.hideBlessing = true;
          if (date) payload.startDate = date;
          if (selectedCities.length > 0) payload.cities = selectedCities;
          payload.dateFormat = selectedDateFormat;

          // Add manual overrides if provided
          const mainTitleOverride = overrideMainTitle.value.trim();
          const subtitleOverride = overrideSubtitle.value.trim();
          if (mainTitleOverride) payload.overrideMainTitle = mainTitleOverride;
          if (subtitleOverride) payload.overrideSubtitle = subtitleOverride;

          // Add custom cities if any
          const customCities = getCustomCities();
          if (customCities.length > 0) {
            payload.customCities = customCities;
          }

          statusEl.textContent = isMultiple
            ? `⏳ יוצרת זְמוּנָה ${i + 1} מתוך ${datesToGenerate.length}...`
            : "⏳ יוצרת את הזְמוּנָה שלך...";

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

        // Revoke old blob URLs to free memory
        currentBlobUrls.forEach(url => URL.revokeObjectURL(url));
        currentBlobUrls = [];

        // Update gallery with all posters
        previewGallery.innerHTML = '';
        previewGallery.className = generatedPosters.length === 1 ? 'preview-gallery single' : 'preview-gallery multiple';

        generatedPosters.forEach((poster, index) => {
          const item = document.createElement('div');
          item.className = 'preview-gallery-item';

          const blobUrl = URL.createObjectURL(poster.blob);
          currentBlobUrls.push(blobUrl);

          const img = document.createElement('img');
          img.src = blobUrl;
          img.alt = `זְמוּנָה ${index + 1}`;

          const label = document.createElement('div');
          label.className = 'poster-label';
          label.textContent = `זְמוּנָה ${index + 1}`;

          item.appendChild(img);
          item.appendChild(label);
          previewGallery.appendChild(item);
        });

        previewEl.classList.add("show");

        // Update title and button text based on count
        if (isMultiple) {
          previewTitle.textContent = `🎉 ${datesToGenerate.length} זְמוּנוֹת מוכנות!`;
          downloadBtnText.textContent = `הורד ${datesToGenerate.length} זְמוּנוֹת`;
          statusEl.textContent = `✅ נוצרו ${datesToGenerate.length} זְמוּנוֹת בהצלחה!`;
        } else {
          previewTitle.textContent = '🎉 הזְמוּנָה מוכנה!';
          downloadBtnText.textContent = 'הורד תמונה';
          statusEl.textContent = "✅ הזְמוּנָה נוצרה בהצלחה!";
        }
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
    """Get upcoming Shabbat/holiday events for one year ahead."""
    events = []
    current_date = date.today()
    # Calculate end date as one year from today
    one_year_ahead = date(current_date.year + 1, current_date.month, current_date.day)

    i = 0
    while current_date < one_year_ahead:
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
                "Rosh Hashanah": "ראש השנה",
                "Yom Kippur": "יום כיפור",
                "Sukkos": "סוכות",
                "Sukkot": "סוכות",
                "Shmini Atzeres": "שמיני עצרת",
                "Shemini Atzeret": "שמיני עצרת",
                "Simchas Torah": "שמחת תורה",
                "Simchat Torah": "שמחת תורה",
                "Pesach": "פסח",
                "Passover": "פסח",
                "Shavuos": "שבועות",
                "Shavuot": "שבועות",
                "Chanukah": "חנוכה",
                "Hanukkah": "חנוכה",
                "Purim": "פורים",
                "Tu BiShvat": "ט״ו בשבט",
                "Tu B'Shvat": "ט״ו בשבט",
                "Lag BaOmer": "ל״ג בעומר",
                "Lag B'Omer": "ל״ג בעומר",
                "Tisha B'Av": "תשעה באב",
                "Yom HaShoah": "יום השואה",
                "Yom HaZikaron": "יום הזיכרון",
                "Yom HaAtzmaut": "יום העצמאות",
                "Yom Yerushalayim": "יום ירושלים",
                "Chol HaMoed": "חול המועד",
                "Shmini Atzeret": "שמיני עצרת",
                "Simchat Tora": "שמחת תורה",
                "Shmini Atzeret / Simchat Tora": "שמיני עצרת / שמחת תורה",
            }
            # Try exact match first, then try partial match for variations like "Pesach I"
            display_name = yomtov_translations.get(event_name)
            if not display_name:
                # Try matching prefix (for "Pesach I", "Sukkot II", etc.)
                for eng, heb in yomtov_translations.items():
                    if event_name.startswith(eng):
                        display_name = heb
                        break
                else:
                    display_name = event_name

            # For Chol HaMoed on Shabbat (Saturday), show "שבת חול המועד"
            is_shabbat = seq_end.weekday() == 5  # Saturday
            if "Chol HaMoed" in event_name and is_shabbat:
                display_name = "שבת חול המועד"
            # For holidays on Shabbat, only show the holiday name (no parsha)

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
            "parsha": parsha,  # Include parsha separately for search
            "dateStr": date_str,
            "isNext": i == 0,
        })

        # Move to day after this sequence ends
        current_date = seq_end + timedelta(days=1)
        i += 1

    return events
