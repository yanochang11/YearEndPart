# app_v2.5.0.py (Optimized Fingerprinting)
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe
from datetime import datetime, time
import pytz
import streamlit.components.v1 as components

# --- App Version ---
VERSION = "2.5.0 (Auto Fingerprinting)"

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
        st.error(f"無法讀取資料表 / Could not read worksheet '{sheet_name}/{worksheet_name}'. Error: {e}")
        return pd.DataFrame()

def update_cell(client, sheet_name, worksheet_name, row, col, value):
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        get_data.clear()
    except Exception as e:
        st.error(f"更新 Google Sheet 失敗 / Failed to update Google Sheet: {e}")

@st.cache_data(ttl=60)
def get_settings(_client, sheet_name):
    try:
        settings_sheet = _client.open(sheet_name).worksheet("Settings")
        mode = settings_sheet.acell('A2').value
        start_time_str = settings_sheet.acell('B2').value
        end_time_str = settings_sheet.acell('C2').value
        start_time = datetime.strptime(start_time_str, '%H:%M').time() if start_time_str else time(9, 0)
        end_time = datetime.strptime(end_time_str, '%H:%M').time() if end_time_str else time(17, 0)
        return {"mode": mode, "start_time": start_time, "end_time": end_time}
    except Exception as e:
        return {"mode": "Check-in", "start_time": time(9, 0), "end_time": time(17, 0)}

def save_settings(client, sheet_name, mode, start_time, end_time):
    try:
        settings_sheet = client.open(sheet_name).worksheet("Settings")
        settings_sheet.update('A2:C2', [[mode, start_time.strftime('%H:%M'), end_time.strftime('%H:%M')]])
        get_settings.clear()
        st.success("設定已儲存! / Settings saved!")
    except Exception as e:
        st.error(f"儲存設定失敗 / Failed to save settings: {e}")
        
def get_fingerprint_component():
    """Renders the JS component to get the device fingerprint and return it to Streamlit."""
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (async () => {
        // Flag to ensure this runs only once
        if (window.fingerprintJsExecuted) {
            return;
        }
        window.fingerprintJsExecuted = true;
        try {
            // Wait for Streamlit to be ready
            while (!window.Streamlit) {
              await new Promise(resolve => setTimeout(resolve, 50));
            }
            const fp = await FingerprintJS.load();
            const result = await fp.get();
            // Send the visitorId back to the Python backend
            window.Streamlit.setComponentValue(result.visitorId);
        } catch (error) {
            console.error("FingerprintJS error:", error);
            window.Streamlit.setComponentValue({ "error": error.message });
        }
      })();
    </script>
    """
    return components.html(js_code, height=0)

def main():
    st.title("活動報到系統 / Event Check-in System")
    st.markdown(f"<p style='text-align: right; color: grey;'>v{VERSION}</p>", unsafe_allow_html=True)

    # Initialize state variables
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ''
    if 'feedback' not in st.session_state:
        st.session_state.feedback = None
    if 'fingerprint_id' not in st.session_state:
        st.session_state.fingerprint_id = None
        
    # --- 1. Fingerprint Acquisition ---
    # This component will run on the first load and send the result back.
    if st.session_state.fingerprint_id is None:
        component_return_value = get_fingerprint_component()
        if component_return_value:
            st.session_state.fingerprint_id = component_return_value
            st.rerun() # Rerun to update the UI now that we have the ID

    is_ready = st.session_state.fingerprint_id is not None and isinstance(st.session_state.fingerprint_id, str)
    
    # --- 2. Main Application Flow ---
    client = get_gsheet()
    settings = get_settings(client, GOOGLE_SHEET_NAME)
    
    # Display current mode and a status message for fingerprinting
    st.info(f"**目前模式 / Current Mode:** `{settings['mode']}`")
    if not is_ready:
        st.warning("🔄 正在獲取裝置識別碼，請稍候... / Acquiring device ID, please wait...")
    
    # Admin Panel
    with st.sidebar.expander("管理員面板 / Admin Panel", expanded=False):
        if not st.session_state.authenticated:
            password = st.text_input("請輸入密碼 / Password:", type="password", key="admin_password")
            if st.button("登入 / Login"):
                if password == st.secrets.admin.password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("密碼錯誤 / Incorrect Password")
        else:
            st.success("已認證 / Authenticated")
            mode = st.radio("模式 / Mode", ["Check-in", "Check-out"], index=["Check-in", "Check-out"].index(settings['mode']))
            start_time = st.time_input("開始時間 / Start Time", settings['start_time'])
            end_time = st.time_input("結束時間 / End Time", settings['end_time'])
            if st.button("儲存設定 / Save Settings"):
                save_settings(client, GOOGLE_SHEET_NAME, mode, start_time, end_time)
            if st.button("登出 / Logout"):
                st.session_state.authenticated = False
                st.rerun()
    
    # Feedback display
    if st.session_state.feedback:
        msg_type, msg_text = st.session_state.feedback.values()
        if msg_type == "success": st.success(msg_text)
        elif msg_type == "warning": st.warning(msg_text)
        elif msg_type == "error": st.error(msg_text)
        st.session_state.feedback = None

    # --- 3. User Interaction UI ---
    st.session_state.search_term = st.text_input(
        "請輸入您的員工編號或姓名 / Please enter your Employee ID or Name:",
        value=st.session_state.search_term,
        key="search_input",
        disabled=not is_ready # Disable until fingerprint is ready
    ).strip()

    if st.button("確認 / Confirm", disabled=not is_ready): # Disable until fingerprint is ready
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz).time()
        fingerprint = st.session_state.fingerprint_id

        if not (settings['start_time'] <= now <= settings['end_time']):
            st.session_state.feedback = {"type": "warning", "text": "報到尚未開始或已結束 / Check-in is not yet open or has already closed."}
        elif not st.session_state.search_term:
            st.session_state.feedback = {"type": "error", "text": "請輸入您的員工編號或姓名 / Please enter your Employee ID or Name"}
        else:
            with st.spinner("正在處理 / Processing..."):
                df = get_data(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME)
                if not df.empty:
                    process_request(df, settings, client, fingerprint)
        
        st.session_state.search_term = "" # Clear input after processing
        st.rerun()

def process_request(df, settings, client, final_fingerprint):
    search_term = st.session_state.search_term.lower()
    # Ensure columns exist before searching
    id_match = df[df['EmployeeID'].str.lower() == search_term] if 'EmployeeID' in df.columns else pd.DataFrame()
    name_match = df[df['Name'].str.lower() == search_term] if 'Name' in df.columns else pd.DataFrame()
    employee_row = pd.DataFrame()

    if not id_match.empty:
        employee_row = id_match.iloc[[0]]
    elif not name_match.empty:
        if len(name_match) == 1:
            employee_row = name_match.iloc[[0]]
        else:
            st.session_state.feedback = {"type": "warning", "text": "找到多位同名員工，請改用員工編號搜尋 / Multiple employees found with the same name, please use Employee ID."}
            return
    else:
        st.session_state.feedback = {"type": "error", "text": "查無此人，請確認輸入是否正確 / User not found, please check your input."}
        return

    row_index = employee_row.index[0] + 2
    name = employee_row['Name'].iloc[0]
    timestamp = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")

    if settings['mode'] == "Check-in":
        if pd.notna(employee_row['CheckInTime'].iloc[0]) and str(employee_row['CheckInTime'].iloc[0]).strip() != '':
            st.session_state.feedback = {"type": "warning", "text": f"{name}, 您已報到，無須重複操作 / you have already checked in."}
        elif 'DeviceFingerprint' in df.columns and not df[df['DeviceFingerprint'] == final_fingerprint].empty:
            st.session_state.feedback = {"type": "error", "text": "此裝置已用於報到，請勿代他人操作 / This device has already been used to check in."}
        else:
            table_no = employee_row['TableNo'].iloc[0]
            # Ensure target columns exist
            if 'CheckInTime' in df.columns:
                update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, df.columns.get_loc('CheckInTime') + 1, timestamp)
            if 'DeviceFingerprint' in df.columns:
                 update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, df.columns.get_loc('DeviceFingerprint') + 1, final_fingerprint)
            st.session_state.feedback = {"type": "success", "text": f"報到成功！歡迎 {name}，您的桌號是 {table_no} / Check-in successful! Welcome {name}, your table number is {table_no}."}
    else: # Check-out Mode
        if pd.notna(employee_row['CheckOutTime'].iloc[0]) and str(employee_row['CheckOutTime'].iloc[0]).strip() != '':
            st.session_state.feedback = {"type": "warning", "text": f"{name}, 您已完成簽退 / you have already checked out."}
        else:
            if 'CheckOutTime' in df.columns:
                update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, df.columns.get_loc('CheckOutTime') + 1, timestamp)
            st.session_state.feedback = {"type": "success", "text": f"簽退成功，{name}，祝您有個美好的一天！ / Check-out successful, {name}, have a nice day!"}

if __name__ == "__main__":
    main()

