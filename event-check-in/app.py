# app_v1.2.0.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe
from datetime import datetime, time
import pytz
import streamlit.components.v1 as components

# --- App Version ---
VERSION = "1.2.0 (Final Stable Release)"

# --- Configuration ---
TIMEZONE = "Asia/Taipei"
GOOGLE_SHEET_NAME = "Event_Check-in"
WORKSHEET_NAME = "Sheet1"
SUCCESS_SOUND_URL = "https://cdn.jsdelivr.net/gh/yanochang11/yearendpart@main/event-check-in/assets/success.mp3"
ERROR_SOUND_URL = "https://cdn.jsdelivr.net/gh/yanochang11/yearendpart@main/event-check-in/assets/error.mp3"

# --- Page Configuration ---
st.set_page_config(
    page_title=f"活動報到系統 v{VERSION}",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS (僅保留基本排版，以適應系統主題) ---
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    /* 確保隱藏的輸入框在視覺上不可見 */
    div[data-testid="stTextInput"] input[placeholder="__fingerprint_placeholder__"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)


# --- Google Sheets Connection ---
@st.cache_resource(ttl=600)
def get_gsheet():
    """Establishes a connection to the Google Sheet using cached credentials."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets.gcp_service_account, scope)
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=30)
def get_data(_client, sheet_name, worksheet_name):
    """Fetches and caches data from the worksheet."""
    try:
        sheet = _client.open(sheet_name).worksheet(worksheet_name)
        data = get_as_dataframe(sheet, evaluate_formulas=True)
        for col in ['EmployeeID', 'DeviceFingerprint']:
            if col in data.columns:
                data[col] = data[col].astype(str).str.strip()
        return data.dropna(how='all')
    except Exception as e:
        st.error(f"無法讀取資料表 '{sheet_name}/{worksheet_name}'。錯誤: {e}")
        return pd.DataFrame()

def update_cell(client, sheet_name, worksheet_name, row, col, value):
    """Updates a single cell and clears caches."""
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        get_data.clear()
    except Exception as e:
        st.error(f"更新 Google Sheet 失敗: {e}")

# --- Settings Management ---
@st.cache_data(ttl=60)
def get_settings(_client, sheet_name):
    """Fetches settings from the 'Settings' worksheet."""
    try:
        settings_sheet = _client.open(sheet_name).worksheet("Settings")
        mode = settings_sheet.acell('A2').value
        start_time = datetime.strptime(settings_sheet.acell('B2').value, '%H:%M').time()
        end_time = datetime.strptime(settings_sheet.acell('C2').value, '%H:%M').time()
        return {"mode": mode, "start_time": start_time, "end_time": end_time}
    except Exception as e:
        st.error(f"無法載入設定，將使用預設值。錯誤: {e}")
        return {"mode": "Check-in", "start_time": time(9, 0), "end_time": time(17, 0)}

def save_settings(client, sheet_name, mode, start_time, end_time):
    """Saves settings to the 'Settings' worksheet."""
    try:
        settings_sheet = client.open(sheet_name).worksheet("Settings")
        settings_sheet.update('A2:C2', [[mode, start_time.strftime('%H:%M'), end_time.strftime('%H:%M')]])
        get_settings.clear()
        st.success("設定已儲存!")
    except Exception as e:
        st.error(f"儲存設定失敗: {e}")


def main():
    """Main function to run the Streamlit application."""
    st.title("活動報到系統")
    st.markdown(f"<p style='text-align: right; color: grey;'>v{VERSION}</p>", unsafe_allow_html=True)

    # --- (核心) 裝置識別碼處理 (完全採用您最初的、最穩定的程式碼) ---
    js_code = '''
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      function setFingerprint() {
        const fpPromise = FingerprintJS.load();
        fpPromise
          .then(fp => fp.get())
          .then(result => {
            const visitorId = result.visitorId;
            console.log("Device Fingerprint:", visitorId); // 保留您需要的 Console Log
            let attempts = 0;
            const maxAttempts = 50;
            const intervalId = setInterval(() => {
                attempts++;
                const input = window.parent.document.querySelector('input[placeholder="__fingerprint_placeholder__"]');
                if (input) {
                    if(input.value === "" || input.value === "__fingerprint_placeholder__") {
                        input.value = visitorId;
                        const event = new Event('input', { bubbles: true });
                        input.dispatchEvent(event);
                        console.log('Fingerprint set successfully into hidden field.'); // 保留您需要的 Console Log
                    }
                    clearInterval(intervalId);
                } else if (attempts >= maxAttempts) {
                    clearInterval(intervalId);
                    console.error('Failed to find the fingerprint input field.');
                }
            }, 100);
          })
          .catch(error => console.error(error));
      }
      setFingerprint();
    </script>
    '''
    components.html(js_code, height=0)

    # 隱藏的輸入元件，作為 JS 和 Python 之間的穩定橋樑
    st.text_input("Device Fingerprint", key="device_fingerprint_hidden", label_visibility="hidden",
                  placeholder="__fingerprint_placeholder__")

    # --- App State Initialization ---
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'search_term' not in st.session_state: st.session_state.search_term = ""
    if 'selected_employee_id' not in st.session_state: st.session_state.selected_employee_id = None
    if 'feedback' not in st.session_state: st.session_state.feedback = None
    if 'sound_to_play' not in st.session_state: st.session_state.sound_to_play = None

    # --- 主應用程式流程 ---
    client = get_gsheet()
    settings = get_settings(client, GOOGLE_SHEET_NAME)
    st.info(f"**目前模式:** `{settings['mode']}`")

    # --- Admin Panel ---
    with st.sidebar.expander("管理員面板", expanded=False):
        if not st.session_state.authenticated:
            password = st.text_input("請輸入密碼:", type="password")
            if st.button("登入"):
                if password == st.secrets.admin.password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("密碼錯誤")
        else:
            st.success("已認證")
            mode = st.radio("模式", ["Check-in", "Check-out"], index=["Check-in", "Check-out"].index(settings['mode']))
            start_time = st.time_input("開始時間", settings['start_time'])
            end_time = st.time_input("結束時間", settings['end_time'])
            if st.button("儲存設定"):
                save_settings(client, GOOGLE_SHEET_NAME, mode, start_time, end_time)
            if st.button("登出"):
                st.session_state.authenticated = False
                st.rerun()

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).time()
    if not (settings['start_time'] <= now <= settings['end_time']):
        st.warning("報到尚未開始或已結束。")
        return

    with st.spinner("正在載入員工名單..."):
        df = get_data(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME)
    if df.empty:
        return

    if st.session_state.feedback:
        message_type, message_text = st.session_state.feedback.values()
        if message_type == "success": st.success(message_text)
        elif message_type == "warning": st.warning(message_text)
        elif message_type == "error": st.error(message_text)
        st.session_state.feedback = None

    if st.session_state.sound_to_play:
        st.audio(st.session_state.sound_to_play, autoplay=True)
        st.session_state.sound_to_play = None

    # --- Search and Confirmation Flow ---
    if not st.session_state.get('selected_employee_id'):
        st.session_state.search_term = st.text_input("請輸入您的員工編號或姓名:", value=st.session_state.search_term).strip()
        if st.button("確認"):
            if not st.session_state.search_term:
                st.session_state.feedback = {"type": "error", "text": "請輸入您的員工編號或姓名"}
            else:
                search_term_lower = st.session_state.search_term.lower()
                id_match = df[df['EmployeeID'].str.lower() == search_term_lower]
                name_match = df[df['Name'].str.lower() == search_term_lower]
                if not id_match.empty:
                    st.session_state.selected_employee_id = id_match['EmployeeID'].iloc[0]
                elif not name_match.empty:
                    if len(name_match) == 1:
                        st.session_state.selected_employee_id = name_match['EmployeeID'].iloc[0]
                    else:
                        st.session_state.feedback = {"type": "warning", "text": "找到多位同名員工，請改用員工編號搜尋。"}
                else:
                    st.session_state.feedback = {"type": "error", "text": "查無此人，請確認輸入是否正確。"}
                    st.session_state.sound_to_play = ERROR_SOUND_URL
            st.rerun()
    else:
        employee_id = st.session_state.selected_employee_id
        employee_row = df[df['EmployeeID'] == employee_id]
        if not employee_row.empty:
            row_index = employee_row.index[0] + 2
            if settings['mode'] == "Check-in":
                handle_check_in(df, employee_row, row_index, client)
            else:
                handle_check_out(employee_row, row_index, client)


def handle_check_in(df, employee_row, row_index, client):
    """Handles the check-in process using the stable fingerprint method."""
    name = employee_row['Name'].iloc[0]
    employee_id = employee_row['EmployeeID'].iloc[0]
    st.subheader(f"確認報到資訊: {name} ({employee_id})")

    check_in_time = employee_row['CheckInTime'].iloc[0]
    if pd.notna(check_in_time) and str(check_in_time).strip() != '':
        st.session_state.feedback = {"type": "warning", "text": "您已報到，無須重複操作。"}
        st.session_state.sound_to_play = ERROR_SOUND_URL
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()
        return

    # 唯一的真相來源：直接從隱藏元件的 session_state 讀取識別碼
    fingerprint = st.session_state.get('device_fingerprint_hidden')

    # 檢查是否已成功獲取
    if not fingerprint or fingerprint == "__fingerprint_placeholder__":
        st.warning("🔄 正在識別您的裝置，請稍候...")
        st.caption("如果長時間停留在此畫面，請嘗試重新整理頁面。")
        return
    
    st.text_input("裝置識別碼 (Device ID)", value=fingerprint, disabled=True)

    if st.button("✅ 確認報到"):
        # 在按下按鈕的瞬間，再次從唯一的真相來源確認最新的識別碼
        final_fingerprint = st.session_state.get('device_fingerprint_hidden')
        if not final_fingerprint or final_fingerprint == "__fingerprint_placeholder__":
            st.session_state.feedback = {"type": "error", "text": "無法確認報到，識別碼遺失，請刷新頁面再試一次。"}
            st.session_state.sound_to_play = ERROR_SOUND_URL
        elif 'DeviceFingerprint' in df.columns and not df[df['DeviceFingerprint'] == final_fingerprint].empty:
            st.session_state.feedback = {"type": "error", "text": "此裝置已用於報到，請勿代他人操作。"}
            st.session_state.sound_to_play = ERROR_SOUND_URL
        else:
            table_no = employee_row['TableNo'].iloc[0]
            tz = pytz.timezone(TIMEZONE)
            timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, 4, timestamp)
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, 6, final_fingerprint)
            st.session_state.feedback = {"type": "success", "text": f"報到成功！歡迎 {name}，您的桌號是 {table_no}"}
            st.session_state.sound_to_play = SUCCESS_SOUND_URL

        # 重設狀態以供下一位使用者
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()


def handle_check_out(employee_row, row_index, client):
    """Handles the check-out process."""
    name = employee_row['Name'].iloc[0]
    st.subheader(f"確認簽退: {name}")

    check_out_time = employee_row['CheckOutTime'].iloc[0]
    if pd.notna(check_out_time) and str(check_out_time).strip() != '':
        st.session_state.feedback = {"type": "warning", "text": "您已完成簽退。"}
        st.session_state.sound_to_play = ERROR_SOUND_URL
    else:
        if st.button("✅ 確認簽退"):
            tz = pytz.timezone(TIMEZONE)
            timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, 5, timestamp)
            st.session_state.feedback = {"type": "success", "text": f"簽退成功，{name}，祝您有個美好的一天！"}
            st.session_state.sound_to_play = SUCCESS_SOUND_URL
            st.session_state.selected_employee_id = None
            st.session_state.search_term = ""
            st.rerun()

    if st.button("返回"):
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()

if __name__ == "__main__":
    main()
