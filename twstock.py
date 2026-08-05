"""台股即時資料爬蟲 - Gradio 網頁介面啟動入口。

執行：
    uv run twstock.py
    # 開啟 http://127.0.0.1:7860
"""

from twstock.app import demo

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
