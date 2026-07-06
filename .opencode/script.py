import asyncio
import csv
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

async def main():
    os.makedirs(os.path.join(OUT_DIR, "screenshots"), exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 1800},
            locale="zh-TW"
        )
        page = await context.new_page()

        # --- Step 1: Load homepage and accept disclaimer ---
        await page.goto("https://mis.taifex.com.tw/futures/", wait_until="networkidle")
        await asyncio.sleep(3)

        if "disclaimer" in page.url:
            await page.locator("div.approve-wrap button.btn").first.click()
            await asyncio.sleep(5)

        # --- Step 2: Bypass Nuxt route guard ---
        await page.evaluate("""
            () => {
                sessionStorage.setItem("disclaimer_tc", 1);
            }
        """)

        # --- Step 3: Navigate to after-hours domestic index futures ---
        await page.evaluate("""
            async () => {
                await window.$nuxt.$router.push(
                    "AfterHoursSession/EquityIndices/FuturesDomestic"
                );
            }
        """)
        await asyncio.sleep(5)

        # --- Step 4: Wait for table data to be populated ---
        # The data arrives via WebSocket, so we need to wait a bit
        for attempt in range(20):
            table_text = await page.locator("table").first.inner_text()
            if "--" not in table_text and len(table_text) > 100:
                break
            await asyncio.sleep(2)
        else:
            print("Warning: table may not have full data")

        await page.screenshot(
            path=os.path.join(OUT_DIR, "screenshots", "ah_prices.png")
        )

        # --- Step 5: Extract table data ---
        tables = page.locator("table")
        table_count = await tables.count()
        print(f"Tables found: {table_count}")

        all_data = []
        for i in range(table_count):
            table = tables.nth(i)
            rows = table.locator("tr")
            row_count = await rows.count()
            print(f"  Table {i}: {row_count} rows")

            for r in range(row_count):
                cells = rows.nth(r).locator("td, th")
                cell_count = await cells.count()
                row_data = []
                for c in range(cell_count):
                    text = (await cells.nth(c).inner_text()).strip()
                    row_data.append(text)
                all_data.append(row_data)

        # --- Step 6: Save as CSV ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(OUT_DIR, f"ah_prices_{timestamp}.csv")
        txt_path = os.path.join(OUT_DIR, f"ah_prices_{timestamp}.txt")

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(all_data)
        print(f"Saved CSV: {csv_path} ({len(all_data)} rows)")

        with open(txt_path, "w", encoding="utf-8") as f:
            for row in all_data:
                f.write("\t".join(row) + "\n")
        print(f"Saved TXT: {txt_path}")

        # --- Step 7: Try API-based data extraction ---
        # The WebSocket delivers data via rtCore, but we can also try the API
        api_data = await page.evaluate("""
            () => {
                try {
                    // Try to get data from the Vue component's reactive properties
                    const app = document.querySelector('#__nuxt');
                    if (app && app.__vue__) {
                        const children = app.__vue__.$children;
                        for (const child of children) {
                            if (child.tableData || child.quoteData || child.rows) {
                                return JSON.stringify({
                                    tableData: child.tableData,
                                    quoteData: child.quoteData,
                                    rows: child.rows
                                }).substring(0, 10000);
                            }
                        }
                    }
                    return 'no vue data found';
                } catch(e) {
                    return 'error: ' + e.message;
                }
            }
        """)
        if api_data and "no vue data" not in api_data and "error" not in api_data:
            with open(os.path.join(OUT_DIR, f"api_data_{timestamp}.json"), "w", encoding="utf-8") as f:
                f.write(api_data)
            print(f"Saved API data")

        await browser.close()

asyncio.run(main())
