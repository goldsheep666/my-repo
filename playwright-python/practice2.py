from playwright.sync_api import sync_playwright, Browser, Page

def run():
    ## with as : 語法糖 結束會自動關閉 不用手動close清除記憶體
    #  with sync_playwright() as p:
    p = sync_playwright().start()

    try:
        # 啟動瀏覽器
        browser: Browser = p.chromium.launch(headless=False)

        # 開啟新分頁
        page: Page = browser.new_page()

        # 訪問網站
        page.goto("https://zh.wikipedia.org")
        # page.get_by_role("searchbox").first.fill("臺灣")
        page.locator("#searchInput").fill("臺灣")
        page.screenshot(path="screenshot.png")
        page.keyboard.press("Enter")

        page.wait_for_load_state("networkidle")
        # page.wait_for_load_state() 等待頁面達到指定的載入狀態後才繼續執行，避免在頁面還沒載入完就操作元素導致失敗。
        # 三種狀態：
        # - "commit" — 響應到達、文檔開始載入
        # - "domcontentloaded" — DOM 解析完成（HTML 讀完）
        # - "load"（預設） — 所有資源（圖片、樣式等）載入完成
        # - "networkidle" — 500ms 內沒有網路請求，代表頁面完全靜止

        first_heading:str=page.locator("#firstHeading").inner_text()
        print(first_heading)

        content: str = page.locator("#mw-content-text p").first.inner_text()
        print(f"摘要:{content}")

        page.go_back()

        page.wait_for_load_state("networkidle")
        print(f"返回首頁:{page.title()}")

        # flush=True 強制把內容立刻寫到終端機
        print("按 Enter 關閉瀏覽器...", flush=True)

        input()# 利用input 只能靠按 Enter 打斷。按其他鍵都不會有反應，游標會一直等
    except Exception as e:
        print(f"發生錯誤: {e}", flush=True)
    finally:
        p.stop()

    # 因為 run() 函式結束後，Python 會自動回收 p（playwright 實例），觸發瀏覽器關閉。
    # 這不是按 Enter 的問題，是程式結束 = 瀏覽器關掉。Playwright 的瀏覽器是綁在程式上的，程式活著它才活著。


if __name__ == "__main__":
    run()
