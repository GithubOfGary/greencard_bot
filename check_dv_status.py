import requests
from bs4 import BeautifulSoup
import json
import os
import re
import telegram
import asyncio
from dotenv import load_dotenv
import datetime
import google.generativeai as genai  # 1. 匯入 Gemini

# --- 1. 設定區 (從 .env 讀取) ---
load_dotenv()
YOUR_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUR_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # 2. 讀取 Gemini 金鑰

# 檢查 Telegram 金鑰
if not YOUR_TELEGRAM_BOT_TOKEN or not YOUR_TELEGRAM_CHAT_ID:
    print("錯誤：未能在 .env 檔案中找到 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID。")
    exit()

# 3. 檢查並設定 Gemini
if not GEMINI_API_KEY:
    print("錯誤：未能在 .env 檔案中找到 GEMINI_API_KEY。")
    exit()

genai.configure(api_key=GEMINI_API_KEY)
# 使用 1.5 Flash，它速度快且成本低，非常適合這類任務
model = genai.GenerativeModel('gemini-2.5-flash') 

DV_INFO_URL = "https://travel.state.gov/content/travel/en/us-visas/immigrate/diversity-visa-program-entry.html"
STATE_FILE = "dv_date_status_gemini.json" # 換個新檔案名，避免和舊版衝突

# --- 2. 輔助函式：取得時間 (不變) ---
def get_current_time_string():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

# --- 3. 【全新】使用 Gemini 提取資訊 ---

def get_dv_info_with_gemini():
    """
    爬取 DV 指南頁面，並使用 Gemini API 提取最新開放日期。
    """
    
    # 步驟 1: 爬取網頁文字
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
        }
        response = requests.get(DV_INFO_URL, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        article_content = soup.find('article')
        
        if not article_content:
            page_text = soup.get_text()
        else:
            page_text = article_content.get_text()
        
        # 限制文字長度，避免 API 費用過高或請求過大 (15000 個字元通常足夠)
        page_text = page_text[:15000]

    except requests.exceptions.RequestException as e:
        print(f"抓取網頁時發生錯誤: {e}")
        return None, None # 返回 None 表示此次抓取失敗

    # 步驟 2: 呼叫 Gemini API
    try:
        # 這是關鍵的 Prompt，指示 Gemini 如何行動並回傳 JSON
        prompt = f"""
        你是一個資訊提取助理。請仔細分析以下來自美國國務院官方網站的文字，
        提取出【最新】的「多元簽證計畫 (Diversity Visa)」的資訊。

        請嚴格按照以下 JSON 格式回傳。
        如果文字中沒有提到相關資訊，請在欄位中回傳 "Not Found"。

        {{
          "program_year": "例如: DV-2027",
          "start_date": "例如: October 1, 2025",
          "end_date": "例如: November 4, 2025"
        }}

        ---
        網站文字開始：
        {page_text}
        ---
        網站文字結束。

        請嚴格回傳 JSON：
        """

        # 設定 Gemini 回傳 JSON 格式
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json"
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        # 步驟 3: 解析 Gemini 的 JSON 回應
        data = json.loads(response.text)
        
        dv_year = data.get("program_year", "Not Found")
        start_date = data.get("start_date", "Not Found")
        end_date = data.get("end_date", "Not Found")

        if "Not Found" in [dv_year, start_date, end_date] or dv_year is None:
            print("Gemini 回報：未在文字中找到指定日期資訊。")
            return "not_found", "尚未公布"

        # 建立用來比對的 ID 和通知訊息
        identifier = f"{dv_year}-{start_date}-{end_date}"
        info_string = f"{dv_year} 申請時間: {start_date} 至 {end_date}"
        
        return identifier, info_string

    except Exception as e:
        print(f"呼叫 Gemini API 或解析 JSON 時發生錯誤: {e}")
        # 如果 API 失敗，印出原始回傳內容以供除錯
        if 'response' in locals():
            print(f"Gemini 原始回傳 (可能非 JSON): {response.text}")
        return None, None

# --- 4. 狀態儲存 (不變) ---

def load_last_status_id():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_status_id')
    except json.JSONDecodeError:
        return None

def save_current_status_id(status_id):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'last_status_id': status_id}, f)
    except IOError as e:
        print(f"儲存狀態時發生錯誤: {e}")

# --- 5. Telegram 通知 (不變) ---

async def send_telegram_notification(message):
    try:
        bot = telegram.Bot(token=YOUR_TELEGRAM_BOT_TOKEN)
        # 增加 disable_web_page_preview 避免 URL 預覽佔版面
        await bot.send_message(chat_id=YOUR_TELEGRAM_CHAT_ID, 
                               text=message, 
                               disable_web_page_preview=True) 
        print(f"成功發送 Telegram 通知")
    except Exception as e:
        print(f"發送 Telegram 通知時失敗: {e}")

# --- 6. 主程式 (修改了函式呼叫) ---

def main():
    print(f"--- {get_current_time_string()} ---")
    print("--- 開始執行 DV 日期檢查 (Gemini 版) ---")
    
    # 4. *** 呼叫新的 Gemini 函式 ***
    current_status_id, current_info = get_dv_info_with_gemini() 
    
    if current_status_id is None:
        print("無法取得目前狀態，本次跳過。")
        error_message = (
            f"❌ 機器人爬蟲錯誤 (DV Program - Gemini 版):\n\n"
            f"無法抓取 {DV_INFO_URL} 或呼叫 Gemini API 失敗。\n"
            f"請檢查程式日誌。\n"
            f"(檢查時間: {get_current_time_string()})"
        )
        asyncio.run(send_telegram_notification(error_message))
        return

    last_status_id = load_last_status_id()

    print(f"上次狀態 ID: {last_status_id}")
    print(f"目前狀態 ID: {current_status_id}")
    print(f"Gemini 抓取到資訊: {current_info}")

    if current_status_id != last_status_id:
        print("偵測到日期資訊變更！準備發送通知...")
        
        message = (
            f"🔔 美國綠卡抽籤 (DV Program) 日期更新！ (AI 驗證)\n\n"
            f"【最新資訊】\n{current_info}\n\n"
            f"請立刻至官方網站確認：\n{DV_INFO_URL}"
        )
        
        asyncio.run(send_telegram_notification(message))
        save_current_status_id(current_status_id) # 只有變更時才儲存
        
    else:
        print("日期資訊未變更，發送例行通知。")
        timestamp = get_current_time_string()
        message = (
            f"🤖 機器人例行回報 (DV Program - AI 版):\n\n"
            f"狀態無變化。\n"
            f"AI 監控資訊: {current_info}\n"
            f"(檢查時間: {timestamp})"
        )
        
        asyncio.run(send_telegram_notification(message))

    print("--- 檢查完畢 ---")

if __name__ == "__main__":
    main()