# app_v1.7.0.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe
from datetime import datetime, time
import pytz
import streamlit.components.v1 as components

# --- App Version ---
VERSION = "1.7.0 (Stable Fingerprint Release)"

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

# --- Custom CSS ---
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    body { background-color: #f0f2f6; }
    h1 { color: #1a1a1a; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- Google Sheets Connection & Data Functions ---
@st.cache_resource(ttl=600)
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets.gcp_service_account, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def get_data(_client, sheet_name, worksheet_name):
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
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        get_data.clear()
    except Exception as e:
        st.error(f"更新 Google Sheet 失敗: {e}")

@st.cache_data(ttl=60)
def get_settings(_client, sheet_name):
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
    try:
        settings_sheet = client.open(sheet_name).worksheet("Settings")
        settings_sheet.update('A2:C2', [[mode, start_time.strftime('%H:%M'), end_time.strftime('%H:%M')]])
        get_settings.clear()
        st.success("設定已儲存!")
    except Exception as e:
        st.error(f"儲存設定失敗: {e}")


def main():
    st.title("活動報到系統")
    st.markdown(f"<p style='text-align: right; color: grey;'>v{VERSION}</p>", unsafe_allow_html=True)

    # --- (核心修改 v1.7.0) 完全採用您提供的 JavaScript 邏輯 ---
    js_code = '''
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      function setFingerprint() {
        const fpPromise = FingerprintJS.load();
        fpPromise
          .then(fp => fp.get())
          .then(result => {
            const visitorId = result.visitorId;
            console.log("Device Fingerprint:", visitorId); // Log for debugging
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
                        console.log('Fingerprint set successfully into hidden field.');
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
      // 確保在頁面載入時執行
      if (document.readyState === 'complete') {
        setFingerprint();
      } else {
        window.addEventListener('load', setFingerprint);
      }
    </script>
    '''
    components.html(js_code, height=0)

    # --- 溝通橋樑：與您的 JS 完全對應的隱藏輸入框 ---
    st.text_input("Device Fingerprint Hidden", key="device_fingerprint_hidden", label_visibility="hidden",
                  placeholder="__fingerprint_placeholder__")

    # --- App State Initialization ---
    for key in ['authenticated', 'search_term', 'selected_employee_id', 'feedback', 'sound_to_play']:
        if key not in st.session_state:
            st.session_state[key] = None if key != 'search_term' else ""

    # --- 立即顯示且固定的裝置識別碼欄位 ---
    fingerprint_placeholder = st.empty()
    # 我們唯一的真相來源就是 'device_fingerprint_hidden'
    fingerprint = st.session_state.get('device_fingerprint_hidden')

    if not fingerprint or fingerprint == "__fingerprint_placeholder__":
        fingerprint_placeholder.warning("🔄 正在識別您的裝置，請稍候...")
    else:
        fingerprint_placeholder.text_input(
            "裝置識別碼 (Device ID)",
            value=fingerprint,
            disabled=True,
            key="static_fingerprint_display"
        )

    # --- 主應用程式流程 ---
    client = get_gsheet()
    settings = get_settings(client, GOOGLE_SHEET_NAME)
    st.info(f"**目前模式:** `{settings['mode']}`")

    # ... (Admin Panel and other logic remains the same)
    with st.sidebar.expander("管理員面板", expanded=False):
        if not st.session_state.authenticated:
            password = st.text_input("請輸入密碼:", type="password", key="admin_password")
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
        msg_type, msg_text = st.session_state.feedback.values()
        if msg_type == "success": st.success(msg_text)
        elif msg_type == "warning": st.warning(msg_text)
        elif msg_type == "error": st.error(msg_text)
        st.session_state.feedback = None

    if st.session_state.sound_to_play:
        st.audio(st.session_state.sound_to_play, autoplay=True)
        st.session_state.sound_to_play = None

    if not st.session_state.get('selected_employee_id'):
        st.session_state.search_term = st.text_input("請輸入您的員工編號或姓名:", value=st.session_state.search_term, key="search_input").strip()
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

    if st.button("✅ 確認報到"):
        # 按下按鈕時，再次從唯一的真相來源讀取，確保拿到的是最新的值
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

        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()

def handle_check_out(employee_row, row_index, client):
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
