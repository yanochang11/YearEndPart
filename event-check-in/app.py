import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from datetime import datetime, time, timedelta
import pytz
import streamlit.components.v1 as components
# 【關鍵修正 1】: 引入 Cookie Manager
import streamlit_cookies_manager

# --- Timezone Configuration ---
TIMEZONE = "Asia/Taipei"

# --- Google Sheets Connection ---
@st.cache_resource(ttl=600)
def get_gsheet():
    """Establishes a connection to the Google Sheet using cached credentials."""
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
    """Fetches the entire employee list and caches it for 60 seconds."""
    try:
        sheet = _client.open(sheet_name).worksheet(worksheet_name)
        data = get_as_dataframe(sheet)
        if 'EmployeeID' in data.columns:
            data['EmployeeID'] = data['EmployeeID'].astype(str)
        return data
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Spreadsheet '{sheet_name}' not found. Please check configuration.")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_name}' not found. Please check configuration.")
        return pd.DataFrame()

def update_cell(client, sheet_name, worksheet_name, row, col, value):
    """Updates a single cell in the Google Sheet and clears relevant caches."""
    if st.session_state.get('mock_mode', False):
        st.info("Mock mode: Simulating a successful update.")
        return
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        get_data.clear()
    except Exception as e:
        st.error(f"Failed to update Google Sheet: {e}")

# --- Settings Management ---
@st.cache_data(ttl=60)
def get_settings(_client, sheet_name):
    """Fetches settings from the 'Settings' worksheet and caches them."""
    try:
        settings_sheet = _client.open(sheet_name).worksheet("Settings")
        mode = settings_sheet.acell('A2').value
        start_time_str = settings_sheet.acell('B2').value
        end_time_str = settings_sheet.acell('C2').value
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        return {"mode": mode, "start_time": start_time, "end_time": end_time}
    except Exception as e:
        st.error(f"Could not load settings from Google Sheet: {e}. Using default settings.")
        return {"mode": "Check-in", "start_time": time(9, 0), "end_time": time(17, 0)}

def save_settings(client, sheet_name, mode, start_time, end_time):
    """Saves settings to the 'Settings' worksheet."""
    if st.session_state.get('mock_mode', False):
        st.info("Mock mode: Simulating a successful settings save.")
        return
    try:
        settings_sheet = client.open(sheet_name).worksheet("Settings")
        settings_sheet.update('A2:C2', [[mode, start_time.strftime('%H:%M'), end_time.strftime('%H:%M')]])
        get_settings.clear()
        st.success("設定已儲存 / Settings saved successfully!")
    except Exception as e:
        st.error(f"儲存設定失敗 / Failed to save settings: {e}")

def main():
    """Main function to run the Streamlit application."""
    st.set_page_config(page_title="Event Check-in/out System", initial_sidebar_state="collapsed")
    
    # 【關鍵修正 2】: 初始化 Cookie Manager
    # `key` 參數是為了讓 manager 在 session state 中有一個獨立的命名空間
    cookies = streamlit_cookies_manager.CookieManager(key="app_cookie_manager")

    st.title("Event Check-in/out System")

    # --- Device Fingerprint Handling ---
    # 【關鍵修正 3】: 優先從 Cookie 中讀取 Fingerprint
    fingerprint_from_cookie = cookies.get('device_fingerprint')

    # 只有在 Cookie 中不存在 fingerprint 時，才執行 JS 來獲取
    if not fingerprint_from_cookie:
        js_code = '''
        <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
        <script>
          function setFingerprint() {
            const fpPromise = FingerprintJS.load();
            fpPromise
              .then(fp => fp.get())
              .then(result => {
                const visitorId = result.visitorId;
                console.log("Device Fingerprint:", visitorId);
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
          setFingerprint();
        </script>
        '''
        components.html(js_code, height=0)

    # 這個隱藏元件現在只作為 JS 首次獲取 fingerprint 時的臨時橋樑
    st.text_input("Device Fingerprint JS Bridge", key="device_fingerprint_hidden", label_visibility="hidden",
                  placeholder="__fingerprint_placeholder__")

    # --- Main App Logic ---
    if 'authenticated' not in st.session_state: st.session_state.authenticated = False
    if 'search_term' not in st.session_state: st.session_state.search_term = ""
    if 'selected_employee_id' not in st.session_state: st.session_state.selected_employee_id = None
    if 'feedback_message' not in st.session_state: st.session_state.feedback_message = None
    if 'device_fingerprint' not in st.session_state:
        # 【關鍵修正 4】: 初始化 session_state 時，優先使用 Cookie 的值
        st.session_state.device_fingerprint = fingerprint_from_cookie

    # 【關鍵修正 5】: 如果 Cookie 中沒有，則嘗試從 JS 橋樑獲取，並存入 Cookie
    temp_fingerprint_from_js = st.session_state.get('device_fingerprint_hidden')
    if not st.session_state.device_fingerprint and temp_fingerprint_from_js and temp_fingerprint_from_js != "__fingerprint_placeholder__":
        st.session_state.device_fingerprint = temp_fingerprint_from_js
        # 將首次獲取的值存入 Cookie，讓它在下次刷新後依然存在
        cookies['device_fingerprint'] = temp_fingerprint_from_js
        cookies.save() # 寫入瀏覽器
        st.rerun() # 立即重新整理一次，確保後續邏輯都從已存在的 state 開始

    GOOGLE_SHEET_NAME = "Event_Check-in"
    WORKSHEET_NAME = "Sheet1"

    client = get_gsheet()
    settings = get_settings(client, GOOGLE_SHEET_NAME)
    st.markdown(f"**目前模式 / Current Mode:** `{settings['mode']}`")

    with st.sidebar.expander("管理員面板 / Admin Panel", expanded=False):
        if not st.session_state.authenticated:
            password = st.text_input("請輸入密碼 / Enter password:", type="password", key="password_input")
            if st.button("登入 / Login"):
                if password == st.secrets.admin.password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("密碼錯誤 / Incorrect password")
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

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).time()
    if not (settings['start_time'] <= now <= settings['end_time']):
        st.warning("報到尚未開始或已結束 / Not currently open for check-in/out.")
        return

    with st.spinner("正在載入員工名單，請稍候... / Loading employee list..."):
        df = get_data(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME)

    if df.empty:
        st.error("無法載入員工名單，請洽詢工作人員 / Could not load employee list, please contact staff.")
        return

    if st.session_state.feedback_message:
        message_type = st.session_state.feedback_message["type"]
        message_text = st.session_state.feedback_message["text"]
        if message_type == "success": st.success(message_text)
        elif message_type == "warning": st.warning(message_text)
        elif message_type == "error": st.error(message_text)
        st.session_state.feedback_message = None

    # --- Search and Confirmation Flow ---
    if not st.session_state.get('selected_employee_id'):
        st.session_state.search_term = st.text_input("請輸入您的員工編號或姓名 / Please enter your Employee ID or Name:", value=st.session_state.search_term).strip()
        if st.button("確認 / Confirm"):
            if not st.session_state.search_term:
                st.session_state.feedback_message = {"type": "error", "text": "請輸入您的員工編號或名字 / Please enter your Employee ID or Name"}
            else:
                id_match = df[df['EmployeeID'] == st.session_state.search_term]
                name_match = df[df['Name'] == st.session_state.search_term]
                if not id_match.empty:
                    st.session_state.selected_employee_id = id_match['EmployeeID'].iloc[0]
                elif not name_match.empty:
                    if len(name_match) == 1:
                        st.session_state.selected_employee_id = name_match['EmployeeID'].iloc[0]
                    else:
                        st.session_state.feedback_message = {"type": "warning", "text": "找到多位同名員工，請選擇一位 / Multiple employees found with the same name, please select one:"}
                        for index, row in name_match.iterrows():
                            if st.button(f"{row['Name']} ({row['EmployeeID']})", key=row['EmployeeID']):
                                st.session_state.selected_employee_id = row['EmployeeID']
                                st.rerun()
                        return
                else:
                    st.session_state.feedback_message = {"type": "error", "text": "查無此人，請確認輸入是否正確，或洽詢工作人員 / User not found, please check your input or contact staff."}
            st.rerun()
    else: # An employee has been selected
        employee_id = st.session_state.selected_employee_id
        employee_row = df[df['EmployeeID'] == employee_id]
        if not employee_row.empty:
            row_index = employee_row.index[0] + 2
            if settings['mode'] == "Check-in":
                handle_check_in(df, employee_row, row_index, client)
            else:
                handle_check_out(employee_row, row_index, client)

def handle_check_in(df, employee_row, row_index, client):
    """Handles the check-in process for a selected employee."""
    check_in_time = employee_row['CheckInTime'].iloc[0]
    if pd.notna(check_in_time) and str(check_in_time).strip() != '':
        st.session_state.feedback_message = {"type": "warning", "text": "您已報到，無須重複操作 / You have already checked in."}
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()
        return

    name = employee_row['Name'].iloc[0]
    employee_id = employee_row['EmployeeID'].iloc[0]
    st.info(f"正在為 **{name}** ({employee_id}) 辦理報到手續。 / Processing check-in for **{name}** ({employee_id}).")

    # 從 session_state 讀取指紋
    fingerprint = st.session_state.get('device_fingerprint')

    # 檢查指紋是否已成功獲取
    if not fingerprint:
        st.warning("正在識別您的裝置，請稍候... / Identifying your device, please wait...")
        st.text_input("設備識別碼 / Device Fingerprint", "正在獲取中... / Acquiring...", disabled=True)
        # 不需要手動 rerun，Streamlit 的機制會自動在 JS 橋樑更新值後重跑
        return

    # 顯示指紋，並設定為 disabled，讓使用者無法修改
    st.text_input("設備識別碼 / Device Fingerprint", value=fingerprint, disabled=True)

    if st.button("✅ 確認報到 / Confirm Check-in"):
        # 直接使用我們已安全儲存的指紋
        final_fingerprint = st.session_state.get('device_fingerprint')
        
        if not final_fingerprint:
             st.error("無法確認報到，識別碼遺失，請刷新頁面再試一次。 / Cannot confirm, fingerprint is missing. Please refresh and try again.")
             return

        # 檢查 Google Sheet 中是否已存在此指紋
        if 'DeviceFingerprint' in df.columns and not df[df['DeviceFingerprint'] == final_fingerprint].empty:
            st.session_state.feedback_message = {"type": "error", "text": "此裝置已完成報到 / This device has already been used for check-in."}
        else:
            table_no = employee_row['TableNo'].iloc[0]
            tz = pytz.timezone(TIMEZONE)
            timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
            update_cell(client, "Event_Check-in", "Sheet1", row_index, 4, timestamp)
            # 假設 DeviceFingerprint 在 G 欄 (第 7 欄)，請根據您的 Sheet 調整
            update_cell(client, "Event_Check-in", "Sheet1", row_index, 6, final_fingerprint)
            st.session_state.feedback_message = {"type": "success", "text": f"報到成功！歡迎 {name}，您的桌號在 {table_no} / Check-in successful! Welcome {name}, your table is {table_no}"}

        # 【關鍵修正 6】: 只重設使用者相關的狀態，保留 fingerprint
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""
        st.rerun()

def handle_check_out(employee_row, row_index, client):
    """Handles the check-out process for a selected employee."""
    check_out_time = employee_row['CheckOutTime'].iloc[0]
    if pd.notna(check_out_time) and str(check_out_time).strip() != '':
        st.session_state.feedback_message = {"type": "warning", "text": "您已完成簽退 / You have already checked out."}
    else:
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        update_cell(client, "Event_Check-in", "Sheet1", row_index, 5, timestamp)
        st.session_state.feedback_message = {"type": "success", "text": "簽退成功，祝您有個美好的一天！ / Check-out successful, have a nice day!"}

    st.session_state.selected_employee_id = None
    st.session_state.search_term = ""
    st.rerun()

if __name__ == "__main__":
    main()
