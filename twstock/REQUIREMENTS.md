# 台股即時資料爬蟲 — 需求規格書

> 版本：1.0　日期：2026-08-05　狀態：定稿（依此文件開發）

## 1. 專案目標

建立一個以 **Python + Playwright** 為技術棧的命令列工具，從 **奇摩股市（Yahoo 股市台灣版）** 爬取台股即時報價資料，並輸出為 JSON / CSV 檔案，供後續分析使用。

## 2. 技術棧

| 項目 | 內容 |
| --- | --- |
| 語言 | Python 3.12 |
| 瀏覽器自動化 | Playwright（同步 API） |
| 瀏覽器 | Chromium（headless 無頭模式） |
| Web 介面 | Gradio（app.py） |
| 依賴管理 | uv（`pyproject.toml` 已含 `playwright>=1.61.0`、`gradio`） |
| 資料來源 | https://tw.stock.yahoo.com/quote/{代號}.{交易所} |

## 3. 功能需求

### 3.1 即時行情（基本行情）
爬取個股報價頁面的以下欄位：

| 欄位 | 說明 |
| --- | --- |
| 股票名稱 | 例：台積電 |
| 成交價 | 例：2,405 |
| 漲跌 | 例：+85.00 |
| 漲跌幅 | 例：3.66% |
| 開盤 / 最高 / 最低 | 當日開高低 |
| 昨收 | 前一交易日收盤價 |
| 均價 | 當日均價 |
| 成交量 / 昨量 | 單位：張 |
| 成交金額(億) | 成交金額，單位：億 |
| 振幅 | 當日振幅 % |
| 收盤狀態 | 例：收盤 / 盤中 / 盤後，與資料更新時間 |

### 3.2 買賣五檔
爬取「買賣五檔」區塊：

- 五檔買價與對應委買量
- 五檔賣價與對應委賣量
- 委買 / 委賣小計

### 3.3 分時 / 歷史資料（可選）
透過 Playwright 的 `APIRequestContext` 呼叫 Yahoo Chart API，下載指定區間（如近一個月、近一年）的日線資料並輸出 CSV。

### 3.4 股票清單指定方式（兩者並存）
1. **命令列參數**（優先）：`python main.py 2330 2317 2454`
2. **設定檔 `config.json`**（兜底）：未提供參數時讀取設定檔內的股票清單

### 3.5 輸出方式
- 每次執行產生一個輸出檔：`quotes_YYYYMMDD_HHMMSS.json` 與 `.csv`
- 輸出至 `output/` 資料夾
- JSON：完整結構（含五檔）
- CSV：扁平化欄位（含五檔買賣價量）

### 3.6 Gradio 網頁介面
- 以 `python twstock/app.py` 啟動本機 Web 介面（http://127.0.0.1:7860）
- 「即時行情」頁籤：輸入股票代號（逗號/空白分隔）、勾選買賣五檔與存檔選項，抓取後以表格 + JSON 顯示，可下載輸出檔案
- 「歷史資料」頁籤：選擇區間下載歷史日線並預覽、下載 CSV
- 介面與 CLI 共用同一套爬蟲核心，多執行緒下以 lock 保護瀏覽器

## 4. 執行流程

1. 解析命令列參數與設定檔，決定股票清單
2. 啟動 Playwright + Chromium（headless）
3. 對每檔股票開啟報價頁面
4. 自動判斷交易所：先試 `.TW`（上市），找不到再試 `.TWO`（上櫃）
5. 解析：名稱、即時行情、買賣五檔
6. 若指定 `--history`，另以 Chart API 下載歷史資料
7. 寫入 JSON / CSV 至 `output/`
8. 關閉瀏覽器，於終端顯示摘要

## 5. 設定檔範例（config.json）

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

## 6. 命令列介面

```
python twstock/main.py                          # 讀取 config.json 的股票
python twstock/main.py 2330 2317                # 命令列指定股票
python twstock/main.py 2330 --no-orderbook      # 略過買賣五檔
python twstock/main.py 2330 --history 1mo       # 額外下載近一個月日線
python twstock/main.py 2330 --format csv        # 只輸出 CSV
```

參數說明：

| 參數 | 說明 | 預設 |
| --- | --- | --- |
| `stocks`（位置參數） | 股票代號，可多個 | 讀取 config.json |
| `--format` | `json` / `csv` / `both` | `both` |
| `--no-orderbook` | 不爬買賣五檔 | 爬 |
| `--history` | 歷史資料區間：`1mo` / `3mo` / `1y` / `1m` | 不下載 |
| `--headless` | 是否無頭模式 | `true` |

## 7. 資料結構

### 7.1 JSON 輸出範例

```json
{
  "fetched_at": "2026-08-05T14:30:00+08:00",
  "quotes": [
    {
      "symbol": "2330",
      "name": "台積電",
      "price": 2405.0,
      "change": 85.0,
      "change_percent": 3.66,
      "open": 2385.0,
      "high": 2415.0,
      "low": 2370.0,
      "prev_close": 2320.0,
      "avg_price": 2396.0,
      "volume": 31863,
      "prev_volume": 35900,
      "amount_yi": 763.67,
      "amplitude": 1.94,
      "status": "收盤",
      "update_time": "2026/08/05 14:30",
      "orderbook": {
        "bids": [{"price": 2400.0, "size": 27}, {"price": 2395.0, "size": 57}],
        "asks": [{"price": 2405.0, "size": 250}, {"price": 2410.0, "size": 1367}],
        "bid_total": 955,
        "ask_total": 5666
      }
    }
  ]
}
```

### 7.2 CSV 欄位

`symbol,name,price,change,change_percent,open,high,low,prev_close,avg_price,volume,prev_volume,amount_yi,amplitude,status,update_time,bid1_price,bid1_size,...,ask5_price,ask5_size`

## 8. 非功能需求

- 每檔股票抓取失敗時不中斷整體流程，記錄錯誤並繼續下一檔
- 頁面載入使用 `wait_for_load_state("load")` + 等待目標元素，不使用 `networkidle`（即時串流 WebSocket 永不 idle）
- 程式碼以 dataclass + 型別註解撰寫，符合 repo 既有風格（basedpyright）
- 不提交輸出檔與截圖等產物至 git

## 9. 驗收標準

1. `python twstock/main.py 2330` 能成功輸出 JSON + CSV
2. 命令列參數優先於 config.json
3. 上櫃股票（如 5347）能自動解析為 `.TWO`
4. 單一股票失敗不影響其他股票
5. `--history 1mo` 能輸出歷史日線 CSV
