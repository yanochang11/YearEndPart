# app_v1.6.0.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe
from datetime import datetime, time
import pytz
import streamlit.components.v1 as components

# --- App Version ---
VERSION = "1.6.0"

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

# --- Custom CSS (UI/UX Improvement) ---
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    body {
        background-color: #f0f2f6;
    }
    h1 {
        color: #1a1a1a;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# --- Fingerprint Component ---
def get_fingerprint_component():
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (async () => {
        while (!window.Streamlit) {
          await new Promise(resolve => setTimeout(resolve, 50));
        }
        try {
            const fp = await FingerprintJS.load();
            const result = await fp.get();
            window.Streamlit.setComponentValue(result.visitorId);
        } catch (error) {
            console.error("FingerprintJS error:", error);
            window.Streamlit.setComponentValue({ "error": error.message });
        }
      })();
    </script>
    """
    return components.html(js_code, height=0)

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

    # --- App State Initialization ---
    for key in ['authenticated', 'search_term', 'selected_employee_id', 'feedback', 'sound_to_play', 'device_fingerprint']:
        if key not in st.session_state:
            st.session_state[key] = None if key != 'search_term' else ""

    # --- (核心修改 v1.6.0) 獲取並立即顯示裝置識別碼 ---
    if not st.session_state.device_fingerprint:
        fingerprint_value = get_fingerprint_component()
        if fingerprint_value:
            st.session_state.device_fingerprint = fingerprint_value
            st.rerun() # 獲取到值後，重跑一次以更新下方的顯示元件

    # 這個 placeholder 會始終存在於主畫面上
    fingerprint_placeholder = st.empty()
    fingerprint = st.session_state.get('device_fingerprint')

    if not fingerprint:
        fingerprint_placeholder.warning("🔄 正在識別您的裝置，請稍候...")
    else:
        # 一旦獲取成功，就用一個 disabled 的 text_input 把值固定住
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

    # --- Admin Panel ---
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

    # --- Feedback and Sound ---
    if st.session_state.feedback:
        msg_type, msg_text = st.session_state.feedback.values()
        if msg_type == "success": st.success(msg_text)
        elif msg_type == "warning": st.warning(msg_text)
        elif msg_type == "error": st.error(msg_text)
        st.session_state.feedback = None

    if st.session_state.sound_to_play:
        st.audio(st.session_state.sound_to_play, autoplay=True)
        st.session_state.sound_to_play = None

    # --- Main Logic Flow ---
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

    # 這裡不再需要顯示識別碼的邏輯，因為它已經顯示在主畫面上了
    # 只需要在按下按鈕時，從 session_state 讀取即可

    if st.button("✅ 確認報到"):
        # 從 session_state 直接讀取已固定的識別碼
        final_fingerprint = st.session_state.get('device_fingerprint')
        if not final_fingerprint:
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
