# 台股即時資料爬蟲（Python + Playwright）

使用 **Playwright** 從 **奇摩股市** 爬取台股即時報價（含買賣五檔），並可透過 Yahoo Chart API 下載歷史資料，輸出為 JSON / CSV。

需求規格詳見 [REQUIREMENTS.md](REQUIREMENTS.md)。

## 環境需求

- Python 3.12+
- Playwright 套件與 Chromium 瀏覽器

```bash
pip install "playwright>=1.61.0"
playwright install chromium
```

## 使用方式

### Gradio 網頁介面

```bash
python twstock/app.py
```

瀏覽器開啟 http://127.0.0.1:7860，提供兩個頁籤：

- **即時行情**：輸入股票代號（逗號或空白分隔）、勾選是否抓取買賣五檔，一鍵抓取並以表格 / JSON 顯示，可勾選同時儲存至 `output/`
- **歷史資料**：選擇區間（1m / 5d / 1mo / 3mo / 6mo / 1y / 5y），下載並預覽歷史資料 CSV

### 命令列

```bash
# 讀取 config.json 的股票清單
python twstock/main.py

# 命令列指定股票（優先於 config.json）
python twstock/main.py 2330 2317 2454

# 上櫃股票自動判斷（5347 會自動以 .TWO 抓取）
python twstock/main.py 5347
```

### 參數

| 參數 | 說明 | 預設 |
| --- | --- | --- |
| `stocks`（位置參數） | 股票代號，可多個 | 讀取 config.json |
| `--format {json,csv,both}` | 輸出格式 | 讀取 config.json |
| `--no-orderbook` | 不爬買賣五檔 | 爬 |
| `--history {1m,5d,1mo,3mo,6mo,1y,5y}` | 額外下載歷史資料 | 不下載 |
| `--headless / --no-headless` | 無頭 / 有頭模式 | 讀取 config.json |

```bash
python twstock/main.py 2330 --history 1mo --format both
python twstock/main.py 2330 --no-headless --no-orderbook
```

## 設定檔 config.json

```json
{
  "stocks": ["2330", "2317", "2454"],
  "scraper": {
    "headless": true,
    "timeout_ms": 60000
  },
  "output": {
    "dir": "output",
    "formats": ["json", "csv"]
  }
}
```

## 輸出

執行後於 `output/` 產生：

- `quotes_YYYYMMDD_HHMMSS.json` — 完整結構（含買賣五檔）
- `quotes_YYYYMMDD_HHMMSS.csv` — 扁平化欄位（含五檔買賣價量）
- `history_<代號>_YYYYMMDD_HHMMSS.csv` — 歷史日線（搭配 `--history`）

## 專案結構

```
twstock/
├── REQUIREMENTS.md   # 需求規格書
├── README.md         # 本文件
├── config.json       # 股票清單與設定
├── app.py            # Gradio 網頁介面
├── main.py           # CLI 進入點
├── models.py         # 資料模型（Quote / OrderBook / HistoryBar）
├── scraper.py        # Playwright 爬蟲核心
└── output.py         # JSON / CSV 輸出
```

## 開發

型別檢查（basedpyright）：

```bash
uv run basedpyright twstock
```
