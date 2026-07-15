from playwright.sync_api import sync_playwright
from playwright.sync_api import Browser, Page, Locator

def main():
  with sync_playwright() as p:
      # 啟動 Chromium 瀏覽器（無頭模式 headless=True）
      browser: Browser = p.chromium.launch(headless=True)

      # 開啟新的分頁
      page: Page = browser.new_page()

      # 導向 PTT 八卦版首頁
      page.goto("https://www.ptt.cc/bbs/Gossiping/index.html")

      # 等待「年齡確認」的同意按鈕出現（最多等待 10 秒）
      page.wait_for_selector("button.btn-big", timeout=10000)

      # 點擊「我同意，我已年滿十八歲」按鈕
      page.get_by_role("button", name="我同意，我已年滿十八歲").click()

      # 等待文章列表區塊載入（確保 .r-ent 元素已出現在畫面上）
      page.wait_for_selector("div.r-ent", timeout=10000)

      # 取得並輸出頁面標題
      title: str = page.title()
      print(f"頁面標題: {title}")

      # 尋找所有文章標題連結的 Locator
      articles: list[Locator] = page.locator("div.r-ent div.title a").all()
      print(f"文章數量: {len(articles)}")

      # 取出前 5 篇的文章標題並印出
      for article in articles[:5]:
          print(f"  - {article.inner_text()}")

      # 拍攝整頁截圖並儲存至本機
      page.screenshot(path="ptt_screenshot.png", full_page=True)
      print("截圖已儲存: ptt_screenshot.png")

      # 關閉瀏覽器結束會話
      browser.close()

if __name__ == "__main__":
  main()