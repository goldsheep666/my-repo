lsp
language server protocol檢查語法
basedpyright => 使用的protocol

## __name__=="__main__"
- __name__ 是什麼？
  在 Python 中，__name__ 是一個內建的特殊變數。每個 Python 檔案（也就是「模組」）在執行時，Python 都會自動幫它設定 __name__ 的值。

  這個值會根據你執行它的方式而改變：

情況 A（直接執行）： 如果你是直接按執行鍵，或在終端機輸入 python my_script.py，Python 就會把這個檔案當成主程式。這時候，這個檔案的 __name__ 會被自動設定為 "__main__"。

情況 B（被匯入）： 如果這個檔案是被別的檔案用 import my_script 匯入的，Python 就會把它的 __name__ 設定為它原本的檔名（例如 "my_script"）。


- 為什麼需要這行判斷式？
  我們用一個簡單的例子來對比：

  假設你有一個檔案叫 math_tools.py，裡面寫了一個相加的函式，並在最下面寫了測試程式碼：


``` python
# math_tools.py
def add(a, b):
    return a + b
```
# 測試用：
print("測試相加：", add(5, 5))
如果你直接執行 math_tools.py： 螢幕上會印出 測試相加： 10。這很完美。

但如果你在另一個檔案 main.py 想要使用這個 add 函式：

# main.py
import math_tools  # 這裡匯入了 math_tools

print("主程式開始執行...")
當你執行 main.py 時，你會發現螢幕上竟然也印出了 測試相加： 10！這是因為 Python 在 import 的時候，會把被匯入檔案裡面的程式碼「從頭到尾執行一遍」。這樣一來，你的測試程式碼就去干擾到別人的檔案了。

3. 使用 if __name__ == "__main__" 來解決
為了避免這種尷尬的情況，我們可以把「測試或只想在直接執行時運作的程式碼」用這個 if 包起來：

Python
``` python
# math_tools.py
def add(a, b):
    return a + b

if __name__ == "__main__":
    # 只有在直接執行 math_tools.py 時，這兩行才會跑
    print("這是在直接執行時才會出現的測試：")
    print("測試相加：", add(5, 5))

```