# app_v2.8.0.py (Modern Auth & Crash Fix)
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials # Using modern google-auth library
import pandas as pd
from gspread_dataframe import get_as_dataframe
from datetime import datetime, time
import pytz
import streamlit.components.v1 as components

# --- App Version ---
VERSION = "2.8.0 (Modern Auth)"

# --- Configuration ---
TIMEZONE = "Asia/Taipei"
GOOGLE_SHEET_NAME = "Event_Check-in"
WORKSHEET_NAME = "Sheet1"

# --- Page Configuration ---
st.set_page_config(
    page_title=f"活動報到系統 / Event Check-in System v{VERSION}",
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
    div[data-testid="stTextInput"] > div > div > input[disabled],
    div[data-testid="stButton"] > button[disabled] {
        background-color: #e9ecef;
        cursor: not-allowed;
    }
    input[aria-label="您的裝置識別碼 / Your Device ID"] {
        background-color: #f0f2f6 !important;
        color: #555 !important;
        border: 1px solid #ced4da !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Google Sheets Connection & Data Functions ---
@st.cache_resource(ttl=600)
def get_gsheet():
    """Establishes a connection to Google Sheets using the modern google-auth library."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets.get("gcp_service_account")
        if not creds_dict:
            st.error("GCP Service Account secrets not found. Please configure `[gcp_service_account]` in your Streamlit Secrets.")
            return None
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Google Sheets 連線失敗 / Google Sheets connection failed: {e}")
        st.info("請確認您的 Streamlit Secrets (`[gcp_service_account]`) 是否已正確設定，且服務帳號已被授權編輯您的 Google Sheet。")
        return None

@st.cache_data(ttl=30)
def get_data(_client, sheet_name, worksheet_name):
    if _client is None: return pd.DataFrame()
    try:
        sheet = _client.open(sheet_name).worksheet(worksheet_name)
        data = get_as_dataframe(sheet, evaluate_formulas=True)
        for col in ['EmployeeID', 'DeviceFingerprint']:
            if col in data.columns: data[col] = data[col].astype(str).str.strip()
        return data.dropna(how='all')
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"找不到工作表 '{worksheet_name}' / Worksheet '{worksheet_name}' not found.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"無法讀取資料表 / Could not read worksheet. Error: {e}")
        return pd.DataFrame()

def update_cell(client, sheet_name, worksheet_name, row, col, value):
    if client is None: return
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        get_data.clear()
    except Exception as e:
        st.error(f"更新 Google Sheet 失敗 / Failed to update Google Sheet: {e}")

@st.cache_data(ttl=60)
def get_settings(_client, sheet_name):
    if _client is None: return {"mode": "Check-in", "start_time": time(9, 0), "end_time": time(17, 0)}
    try:
        settings_sheet = _client.open(sheet_name).worksheet("Settings")
        mode = settings_sheet.acell('A2').value
        start_time = datetime.strptime(settings_sheet.acell('B2').value, '%H:%M').time()
        end_time = datetime.strptime(settings_sheet.acell('C2').value, '%H:%M').time()
        return {"mode": mode, "start_time": start_time, "end_time": end_time}
    except Exception:
        return {"mode": "Check-in", "start_time": time(9, 0), "end_time": time(17, 0)}

def save_settings(client, sheet_name, mode, start_time, end_time):
    if client is None: return
    try:
        settings_sheet = client.open(sheet_name).worksheet("Settings")
        settings_sheet.update('A2:C2', [[mode, start_time.strftime('%H:%M'), end_time.strftime('%H:%M')]])
        get_settings.clear()
        st.success("設定已儲存! / Settings saved!")
    except Exception as e:
        st.error(f"儲存設定失敗 / Failed to save settings: {e}")

def render_fingerprint_button_component():
    js_code = """
    <div style="display: flex; justify-content: center; margin: 1rem 0;">
        <button id="fp_button" style="padding: 10px 24px; font-size: 16px; cursor: pointer;">
            獲取裝置識別碼 / Get Device ID
        </button>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      const button = document.getElementById('fp_button');
      if (button) {
        button.onclick = function() {
          this.disabled = true; this.textContent = '讀取中... / Loading...';
          FingerprintJS.load().then(fp => fp.get()).then(result => {
              window.Streamlit.setComponentValue(result.visitorId);
            }).catch(err => {
                console.error('FingerprintJS error:', err);
                this.textContent = '獲取失敗，請重試 / Error, please retry';
                window.Streamlit.setComponentValue({ "error": err.message });
            });
        };
      }
    </script>
    """
    return components.html(js_code, height=60)

def main():
    st.title("活動報到系統 / Event Check-in System")
    st.markdown(f"<p style='text-align: right; color: grey;'>v{VERSION}</p>", unsafe_allow_html=True)

    client = get_gsheet()
    if client is None:
        st.stop()

    for key, default in [('authenticated', False), ('search_term', ''), ('feedback', None), ('fingerprint_id', None)]:
        if key not in st.session_state: st.session_state[key] = default

    is_ready = st.session_state.fingerprint_id is not None and isinstance(st.session_state.fingerprint_id, str)
    
    settings = get_settings(client, GOOGLE_SHEET_NAME)
    st.info(f"**目前模式 / Current Mode:** `{settings['mode']}`")

    if not is_ready:
        st.info("第一步：請點擊下方按鈕以載入您的裝置識別碼。\nStep 1: Please click the button below to load your device ID.")
        component_return_value = render_fingerprint_button_component()
        if component_return_value:
            if isinstance(component_return_value, str):
                st.session_state.fingerprint_id = component_return_value
            else:
                st.error("無法獲取裝置識別碼，請刷新頁面再試一次。")
            st.rerun()
    
    st.text_input("您的裝置識別碼 / Your Device ID", value=st.session_state.fingerprint_id if is_ready else "尚未獲取", disabled=True)
    
    with st.sidebar.expander("管理員面板 / Admin Panel", expanded=False):
        if not st.session_state.authenticated:
            password = st.text_input("密碼:", type="password", key="admin_pw")
            if st.button("登入"):
                if password == st.secrets.admin.password: st.session_state.authenticated = True; st.rerun()
                else: st.error("密碼錯誤")
        else:
            st.success("已認證")
            mode = st.radio("模式", ["Check-in", "Check-out"], index=["Check-in", "Check-out"].index(settings['mode']))
            start_time = st.time_input("開始時間", settings['start_time'])
            end_time = st.time_input("結束時間", settings['end_time'])
            if st.button("儲存設定"): save_settings(client, GOOGLE_SHEET_NAME, mode, start_time, end_time)
            if st.button("登出"): st.session_state.authenticated = False; st.rerun()

    if st.session_state.feedback:
        msg_type, msg_text = st.session_state.feedback.values()
        if msg_type == "success": st.success(msg_text)
        elif msg_type == "warning": st.warning(msg_text)
        elif msg_type == "error": st.error(msg_text)
        st.session_state.feedback = None

    st.markdown("---")

    st.session_state.search_term = st.text_input("請輸入員工編號或姓名:", value=st.session_state.search_term, key="search_input", disabled=not is_ready).strip()

    if st.button("確認 / Confirm", disabled=not is_ready):
        now = datetime.now(pytz.timezone(TIMEZONE)).time()
        if not (settings['start_time'] <= now <= settings['end_time']):
            st.session_state.feedback = {"type": "warning", "text": "報到尚未開始或已結束"}
        elif not st.session_state.search_term:
            st.session_state.feedback = {"type": "error", "text": "請輸入員工編號或姓名"}
        else:
            with st.spinner("正在處理..."):
                df = get_data(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME)
                if not df.empty:
                    process_request(df, settings, client, st.session_state.fingerprint_id)
        st.session_state.search_term = ""
        st.rerun()

def process_request(df, settings, client, final_fingerprint):
    search_term = st.session_state.search_term.lower()
    id_match = df[df['EmployeeID'].str.lower() == search_term]
    name_match = df[df['Name'].str.lower() == search_term]
    employee_row = pd.DataFrame()

    if not id_match.empty: employee_row = id_match.iloc[[0]]
    elif not name_match.empty:
        if len(name_match) == 1: employee_row = name_match.iloc[[0]]
        else: st.session_state.feedback = {"type": "warning", "text": "找到多位同名員工，請改用員工編號"}; return
    else: st.session_state.feedback = {"type": "error", "text": "查無此人，請確認輸入是否正確"}; return

    row_index = employee_row.index[0] + 2
    name = employee_row['Name'].iloc[0]
    timestamp = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")

    if settings['mode'] == "Check-in":
        if pd.notna(employee_row['CheckInTime'].iloc[0]) and str(employee_row['CheckInTime'].iloc[0]).strip():
            st.session_state.feedback = {"type": "warning", "text": f"{name}, 您已報到，無須重複操作"}
        elif 'DeviceFingerprint' in df.columns and not df[df['DeviceFingerprint'] == final_fingerprint].empty:
            st.session_state.feedback = {"type": "error", "text": "此裝置已用於報到，請勿代他人操作"}
        else:
            table_no = employee_row['TableNo'].iloc[0]
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, df.columns.get_loc('CheckInTime') + 1, timestamp)
            if 'DeviceFingerprint' in df.columns:
                 update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, df.columns.get_loc('DeviceFingerprint') + 1, final_fingerprint)
            st.session_state.feedback = {"type": "success", "text": f"報到成功！歡迎 {name}，您的桌號是 {table_no}"}
    else: # Check-out Mode
        if pd.notna(employee_row['CheckOutTime'].iloc[0]) and str(employee_row['CheckOutTime'].iloc[0]).strip():
            st.session_state.feedback = {"type": "warning", "text": f"{name}, 您已完成簽退"}
        else:
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, df.columns.get_loc('CheckOutTime') + 1, timestamp)
            st.session_state.feedback = {"type": "success", "text": f"簽退成功，{name}，祝您有個美好的一天！"}

if __name__ == "__main__":
    main()
