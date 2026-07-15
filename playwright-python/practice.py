from playwright.sync_api import sync_playwright,Browser,Page

def run():
    ## with as : 語法糖 結束會自動關閉 不用手動close清除記憶體
    with sync_playwright() as p:
        # 啟動瀏覽器
        # headless 是無圖形介面模式，適合在這種容器環境中執行
        browser:Browser = p.chromium.launch(headless=True)

        # 開啟新分頁
        page:Page = browser.new_page()

        # 訪問網站
        res = page.goto("https://www.google.com")
        # return Response | None <Response url='https://www.google.com/' request=<Request url='https://www.google.com/' method='GET'>>

        # 取得標題
        print(page.title()) # Google

        # 關閉瀏覽器
        browser.close()

if __name__ == "__main__":
    run()
