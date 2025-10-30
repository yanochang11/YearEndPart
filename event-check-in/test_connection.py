# test_connection.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Google Sheets 連線測試",
    layout="centered"
)

st.title("🧪 Google Sheets 連線測試")

# --- 1. 檢查 Streamlit Secrets 是否存在 ---
st.header("1. 檢查 Secrets 設定")
if "gcp_service_account" in st.secrets:
    st.success("✅ `[gcp_service_account]` 區段存在於 Streamlit Secrets 中。")
    
    # 為了安全，只顯示金鑰的類型和專案ID，不顯示私鑰
    try:
        creds_dict = st.secrets.get("gcp_service_account")
        st.write(f"**專案 ID (Project ID):** `{creds_dict.get('project_id', '未找到')}`")
        st.write(f"**服務帳號 Email:** `{creds_dict.get('client_email', '未找到')}`")
    except Exception as e:
        st.error(f"讀取 Secrets 內容時出錯：{e}")

else:
    st.error("❌ 在 Streamlit Secrets 中找不到 `[gcp_service_account]` 區段！")
    st.info("請檢查您的 `.streamlit/secrets.toml` 檔案是否已正確複製到 Streamlit Cloud 的設定中。")
    st.stop() # 如果連 secrets 都沒有，就停止執行

# --- 2. 嘗試連線到 Google Sheets ---
st.header("2. 嘗試進行連線")

@st.cache_resource
def connect_to_gsheet():
    """使用 st.secrets 中的憑證連線到 Google Sheets"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(
            st.secrets.gcp_service_account,
            scopes=scope
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return str(e) # 如果出錯，返回錯誤訊息字串

with st.spinner("正在使用憑證連線到 Google API..."):
    connection_result = connect_to_gsheet()

if isinstance(connection_result, gspread.Client):
    st.success("✅ 成功授權並建立 Google Sheets Client！")
    st.session_state.gsheet_client = connection_result
else:
    st.error(f"❌ 連線失敗！")
    st.code(connection_result, language=None) # 顯示詳細的錯誤訊息
    st.stop()

# --- 3. 嘗試開啟指定的 Google Sheet ---
st.header("3. 嘗試開啟您的試算表")

GOOGLE_SHEET_NAME = "Event_Check-in" # 請確保這個名稱和您的一樣
st.info(f"正在嘗試開啟名為 **`{GOOGLE_SHEET_NAME}`** 的試算表...")

try:
    with st.spinner(f"正在開啟 '{GOOGLE_SHEET_NAME}'..."):
        spreadsheet = st.session_state.gsheet_client.open(GOOGLE_SHEET_NAME)
    st.success("✅ 成功開啟試算表！")
    
    # --- 4. 列出所有工作表 ---
    st.header("4. 列出試算表中的所有工作表")
    worksheets = spreadsheet.worksheets()
    for ws in worksheets:
        st.write(f"- `{ws.title}` (共有 {ws.row_count} 列)")
    
    st.balloons()
    st.success("🎉 **恭喜！所有測試已通過！**")
    st.info("這代表您的 Streamlit Secrets 和 Google Sheets 權限設定完全正確。現在可以將 `app.py` 部署回來了。")

except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"❌ 找不到名為 '{GOOGLE_SHEET_NAME}' 的試算表！")
    st.warning("請檢查：")
    st.markdown("""
    - 您的 Google Sheet 檔案名稱是否完全相符？
    - 您是否已將服務帳號的 email (`{st.secrets.gcp_service_account.client_email}`) 分享給這個試算表，並給予「編輯者」權限？
    """)
except Exception as e:
    st.error(f"❌ 開啟試算表時發生未知錯誤！")
    st.code(e, language=None)
