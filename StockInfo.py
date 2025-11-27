import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import Menu
import requests
import re
import threading
import time
from datetime import datetime
import pytz
from post_market_info import show_post_market_info
import ssl
import urllib3


ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 停止更新的旗標
is_updating = False
update_thread = None  # 用來存儲更新的線程
update_event = threading.Event()  # 用來控制更新是否停止

global is_US_Stock

# 設置抓取股市資料的函數
def get_stock_info(stock_code,patterns):
    yahoo_stock_url = f"https://tw.stock.yahoo.com/q/q?s={stock_code}"

    def extract_value(pattern_keys, html_content):
        for key in pattern_keys:
            match = re.search(patterns[key], html_content)
            if match:
                return match.group(1),key
        return "無法找到",key

    response = requests.get(yahoo_stock_url, timeout=10)
    html_content = response.text

    # 抓取股價
    stock_price ,key = extract_value(["price_max_up", "price_max_down", "price_up", "price_down", "price_no_change", "US_price_up", "US_price_down", "US_price_no_change"], html_content)
    if key == "price_max_up" or key == "price_up" or key == "US_price_up":
        price_color = "Red"  # 上漲顯示紅色
    elif key == "price_max_down" or key == "price_down" or key == "US_price_down":
        price_color = "Green"  # 下跌顯示綠色
    else:
        price_color = "Black"  # 無變化顯示黑色

    # 抓取漲跌(元)
    change_value ,key= extract_value(["change_value_up", "change_value_down", "change_value_nochange"], html_content)
    if key == "change_value_up":
        change_value = "+" + change_value
        change_color = "Red"  # 上漲顯示紅色
    elif key == "change_value_down":
        change_value = "-" + change_value
        change_color = "Green"  # 下跌顯示綠色
    else:
        change_color = "Black"  # 無變化顯示黑色

    # 抓取成交量
    stock_volume ,key= extract_value(["volume"], html_content)
    if stock_volume == "無法找到":
        matches = list(re.finditer(patterns["US_volume"], html_content))
        if len(matches) >= 5:
            stock_volume = matches[3].group(1)  # 顯示第三個匹配項
        elif len(matches) >= 4:
            stock_volume = matches[2].group(1)  # 顯示第二個匹配項

    # 抓取漲跌幅
    stock_change ,key= extract_value(["change_up", "change_down", "change_no_change"], html_content)
    if key == "change_up":
        change_color = "Red"  # 漲幅顯示紅色
    elif key == "change_down":
        change_color = "Green"  # 跌幅顯示綠色
    else:
        change_color = "Black"  # 無變化顯示黑色

    # 抓取股票名稱
    stock_name ,key= extract_value(["stock_name"], html_content)

    # 更新UI顯示
    price_label.config(text=f"目前股價: {stock_price}", fg=price_color)
    change_label.config(text=f"漲跌幅: {change_value} {stock_change}", fg=change_color)
    volume_label.config(text=f"成交量: {stock_volume}", fg="DarkOrange")
    stock_code_label.config(text=f"股票名稱: {stock_name} ({stock_code})")
        

def get_stock_code(User_input_code):
    # 台灣證券交易所 API（上市股票）
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    # 台灣櫃買中心 API（上櫃股票
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    # 台灣櫃買中心 API（興櫃股票
    tpee_url = "https://www.tpex.org.tw/openapi/v1/tpex_esb_latest_statistics"

    # 取得上市股票資料
    twse_response = requests.get(twse_url, verify=False)
    twse_response.raise_for_status()
    twse_data = twse_response.json()

    # 取得上櫃股票資料
    tpex_response = requests.get(tpex_url, verify=False)
    tpex_response.raise_for_status()
    tpex_data = tpex_response.json()

    # 取得興櫃股票資料
    tpee_response = requests.get(tpee_url, verify=False)
    tpee_response.raise_for_status()
    tpee_data = tpee_response.json()

    if User_input_code == "":
        return User_input_code  # 如果未找到，返回 User_input_code
    # 查找股票代碼
    for item in twse_data:
        if item["Name"] == User_input_code or item["Code"] == User_input_code:
            return item["Code"]
    # 查找股票代碼
    for item in tpex_data:
        if item["CompanyName"] == User_input_code or item["SecuritiesCompanyCode"] == User_input_code:
            return item["SecuritiesCompanyCode"]
    # 查找股票代碼
    for item in tpee_data:
        if item["CompanyName"] == User_input_code or item["SecuritiesCompanyCode"] == User_input_code:
            return item["SecuritiesCompanyCode"]

    return User_input_code  # 如果未找到，返回 User_input_code

def fetch_data():
    global is_updating, update_thread, update_event

    update_event = threading.Event()
    update_thread = None
    User_input_code = stock_code_input.get()
    stock_code = get_stock_code(User_input_code)

    # 禁用按鈕防止重複點擊
    fetch_button.config(state=tk.DISABLED, text="補燃料...", fg="White", disabledforeground="White")

    is_updating = True
    update_event.clear()  # 重置事件

    # 啟動一個新線程來處理持續更新
    update_thread = threading.Thread(target=update_stock_data, args=(stock_code,))
    update_thread.daemon = True
    update_thread.start()
    
def getpattern():
        # 正則表達式
    patterns = {
        "price_max_up": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(16px\) C\(\#fff\) Px\(6px\) Py\(2px\) Bdrs\(4px\) Bgc\(\$c-trend-up\)">([^<]+)</span>',
        "price_max_down": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(16px\) C\(\#fff\) Px\(6px\) Py\(2px\) Bdrs\(4px\) Bgc\(\$c-trend-down\)">([^<]+)</span>',
        "price_up": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(16px\) D\(f\) Ai\(c\) C\(\$c-trend-up\)">([^<]+)</span>',
        "price_down": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(16px\) D\(f\) Ai\(c\) C\(\$c-trend-down\)">([^<]+)</span>',
        "price_no_change": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(16px\) D\(f\) Ai\(c\)">([^<]+)</span>',
        "US_price_up": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(4px\) D\(f\) Ai\(c\) C\(\$c-trend-up\)">([^<]+)</span>',
        "US_price_down": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(4px\) D\(f\) Ai\(c\) C\(\$c-trend-down\)">([^<]+)</span>',
        "US_price_no_change": r'class="Fz\(32px\) Fw\(b\) Lh\(1\) Mend\(4px\) D\(f\) Ai\(c\) C\(\$c-trend-up\)">([^<]+)</span>',
        "change_up": r'class="Jc\(fe\) Fz\(20px\) Lh\(1.2\) Fw\(b\) D\(f\) Ai\(c\) C\(\$c-trend-up\)">([^<]+)</span>',
        "change_down": r'class="Jc\(fe\) Fz\(20px\) Lh\(1.2\) Fw\(b\) D\(f\) Ai\(c\) C\(\$c-trend-down\)">([^<]+)</span>',
        "change_no_change": r'class="Jc\(fe\) Fz\(20px\) Lh\(1.2\) Fw\(b\) D\(f\) Ai\(c\)">([^<]+)</span>',
        "stock_name": r'class="C\(\$c-link-text\)[^"]*">([^<]+)</h1>',
        "volume": r'class="Fz\(16px\) C\(\$c-link-text\) Mb\(4px\)">([^<]+)</span>',
        "US_volume": r'class="Fw\(600\) Fz\(16px\)--mobile Fz\(14px\)">([^<]+)</span>',
        "change_value_up": r'class="Fw\(600\) Fz\(16px\)--mobile Fz\(14px\) D\(f\) Ai\(c\) C\(\$c-trend-up\)"><span class="Mend\(4px\) Bds\(s\)" style="border-color:transparent transparent #ff333a transparent;border-width:0 5px 7px 5px"></span>([^<]+)</span>',
        "change_value_down": r'<span class="Fw\(600\) Fz\(16px\)--mobile Fz\(14px\) D\(f\) Ai\(c\) C\(\$c-trend-down\)"><span class="Mend\(4px\) Bds\(s\)" style="border-color:#00ab5e transparent transparent transparent;border-width:7px 5px 0 5px"></span>([^<]+)</span>',
        "change_value_nochange": r'<span class="Fw\(600\) Fz\(16px\)--mobile Fz\(14px\) D\(f\) Ai\(c\)">([^<]+)</span>'
    }
    return patterns

def update_stock_data(stock_code):
    # 設置股市開盤和結束時間（台灣股市）
    market_open_time = "08:55:00"
    market_close_time = "13:45:00"
    is_US_Stock = False
    yahoo_stock_url = f"https://tw.stock.yahoo.com/q/q?s={stock_code}"
    pattern = getpattern()
    try:
        response = requests.get(yahoo_stock_url, timeout=10, verify=False)
        html_content = response.text
        # 抓取成交量
        stock_volume = "無法找到成交量"
        if re.search(pattern['volume'], html_content):
            stock_volume = re.search(pattern['volume'], html_content).group(1)
            # 設置股市開盤和結束時間（台灣股市）
            market_open_time = "08:55:00"
            market_close_time = "13:45:00"
            is_US_Stock = False
        elif re.search(pattern['US_volume'], html_content):
            # 設置股市開盤和結束時間（美國股市）
            market_open_time = "08:25:00"
            market_close_time = "16:15:00"
            is_US_Stock = True
            stock_volume = re.search(pattern['US_volume'], html_content).group(1)
    except requests.exceptions.RequestException as e:
        messagebox.showerror("錯誤", f"抓取資料時出現錯誤: {e}")
    
    if is_US_Stock:
        # 獲取紐約時區的時間
        eastern = pytz.timezone('US/Eastern')
        current_time = datetime.now(eastern).strftime("%H:%M:%S")
    else:
        current_time = datetime.now().strftime("%H:%M:%S")

    # 檢查是否在交易時間範圍內
    if market_open_time <= current_time <= market_close_time  and is_updating and stock_volume != "無法找到成交量":
        # 如果在交易時間內，持續更新每秒一次
        while market_open_time <= current_time <= market_close_time and is_updating:
            get_stock_info(stock_code,pattern)
            for _ in range(1):  # 每秒更新一次
                if update_event.is_set():  # 檢查是否需要停止
                    return
                time.sleep(1)
                if is_US_Stock:
                # 獲取紐約時區的時間
                    eastern = pytz.timezone('US/Eastern')
                    current_time = datetime.now(eastern).strftime("%H:%M:%S")
                else:
                    current_time = datetime.now().strftime("%H:%M:%S")
    else:
        # 如果不在交易時間範圍內，只執行一次
        get_stock_info(stock_code,pattern)
    
    # 恢復按鈕狀態
    fetch_button.config(state=tk.NORMAL, text="To The Moon", fg="black")

def stop_update():
    global is_updating
    is_updating = False
    update_event.set()  # 設置事件，通知更新線程停止

    fetch_button.config(state=tk.NORMAL, text="To The Moon", fg="black")

def on_closing(event=None):
    # 確保停止更新
    stop_update()
    root.destroy()

def adjust_opacity(value):
    # 獲取透明度值，調整窗口透明度
    opacity_value = round(float(value), 2)
    root.wm_attributes('-alpha', float(opacity_value))

    # 綁定Ctrl+方向鍵來控制滑動條的值
def increase_opacity(event):
    current_value = opacity_slider.get()
    new_value = min(current_value + 0.05, 1)  # 增加透明度，最大值為1
    opacity_slider.set(new_value)

def decrease_opacity(event):
    current_value = opacity_slider.get()
    new_value = max(current_value - 0.05, 0.35)  # 減少透明度，最小值為0.35
    opacity_slider.set(new_value)
    
    # 函數：切換視窗是否保持在最上層
def toggle_always_on_top():
    global always_on_top
    always_on_top = not always_on_top  # 切換布爾值
    root.attributes("-topmost", always_on_top)  # 設置視窗屬性
    # 更新選單文字
    if always_on_top:
        menu.entryconfig(0, label="取消置頂")
    else:
        menu.entryconfig(0, label="視窗置頂")

# 狀態變量
always_on_top = False

def show_menu(event):
    menu.post(event.x_root, event.y_root)

# 定義用於驗證的函數
def validate_input(char):
    # 如果輸入的是空白鍵，則返回 False，否則返回 True
    if char == ' ':
        return False
    return True

# 設置GUI
root = tk.Tk()
root.title("股票資訊")
root.geometry("230x190")  # 縮小視窗尺寸
root.configure(bg="#F7F8F9")  # 背景色改為淺灰
root.resizable(False, False)  # 禁止放大視窗

# 右鍵選單
menu = Menu(root, tearoff=0)
menu.add_command(label="視窗置頂", command=toggle_always_on_top)
menu.add_command(label="盤後資訊", command=lambda: show_post_market_info(root))  # 傳遞主視窗 root

# 綁定右鍵選單到主視窗
root.bind("<Button-3>", show_menu)

# 綁定關閉事件
root.protocol("WM_DELETE_WINDOW", on_closing)

# 設置驗證命令
vcmd = (root.register(validate_input), "%S")  # "%S" 代表正在被輸入的字符

# 標題字型
label_font = ("Arial", 13, "bold")
value_font = ("Arial", 12)

# 顯示股價
price_label = tk.Label(root, text="目前股價: ", font=label_font, width=35, anchor="w", bg="#F7F8F9", fg="#333")
price_label.pack(pady=2)

# 顯示漲跌幅
change_label = tk.Label(root, text="漲跌幅: ", font=label_font, width=35, anchor="w", bg="#F7F8F9", fg="#333")
change_label.pack(pady=2)

# 顯示成交量
volume_label = tk.Label(root, text="成交量: ", font=label_font, width=35, anchor="w", bg="#F7F8F9", fg="#333")
volume_label.pack(pady=2)

# 顯示股票代碼
stock_code_label = tk.Label(root, text="股票名稱: ", font=label_font, width=35, anchor="w", bg="#F7F8F9", fg="#333")
stock_code_label.pack(pady=2)

# 輸入股票代碼
stock_code_input = tk.Entry(root, font=value_font, width=10, bd=2, relief="solid", validate="key", validatecommand=vcmd)
stock_code_input.pack(anchor='w', padx=5, pady=5)  # 每個控件將顯示在新的一行
# 聚焦到輸入框並打開對話框
stock_code_input.focus_set()  # 自動將焦點設置到輸入框

# 創建一個框架 (Frame) 用來放置兩個按鈕
button_frame = tk.Frame(root)
button_frame.pack(anchor='w',pady=2)

# 按鈕: 開始抓取股市資料
fetch_button = tk.Button(button_frame, text="To The Moon", font=("Arial", 11, "bold"), bg="#4289CA", fg="Black", command=fetch_data, relief="raised", width=10)
fetch_button.pack(side="left", padx=5)  # 按鈕將放在下一行
root.bind('<Return>', lambda event: fetch_button.invoke())

# 按鈕: 停止更新
stop_button = tk.Button(button_frame, text="暫停更新", font=("Arial", 11, "bold"), bg="gray", fg="white", command=stop_update, relief="raised", width=10)
stop_button.pack(side="left", padx=5)  # 停止更新按鈕放在最後一行
root.bind('<space>', lambda event: stop_button.invoke())

# 創建滑動條，範圍從 0 到 1，表示透明度從 0% 到 100%
opacity_slider = ttk.Scale(root, from_=0.35, to_=1,orient="horizontal", command=adjust_opacity)
opacity_slider.set(1)  # 默認透明度為 100%
opacity_slider.pack(anchor="w", pady=5)

# 設置滑動條樣式
style = ttk.Style()
style.configure("TScale",
                thickness=7,  # 增加滑動條的高度
                sliderlength=20,  # 調整滑塊的大小
                )

# 綁定鍵盤事件
root.bind('<Control-Left>', decrease_opacity)  # Ctrl + 左箭頭減少透明度
root.bind('<Control-Right>', increase_opacity)  # Ctrl + 右箭頭增加透明度

# 綁定 Esc 鍵來觸發 on_closing()
root.bind('<Escape>', on_closing)

# 顯示窗體
root.mainloop()