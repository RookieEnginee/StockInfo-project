import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import re
from concurrent.futures import ThreadPoolExecutor
import time
import math
import threading
from threading import Lock

progress_lock = Lock()  # 創建一個鎖對象
stop_event = threading.Event() # 創建 Event 用於控制線程終止

def get_stock_data(stock_code, start_date,end_date,TWO,days):

    if TWO:
        # 如果股票代碼中沒有 .TW，則自動附加 .TW
        if not stock_code.endswith(".TWO"):
            stock_code = f"{stock_code}.TWO"
    else:
        # 如果股票代碼中沒有 .TW，則自動附加 .TW
        if not stock_code.endswith(".TW"):
            stock_code = f"{stock_code}.TW"

    retries = 0  # 記錄已重試次數
    while retries < 2:  # 最多試 2 次

        # 獲取歷史資料，使用 start 和 end 參數來指定日期範圍
        with progress_lock:
            stock_data = yf.download(stock_code, start=start_date, end=end_date, progress=False)
        # 顯示數據
        #print(stock_data['Volume'])
        #print(f"資料行數: {len(stock_data['Volume'])}")
        if stock_data.empty == False:
            # 获取成交量并计算总和
            trade_volumes = stock_data['Volume']
            total_volume = trade_volumes.sum()
            #print(f"總成交量: {total_volume}")
            # 如果 total_volume 是 Series，提取其中的第一个数值
            if isinstance(total_volume, pd.Series):
                total_volume = int(total_volume.iloc[0])  # 提取第一个值
                yesterday_volume = int(trade_volumes.values[-1])  # 提取前一天的成交量

            close_series = stock_data['Close'].squeeze()
            # 去除 NaN 並計算最大值，保留小數點後兩位
            Stock_High_Price = round(close_series.dropna().max(), 2)

            #print(f"最高價: {Stock_High_Price}")
            return total_volume // 1000 // days,yesterday_volume // 1000,Stock_High_Price  # 返回平均成交量
        else:
            retries += 1  # 增加重試次數
            time.sleep(0.5)  # 延遲 0.5 秒

    print("達到最大重試次數，將返回 0")
    return 0,0,0  # 如果達到最大重試次數，返回 0



def calculate_Start_date(days,End_date):
    # 計算正確啟始日期
    # 初始化日期為今天
    today_date = datetime.now()
    start_date = today_date - timedelta(days=days)
    start_date = start_date.strftime('%Y-%m-%d')    # 格式化日期
    stock_data = yf.download("2330.TW", start=start_date, end=End_date, progress=False)
    # 獲取歷史資料，使用 start 和 end 參數來指定日期範圍
    while len(stock_data['Volume']) < days:
        # 如果資料行數小於指定天數，start_date 往回推 1 天
        start_date = pd.to_datetime(start_date) - pd.Timedelta(days=1)
        start_date = start_date.strftime('%Y-%m-%d')  # 更新 start_date
        stock_data = yf.download("2330.TW", start=start_date, end=End_date, progress=False)
        if len(stock_data) == 0:
            break

    return start_date

def calculate_End_date():
    # 初始化日期為今天
    today_date = datetime.now()
    retries = 0  # 記錄已重試次數
    max_retries = 2  # 最大重試次數

    while retries < max_retries:
        # 將日期格式化為 YYYYMMDD
        formatted_date = today_date.strftime('%Y%m%d')

        # 產生目標 URL
        url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date={formatted_date}&type=ALL"

        try:
            # 發送 GET 請求下載 CSV 資料
            response = requests.get(url, timeout=15, verify=False)  # 設置超時為 5 秒
        except requests.RequestException as e:
            # 捕獲請求異常
            print(f"請求失敗: {e}")
            retries += 1
            today_date -= timedelta(days=1)
            continue

        # 檢查是否成功取得資料
        if response.status_code == 200 and response.text.strip():
            # 如果資料不為空，儲存 raw_data 並結束迴圈
            raw_data = response.text
            end_date = today_date.strftime('%Y-%m-%d')
            return end_date, raw_data
        else:
            # 如果資料為空，將日期往前推一天
            print(f"{formatted_date} 的資料為空，嘗試前一天...")
            today_date -= timedelta(days=1)
            retries += 1

    # 如果達到最大重試次數，拋出異常
    raise RuntimeError(f"無法獲取資料，已嘗試 {max_retries} 次。")


def process_stock(item, raw_data, days, start_date, end_date):
    # 計算平均成交量
    average_trade_volume, yesterday_volume, stock_high_price = get_stock_data(
        item["Code"], start_date, end_date, 0, days
    )

    # 成交量正則
    pattern = rf'="{item["Code"]}","[^"]*","([\d,]+)"|"{item["Code"]}","[^"]*","([\d,]+)"'
    match = re.search(pattern, raw_data)
    if not match:
        print(f"未找到股票 {item['Code']} 的成交量資料")
        return []

    trade_volume = match.group(1) or match.group(2)
    trade_volume = int(trade_volume.replace(",", "")) // 1000

    # 價格正則
    patternPrice = rf'"{item["Code"]}","[^"]*","[^"]*","[^"]*","[^"]*","[^"]*","[^"]*","[^"]*","([^"]+)",'
    matches = re.findall(patternPrice, raw_data)
    if not matches:
        print(f"未找到股票 {item['Code']} 的價格資料")
        return []
    StockPrice = matches[0]

    difference = trade_volume - average_trade_volume
    return {
        "股票代碼": item['Code'],
        "股票名字": item['Name'],
        "股票價格": StockPrice,
        "當日成交量": trade_volume,
        "過去成交量平均": average_trade_volume,
        "成交量差異": difference,
        "前一日成交量": yesterday_volume,
        "最高價": stock_high_price
    }

def process_batch(batch, raw_data, days, start_date, end_date,progress_bar):
    stockAlldata = []
    i = 0
    i = (100/(len(batch)*1))  # 計算迭代次數
    
    for item in batch:
        stockdata = process_stock(item, raw_data, days, start_date, end_date)
        if stockdata:  # 確保有結果時才追加
            # 使用鎖保護進度條更新
            with progress_lock:
                stockAlldata.append(stockdata)
                progress_bar['value'] += i
                progress_bar.update()

        if stop_event.is_set():  # 如果停止事件被設置，則終止處理
            print("停止計算，提前退出。")
            return stockAlldata

    return stockAlldata

def calculate_volume_difference(settingparams,result_text,start_date,end_date,raw_data,button,progress_bar):
    # 台灣證券交易所 API（上市股票）
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    # 台灣櫃買中心 API（上櫃股票）
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"

    # 取得上市股票資料
    twse_response = requests.get(twse_url, verify=False)
    twse_response.raise_for_status()
    twse_data = twse_response.json()

    # 取得上櫃股票資料
    tpex_response = requests.get(tpex_url, verify=False)
    tpex_response.raise_for_status()
    tpex_data = tpex_response.json()

    if settingparams["Filter_out_ETF"]:
        # 筛选掉 "Code" 以 "0" 开头的数据
        filtered_data = [item for item in twse_data if not item["Code"].startswith("0")]
    else:
        filtered_data = twse_data

    # 分批處理股票資料
    batch_size = math.ceil(len(filtered_data) / 1)
    batches = [filtered_data[i:i + batch_size] for i in range(0, len(filtered_data), batch_size)]

    # 結果存放在這裡
    all_results = []

    # 使用 ThreadPoolExecutor 處理
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [executor.submit(process_batch, batch, raw_data, settingparams["days"], start_date, end_date,progress_bar) for batch in batches]
        # 等待所有執行緒完成並收集結果
        for future in futures:
            try:
                batch_results = future.result()  # 獲取該執行緒的回傳值（處理的 batch 結果）
                if batch_results:  # 確保結果非空
                    all_results.extend(batch_results)  # 將每個 batch 的結果合併到主列表
            except Exception as e:
                print(f"執行緒處理出錯：{e}")

    # 查看最終結果
    #for result in all_results:
        #print(result)
    result_text.tag_configure("green", foreground="green")
    # 顯示結果
    for data in all_results:
        if (
            data["當日成交量"] >= (data["過去成交量平均"] * settingparams["threshold"])
            and data["成交量差異"] != 0
            and data["當日成交量"] >= settingparams["samedayvolume"]
            and (settingparams["start_blowing"] == False or (data["前一日成交量"] <= data["過去成交量平均"] * 1.5))):

            result_text.insert(tk.END, f"股票代碼: {data['股票代碼']} {data['股票名字']}\n")
            result_text.insert(tk.END, f"股票價格: {data['股票價格']}\n")
            result_text.insert(tk.END, f"當日成交量: {data['當日成交量']} \n")
            result_text.insert(tk.END, f"過去{settingparams['days']}天成交量平均: {data['過去成交量平均']} \n")
            result_text.insert(tk.END, f"成交量差異: {data['成交量差異']} \n")

            # 插入超連結
            yahoo_url = f"https://tw.stock.yahoo.com/quote/{data['股票代碼']}/technical-analysis"
            result_text.insert(tk.END, "詳細資料", ("link", yahoo_url))
            result_text.insert(tk.END, "\n\n")  # 分隔行

        # 確保 settingparams["HighPricedown"] 是數字
        HighPricedown = float(settingparams["HighPricedown"])
        # 檢查是否為空字串，若是空字串則賦予預設值（例如 0）
        股票價格 = safe_float(data["股票價格"])
        最高價 = safe_float(data["最高價"])
        if (最高價 != 0 and 股票價格!=0):
            差異價數 = (最高價 - 股票價格) / 最高價 * 100
            差異價數 = round(差異價數, 2)  # 保留兩位小數
            建議買進價格 = 最高價*0.75
        else:
            差異價數 = 0
            股票價格 = 0
            最高價 = 0
            建議買進價格 = 0

        if (HighPricedown <= 差異價數) and 股票價格!=0 and 最高價!=0:
            result_text.insert(tk.END, f"股票代碼: {data['股票代碼']} {data['股票名字']}\n","green")
            result_text.insert(tk.END, f"股票價格: {data['股票價格']}\n", "green")
            result_text.insert(tk.END, f"前{settingparams['days']}天最高價: {最高價} \n", "green")
            result_text.insert(tk.END, f"最高價差異: {差異價數}% \n","green")
            result_text.insert(tk.END, f"建議買進價格: {建議買進價格} \n","green")

            # 插入超連結
            yahoo_url = f"https://tw.stock.yahoo.com/quote/{data['股票代碼']}/technical-analysis"
            result_text.insert(tk.END, "詳細資料", ("link", yahoo_url))
            result_text.insert(tk.END, "\n\n")  # 分隔行

    # 配置超連結樣式和行為
    def open_link(event):
        # 獲取點擊的超連結
        link = result_text.tag_names(tk.CURRENT)[1]  # 取得標籤名稱
        import webbrowser
        webbrowser.open(link)  # 打開超連結
        result_text.tag_configure(link, foreground="purple",underline=True)  # 點擊過的超連結變成紫色

    # 設置超連結樣式
    result_text.tag_config("link", foreground="blue", underline=True)  # 設定藍色字體和底線
    result_text.tag_bind("link", "<Button-1>", open_link)  # 綁定點擊事件

    # 啟用按鈕
    button.config(state=tk.NORMAL, text="前往礦坑", fg="black")
    return 

def on_calculate(button,progress_bar,result_text,settingparams_entry):
    # 重置進度條的值
    progress_bar['value'] = 0  # 進度條設為0
    progress_bar.update_idletasks()  # 更新顯示
    result_text.delete("1.0", tk.END)  # 清空文本區域
    try:
        # 提取參數並轉換成int
        settingparams = {
            "days": int(settingparams_entry["days"].get()),
            "threshold": int(settingparams_entry["threshold"].get()),
            "samedayvolume": int(settingparams_entry["same_day_volume"].get()),
            "start_blowing": settingparams_entry["start_blowing"].get(),
            "Filter_out_ETF": settingparams_entry["Filter_out_ETF"].get(),
            "HighPricedown": settingparams_entry["HighPricedown"].get()
        }
        # 禁用按鈕，防止重複點擊
        button.config(state=tk.DISABLED, text="撿鑽石...", fg="White", disabledforeground="White")
        stop_event.clear()  # 清除 Event，以便下次重新啟動線程
        # 計算結束日期
        end_date ,raw_data= calculate_End_date()
        # 計算啟始日期
        start_date = calculate_Start_date(settingparams["days"],end_date)    
        # 插入格式化後的日期
        result_text.insert(tk.END, f"當日日期: {end_date} \r\n", "center")
        result_text.insert(tk.END, "\r\n", "center")  # 空一行也设置居中
        # 啟動一個新線程來處理計算
        calculate_thread = threading.Thread(target=calculate_volume_difference, args=(settingparams,result_text,start_date,end_date,raw_data,button,progress_bar))
        calculate_thread.daemon = True
        calculate_thread.start()

    except (ValueError, RuntimeError) as e:  # 捕获多个异常
        button.config(state=tk.NORMAL, text="前往礦坑", fg="black")  
        if isinstance(e, ValueError):
            messagebox.showerror("輸入錯誤", "請輸入有效的數字！")      
        elif isinstance(e, RuntimeError):
            messagebox.showerror("錯誤", "無法獲取資料，請等TWSE資料庫更新！")
        
def show_post_market_info(root):

    # 創建一個新的視窗來顯示盤後資訊
    post_market_window = tk.Toplevel(root)
    post_market_window.title("盤後資訊")
    post_market_window.geometry("400x500")

    # 驗證函數
    def validate_days(new_value):
        """限制天數只能是 1~25 的數字"""
        if new_value == "" or (new_value.isdigit() and 1 <= int(new_value) <= 25):
            return True
        return False

    def validate_threshold(new_value):
        """限制成交量倍數只能是 2 或更大的數字"""
        if new_value == "" or (new_value.isdigit() and 2 <= int(new_value) <= 99):
            return True
        return False

    # 註冊驗證函數
    vcmd_days = post_market_window.register(validate_days)
    vcmd_threshold = post_market_window.register(validate_threshold)

    # 創建輸入區域 Frame
    entry_frame = tk.Frame(post_market_window)
    entry_frame.pack(anchor="center", padx=10, pady=10)

    # 設定天數 (過去 N 天) 和 "剛開始爆量" 置於同一行
    tk.Label(entry_frame, text="設定天數 (過去1~25天)", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
    days_entry = tk.Entry(entry_frame, font=("Arial", 12), width=8, validate="key", validatecommand=(vcmd_days, "%P"))
    days_entry.grid(row=0, column=1, padx=5, pady=5)
    days_entry.insert(0, "25")  # 預設值為 25
    days_entry.focus_set()  # 設置焦點
    Tooltip(days_entry, text="取當日往前N天成交量平均") # 為 "設定天數" 添加 Tooltip

    # 新增 "剛開始爆量" 的選項，放在右邊
    start_blowing_var = tk.BooleanVar(value=True)  # 用於跟踪勾選狀態，默認為 False
    start_blowing_checkbox = tk.Checkbutton(entry_frame, text="剛開始爆量", variable=start_blowing_var, font=("Arial", 10))
    start_blowing_checkbox.grid(row=0, column=2, padx=5, pady=5, sticky="w")  # 放在同一行的右邊
    Tooltip(start_blowing_checkbox, text="(前一日成交量)<=(往前N天成交量平均*1.5)") # 為 "剛開始爆量" 添加 Tooltip

    # 新增 "過濾ETF/ETN" 的選項，放在右邊
    Filter_out_ETF = tk.BooleanVar(value=True)  # 用於跟踪勾選狀態，默認為 False
    Filter_out_ETF_checkbox = tk.Checkbutton(entry_frame, text="過濾ETF/ETN", variable=Filter_out_ETF, font=("Arial", 10))
    Filter_out_ETF_checkbox.grid(row=1, column=2, padx=5, pady=5, sticky="w")  # 放在同一行的右邊

    # 成交量倍數
    tk.Label(entry_frame, text="設定成交量倍數", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
    threshold_entry = tk.Entry(entry_frame, font=("Arial", 12), width=8, validate="key", validatecommand=(vcmd_threshold, "%P"))
    threshold_entry.grid(row=1, column=1, padx=5, pady=5)
    threshold_entry.insert(0, "3")  # 預設值為 3
    Tooltip(threshold_entry, text="(當日成交量)>=(往前N天成交量平均*倍數)") # 為 "成交量倍數" 添加 Tooltip

    # 設定當日成交量大於N
    tk.Label(entry_frame, text="設定當日成交量大於", font=("Arial", 12)).grid(row=2, column=0, padx=5, pady=5, sticky="e")
    SamedayVolume_entry = tk.Entry(entry_frame, font=("Arial", 12), width=8)
    SamedayVolume_entry.grid(row=2, column=1, padx=5, pady=5)
    SamedayVolume_entry.insert(0, "500")  # 預設值為 500

    # 設定最高往下幾%的股票
    tk.Label(entry_frame, text="前N天最高價往下幾%", font=("Arial", 12)).grid(row=3, column=0, padx=5, pady=5, sticky="e")
    HighPricedown_entry = tk.Entry(entry_frame, font=("Arial", 12), width=8)
    HighPricedown_entry.grid(row=3, column=1, padx=5, pady=5)
    HighPricedown_entry.insert(0, "22")  # 預設值為 22
    
    # 收集參數，直接存儲小部件引用
    settingparams_entry = {
        "days": days_entry,
        "start_blowing": start_blowing_var,
        "Filter_out_ETF": Filter_out_ETF,
        "threshold": threshold_entry,
        "same_day_volume": SamedayVolume_entry,
        "HighPricedown": HighPricedown_entry
    }
    # 結果顯示區域
    result_text = tk.Text(post_market_window, width=50, height=15, font=("Arial", 10))
    result_text.tag_configure("center", justify='center')  # 設置居中對齊
    result_text.pack(pady=5)
    result_text.delete(1.0, tk.END)
    result_text.place(relx=0.5, rely=0.55, relwidth=0.8, relheight=0.5,anchor="center")  # 使用相對比例定位按鈕

    # 創建進度條
    progress_bar = ttk.Progressbar(post_market_window, orient="horizontal", length=300, mode="determinate")
    progress_bar.pack(pady=10)
    progress_bar.place(relx=0.5, rely=0.86, anchor="center")  # 使用相對比例定位按鈕

    def on_closing(event=None):
        stop_event.set()  # 設置 Event，通知線程終止
        post_market_window.destroy()

    def on_stop():
        stop_event.set()  # 設置 Event，通知線程終止

    # 創建一個框架 (Frame) 用來放置兩個按鈕
    button_frame = tk.Frame(post_market_window)
    button_frame.pack(anchor='center',pady=5)
    button_frame.place(relx=0.5, rely=0.96, anchor="center")  # 使用相對比例定位按鈕

    # 添加計算按鈕
    calculate_button = tk.Button(button_frame, text="前往礦坑", font=("Arial", 11, "bold"), bg="#4289CA", fg="black",command=lambda: on_calculate(calculate_button,progress_bar,result_text,settingparams_entry),relief="raised", width=10)
    calculate_button.pack(side="left", padx=5)
    post_market_window.bind('<Return>', lambda event: calculate_button.invoke())  # 綁定 Enter 鍵
    calculate_button.pack(pady=5)

    # 添加暫停按鈕
    stop_button = tk.Button(button_frame, text="收工", font=("Arial", 11, "bold"),bg="gray", fg="white",command=on_stop, relief="raised", width=10)
    stop_button.pack(side="left", padx=5)
    post_market_window.bind('<space>', lambda event: stop_button.invoke()) # 綁定空格鍵
    stop_button.pack(pady=5)

    # 綁定 Esc 鍵來觸發 on_closing()
    post_market_window.bind('<Escape>', on_closing)
    post_market_window.protocol("WM_DELETE_WINDOW", on_closing)  # 綁定關閉按鈕

class Tooltip:
    """用於顯示提示框的類"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)  # 滑鼠進入時顯示提示框
        self.widget.bind("<Leave>", self.hide_tooltip)  # 滑鼠離開時隱藏提示框

    def show_tooltip(self, event):
        """顯示提示框"""
        if self.tooltip_window:
            return
        # 創建一個新窗口作為提示框
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # 移除邊框
        self.tooltip_window.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")  # 設置提示框位置

        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            background="yellow",
            relief="solid",
            borderwidth=1,
            font=("Arial", 10)
        )
        label.pack()

    def hide_tooltip(self, event):
        """隱藏提示框"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
def safe_float(value):
    try:
        return float(value)  # 嘗試將值轉換為浮點數
    except ValueError:
        return 0  # 如果發生錯誤（例如非數字），則返回預設值 0