# app_v1.0.0.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe
from datetime import datetime, time
import pytz
import streamlit.components.v1 as components

# --- App Version ---
VERSION = "1.0.0"

# --- Configuration ---
TIMEZONE = "Asia/Taipei"
GOOGLE_SHEET_NAME = "Event_Check-in"
WORKSHEET_NAME = "Sheet1"
SUCCESS_SOUND_URL = "https://cdn.jsdelivr.net/gh/yanochang11/yearendpart@main/event-check-in/assets/success.mp3"
ERROR_SOUND_URL = "https://cdn.jsdelivr.net/gh/yanochang11/yearendpart@main/event-check-in/assets/error.mp3"

# --- Page Configuration ---
st.set_page_config(
    page_title="活動報到系統 v1.0.0",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for better UI ---
st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        border: 1px solid #0068c9;
        background-color: #0068c9;
        color: white;
        padding: 0.5em 1em;
    }
    .stButton>button:hover {
        background-color: #005aa3;
        color: white;
        border: 1px solid #005aa3;
    }
    .stTextInput>div>div>input {
        background-color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)


# --- Google Sheets Connection ---
@st.cache_resource(ttl=600)
def get_gsheet_client():
    """Establishes a connection to Google Sheets using cached credentials."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
        "type": st.secrets.gcp_service_account.type,
        "project_id": st.secrets.gcp_service_account.project_id,
        "private_key_id": st.secrets.gcp_service_account.private_key_id,
        "private_key": st.secrets.gcp_service_account.private_key,
        "client_email": st.secrets.gcp_service_account.client_email,
        "client_id": st.secrets.gcp_service_account.client_id,
        "auth_uri": st.secrets.gcp_service_account.auth_uri,
        "token_uri": st.secrets.gcp_service_account.token_uri,
        "auth_provider_x509_cert_url": st.secrets.gcp_service_account.auth_provider_x509_cert_url,
        "client_x509_cert_url": st.secrets.gcp_service_account.client_x509_cert_url,
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=60)
def get_data(_client, sheet_name, worksheet_name):
    """Fetches data from the worksheet and caches it."""
    try:
        sheet = _client.open(sheet_name).worksheet(worksheet_name)
        data = get_as_dataframe(sheet, evaluate_formulas=True)
        # Ensure critical columns are treated as strings to avoid data type issues
        for col in ['EmployeeID', 'DeviceFingerprint']:
            if col in data.columns:
                data[col] = data[col].astype(str)
        return data.dropna(how='all')
    except Exception as e:
        st.error(f"無法讀取資料表 '{sheet_name}/{worksheet_name}'。請檢查設定。錯誤: {e}")
        return pd.DataFrame()

def update_cell(client, sheet_name, worksheet_name, row, col, value):
    """Updates a single cell and clears relevant caches."""
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        get_data.clear() # Invalidate cache after update
    except Exception as e:
        st.error(f"更新 Google Sheet 失敗: {e}")

# --- Settings Management ---
@st.cache_data(ttl=60)
def get_settings(_client, sheet_name):
    """Fetches settings from the 'Settings' worksheet."""
    try:
        settings_sheet = _client.open(sheet_name).worksheet("Settings")
        mode = settings_sheet.acell('A2').value
        start_time_str = settings_sheet.acell('B2').value
        end_time_str = settings_sheet.acell('C2').value
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
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

# --- Fingerprint Component ---
def get_fingerprint_component():
    """Renders the JavaScript component to get and return the device fingerprint."""
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (async () => {
        // Flag to prevent duplicate execution
        if (window.fingerprintJsExecuted) {
            return;
        }
        window.fingerprintJsExecuted = true;

        try {
            // Wait for Streamlit object to be ready
            while (!window.Streamlit) {
              await new Promise(resolve => setTimeout(resolve, 50));
            }

            const fp = await FingerprintJS.load();
            const result = await fp.get();

            // Return the value to the Python backend
            window.Streamlit.setComponentValue(result.visitorId);

        } catch (error) {
            console.error("FingerprintJS error:", error);
            window.Streamlit.setComponentValue({ "error": error.message });
        }
      })();
    </script>
    """
    return components.html(js_code, height=0)

# --- Core Application Logic ---
def main():
    """Main function to run the Streamlit application."""
    st.title("活動報到系統")
    st.markdown(f"<p style='text-align: right; color: grey;'>v{VERSION}</p>", unsafe_allow_html=True)


    # Initialize session state
    if 'fingerprint_id' not in st.session_state:
        st.session_state.fingerprint_id = None
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ""
    if 'selected_employee_id' not in st.session_state:
        st.session_state.selected_employee_id = None
    if 'feedback' not in st.session_state:
        st.session_state.feedback = None
    if 'sound_to_play' not in st.session_state:
        st.session_state.sound_to_play = None

    # --- Get Fingerprint ---
    # Only call the component if we don't have the fingerprint yet
    if st.session_state.fingerprint_id is None:
        component_return_value = get_fingerprint_component()
        if component_return_value:
            st.session_state.fingerprint_id = component_return_value
            st.rerun() # Rerun to update the UI with the new state

    # Connect to Google Sheets
    client = get_gsheet_client()
    settings = get_settings(client, GOOGLE_SHEET_NAME)
    st.info(f"**目前模式:** `{settings['mode']}`")

    # --- Admin Panel ---
    with st.sidebar.expander("管理員面板", expanded=False):
        if not st.session_state.authenticated:
            password = st.text_input("請輸入密碼:", type="password", key="password_input")
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

    # --- Time Check ---
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).time()
    if not (settings['start_time'] <= now <= settings['end_time']):
        st.warning("報到尚未開始或已結束。")
        return

    # Load data
    with st.spinner("正在載入員工名單..."):
        df = get_data(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME)

    if df.empty:
        return

    # --- Display Feedback and Play Sound ---
    if st.session_state.feedback:
        message_type, message_text = st.session_state.feedback.values()
        if message_type == "success":
            st.success(message_text)
        elif message_type == "warning":
            st.warning(message_text)
        elif message_type == "error":
            st.error(message_text)
        st.session_state.feedback = None

    if st.session_state.sound_to_play:
        st.audio(st.session_state.sound_to_play, autoplay=True)
        st.session_state.sound_to_play = None


    # --- Search and Confirmation Flow ---
    if not st.session_state.get('selected_employee_id'):
        st.session_state.search_term = st.text_input("請輸入您的員工編號或姓名:", value=st.session_state.search_term, key="search_input").strip()
        if st.button("確認"):
            if not st.session_state.search_term:
                st.session_state.feedback = {"type": "error", "text": "請輸入您的員工編號或姓名"}
            else:
                # Search logic
                search_term_lower = st.session_state.search_term.lower()
                id_match = df[df['EmployeeID'].str.lower() == search_term_lower]
                name_match = df[df['Name'].str.lower() == search_term_lower]

                if not id_match.empty:
                    st.session_state.selected_employee_id = id_match['EmployeeID'].iloc[0]
                elif not name_match.empty:
                    if len(name_match) == 1:
                        st.session_state.selected_employee_id = name_match['EmployeeID'].iloc[0]
                    else:
                        st.session_state.feedback = {"type": "warning", "text": "找到多位同名員工，請選擇一位:"}
                        # This part needs a different UI flow, for now, we handle it as a message.
                else:
                    st.session_state.feedback = {"type": "error", "text": "查無此人，請確認輸入是否正確。"}
                    st.session_state.sound_to_play = ERROR_SOUND_URL
            st.rerun()
    else: # An employee has been selected
        employee_id = st.session_state.selected_employee_id
        employee_row = df[df['EmployeeID'] == employee_id]

        if not employee_row.empty:
            row_index = employee_row.index[0] + 2 # +2 for header and 0-based index
            if settings['mode'] == "Check-in":
                handle_check_in(df, employee_row, row_index, client)
            else:
                handle_check_out(employee_row, row_index, client)

def handle_check_in(df, employee_row, row_index, client):
    """Handles the check-in process for a selected employee."""
    name = employee_row['Name'].iloc[0]
    employee_id = employee_row['EmployeeID'].iloc[0]
    st.subheader(f"確認報到資訊: {name} ({employee_id})")

    # --- Fingerprint Check ---
    fingerprint = st.session_state.get('fingerprint_id')
    if not fingerprint:
        st.warning("🔄 正在識別您的裝置，請稍候...")
        st.text("如果長時間停留在此畫面，請重新整理頁面。")
        return
    elif isinstance(fingerprint, dict) and 'error' in fingerprint:
        st.error(f"無法獲取裝置識別碼: {fingerprint['error']}")
        return

    st.text_input("裝置識別碼 (Device ID)", value=fingerprint, disabled=True)

    # Check if already checked in
    check_in_time = employee_row['CheckInTime'].iloc[0]
    if pd.notna(check_in_time) and str(check_in_time).strip() != '':
        st.session_state.feedback = {"type": "warning", "text": "您已報到，無須重複操作。"}
        st.session_state.sound_to_play = ERROR_SOUND_URL
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()
        return

    if st.button("✅ 確認報到"):
        # Final check for fingerprint before processing
        final_fingerprint = st.session_state.get('fingerprint_id')
        if not final_fingerprint or isinstance(final_fingerprint, dict):
            st.session_state.feedback = {"type": "error", "text": "無法確認報到，識別碼遺失，請刷新頁面再試一次。"}
            st.session_state.sound_to_play = ERROR_SOUND_URL
            st.rerun()
            return

        # Check if this device has already been used
        if 'DeviceFingerprint' in df.columns and not df[df['DeviceFingerprint'] == final_fingerprint].empty:
            st.session_state.feedback = {"type": "error", "text": "此裝置已用於報到，請勿代他人操作。"}
            st.session_state.sound_to_play = ERROR_SOUND_URL
        else:
            table_no = employee_row['TableNo'].iloc[0]
            tz = pytz.timezone(TIMEZONE)
            timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

            # Update Google Sheet
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, 4, timestamp) # Col 4: CheckInTime
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, 6, final_fingerprint) # Col 6: DeviceFingerprint

            st.session_state.feedback = {"type": "success", f"text": f"報到成功！歡迎 {name}，您的桌號是 {table_no}"}
            st.session_state.sound_to_play = SUCCESS_SOUND_URL

        # Reset state
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
            update_cell(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, row_index, 5, timestamp) # Col 5: CheckOutTime
            st.session_state.feedback = {"type": "success", "text": f"簽退成功，{name}，祝您有個美好的一天！"}
            st.session_state.sound_to_play = SUCCESS_SOUND_URL

            # Reset state
            st.session_state.selected_employee_id = None
            st.session_state.search_term = ""
            st.rerun()

    if st.button("返回"):
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()

if __name__ == "__main__":
    main()
