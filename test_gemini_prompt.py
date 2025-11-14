import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. 設定區 (讀取 .env) ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("錯誤：未能在 .env 檔案中找到 GEMINI_API_KEY。")
    exit()

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    print(f"Gemini 設定失敗: {e}")
    exit()

# --- 2. 我們的主力 Prompt (與主程式完全相同) ---
# (這是我們要測試的核心)
PROMPT_TEMPLATE = """
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
{web_text}
---
網站文字結束。

請嚴格回傳 JSON：
"""

# --- 3. 測試用的「假網頁文字」 ---

# 測試案例 1: 模擬 DV-2027 公告 (標準格式)
mock_text_1 = """
Some random text about other visas...
DV-2026 results are available.
...
The online registration period for the DV-2027 Program will begin
on Wednesday, October 1, 2025, at 12:00 noon, Eastern Daylight Time (EDT), 
and will conclude on Tuesday, November 4, 2025, at 12:00 noon, Eastern 
Standard Time (EST). We strongly encourage DV program entrants to apply early.
"""

# 測試案例 2: 模擬 DV-2027 公告 (不同措辭)
mock_text_2 = """
...
DV-2027 Program: The entry submission period for DV-2027
is from 12:00 PM (noon), EDT, on October 2, 2025, 
to 12:00 PM (noon), EST, on November 5, 2025.
...
You must submit your entry for the DV-2027 program electronically.
"""

# 測試案例 3: 模擬「尚未公布」的狀態 (現在的真實情況)
mock_text_3 = """
...
DV-2026 Entrants may check their results now.
The registration period for DV-2026 is closed.
Information regarding the DV-2027 program is not yet available.
Please check back later.
...
"""

# --- 4. 執行測試的函式 ---

def run_test(test_name, mock_text):
    """
    接收假文字，呼叫 Gemini API 並印出結果。
    """
    print(f"\n--- 執行測試: {test_name} ---")
    
    # 組合 Prompt
    final_prompt = PROMPT_TEMPLATE.format(web_text=mock_text)
    
    # 設定 Gemini 回傳 JSON
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json"
    )

    try:
        # 呼叫 API
        response = model.generate_content(
            final_prompt,
            generation_config=generation_config
        )
        
        # 印出 AI 的 JSON 回應
        print("Gemini API 的回應:")
        print(response.text)
        
        # 嘗試解析 JSON 並給出易讀的結論
        try:
            data = json.loads(response.text)
            print(f"【結論】: AI 抓到: {data}")
        except json.JSONDecodeError:
            print("【結論】: 錯誤! Gemini 沒有回傳標準 JSON。")

    except Exception as e:
        print(f"呼叫 Gemini API 時發生錯誤: {e}")

# --- 5. 主程式 ---
if __name__ == "__main__":
    print("=== 開始測試 Gemini Prompt 的準確性 ===")
    
    run_test("測試案例 1 (標準格式)", mock_text_1)
    run_test("測試案例 2 (不同措辭)", mock_text_2)
    run_test("測試案例 3 (尚未公布)", mock_text_3)
    
    print("\n=== 測試完畢 ===")