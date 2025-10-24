import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from datetime import datetime, time, timedelta
from streamlit_cookies_manager import EncryptedCookieManager
import pytz

# --- Timezone Configuration ---
TIMEZONE = "Asia/Taipei"

# --- Google Sheets Connection ---
@st.cache_resource(ttl=600)
def get_gsheet():
    # ... (rest of the function is the same)
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

def find_employee(client, sheet_name, worksheet_name, search_term):
    """Finds an employee by EmployeeID or Name in the Google Sheet."""
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        headers = sheet.row_values(1) # Get headers to map data

        # Search by EmployeeID first (Column 1)
        id_cells = sheet.findall(search_term, in_column=1)
        if id_cells:
            row_data = sheet.row_values(id_cells[0].row)
            employee_dict = dict(zip(headers, row_data))
            return [{'row_index': id_cells[0].row, 'data': employee_dict}]

        # If no ID match, search by Name (Column 2)
        name_cells = sheet.findall(search_term, in_column=2)
        if name_cells:
            results = []
            for cell in name_cells:
                row_data = sheet.row_values(cell.row)
                employee_dict = dict(zip(headers, row_data))
                results.append({'row_index': cell.row, 'data': employee_dict})
            return results

        return [] # No matches found
    except Exception as e:
        st.error(f"查詢時發生錯誤 / An error occurred while searching: {e}")
        return None


def update_cell(client, sheet_name, worksheet_name, row, col, value):
    """Updates a single cell in the Google Sheet."""
    if st.session_state.get('mock_mode', False):
        st.info("Mock mode: Simulating a successful update.")
        return

    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        # Clear the cache to reflect the update
        get_data.clear()
    except Exception as e:
        st.error(f"Failed to update Google Sheet: {e}")

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
        st.error(f"Could not load settings from Google Sheet: {e}. Using default settings.")
        return {"mode": "Check-in", "start_time": time(9, 0), "end_time": time(17, 0)}

def save_settings(client, sheet_name, mode, start_time, end_time):
    """Saves settings to the 'Settings' worksheet."""
    if st.session_state.get('mock_mode', False):
        st.info("Mock mode: Simulating a successful settings save.")
        return
    try:
        settings_sheet = client.open(sheet_name).worksheet("Settings")
        # Update the range A2:C2 with a list of lists
        settings_sheet.update('A2:C2', [[mode, start_time.strftime('%H:%M'), end_time.strftime('%H:%M')]])
        get_settings.clear() # Clear cache after saving
        st.success("設定已儲存 / Settings saved successfully!")
    except Exception as e:
        st.error(f"儲存設定失敗 / Failed to save settings: {e}")


# --- Main App ---
def main():
    if not st.runtime.exists():
        print("---")
        print("This app must be run with `streamlit run`.")
        print("Please run `streamlit run app.py` to view this application.")
        print("---")
        return

    st.set_page_config(page_title="Event Check-in/out System 尾牙報到系統", initial_sidebar_state="collapsed")
    st.title("Event Check-in/out System 尾牙報到系統")
    cookies = EncryptedCookieManager(
        password=st.secrets.cookies.password,
    )
    if not cookies.ready():
        st.stop()

    # Initialize session state for user-specific data
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ""
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'selected_employee' not in st.session_state:
        st.session_state.selected_employee = None

    GOOGLE_SHEET_NAME = "Event_Check-in"
    WORKSHEET_NAME = "Sheet1"

    client = get_gsheet()
    settings = get_settings(client, GOOGLE_SHEET_NAME)

    # --- Main App ---
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

    # Use settings from Google Sheet for the check
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).time()
    if not (settings['start_time'] <= now <= settings['end_time']):
        st.warning("報到尚未開始或已結束 / Not currently open for check-in/out.")
        return

    # --- On-Demand Search Logic ---
    st.session_state.search_term = st.text_input("請輸入您的員工編號或姓名 / Please enter your Employee ID or Name:", value=st.session_state.search_term).strip()

    if st.button("確認 / Confirm"):
        # Reset state on new search
        st.session_state.selected_employee = None
        st.session_state.search_results = None
        if not st.session_state.search_term:
            st.error("請輸入您的員工編號或名字 / Please enter your Employee ID or Name")
        else:
            # Perform the on-demand search
            results = find_employee(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME, st.session_state.search_term)
            if not results:
                st.error("查無此人，請確認輸入是否正確，或洽詢工作人員 / User not found, please check your input or contact staff.")
            elif len(results) == 1:
                st.session_state.selected_employee = results[0]
            else: # Multiple matches
                st.warning("找到多位同名員工，請選擇一位 / Multiple employees found with the same name, please select one:")
                st.session_state.search_results = results
        st.rerun()

    # --- Disambiguation for multiple results ---
    if st.session_state.search_results:
        for result in st.session_state.search_results:
            emp = result['data']
            if st.button(f"{emp['Name']} ({emp['EmployeeID']})", key=emp['EmployeeID']):
                st.session_state.selected_employee = result
                st.session_state.search_results = None
                st.rerun() # Rerun to process the selection immediately

    # --- Process the selected employee ---
    if st.session_state.selected_employee:
        employee_data = st.session_state.selected_employee['data']
        row_index = st.session_state.selected_employee['row_index']

        st.info(f"正在為 {employee_data['Name']} ({employee_data['EmployeeID']}) 進行操作 / Processing for {employee_data['Name']} ({employee_data['EmployeeID']})")

        if settings['mode'] == "Check-in":
            handle_check_in(employee_data, row_index, client, cookies)
        else: # Check-out
            handle_check_out(employee_data, row_index, client)

        # Clear state after processing and rerun to reset the interface
        st.session_state.selected_employee = None
        st.session_state.search_term = ""
        st.session_state.search_results = None
        st.rerun()


def handle_check_in(employee_data, row_index, client, cookies):
    # 1. Check if the device has already been used by checking for the cookie's existence.
    if 'event_checked_in' in cookies:
        st.warning("此裝置已完成報到，如需為他人報到，請使用其他裝置 / This device has already been used for check-in.")
        return

    # 2. Check the Google Sheet to see if this specific employee has already checked in.
    check_in_time = employee_data.get('CheckInTime', '')
    if check_in_time and str(check_in_time).strip(): # Check if not None and not empty
        st.warning("您已報到，無須重複操作 / You have already checked in.")
        return

    # 3. If all checks pass, proceed with the check-in process.
    name = employee_data.get('Name')
    table_no = employee_data.get('TableNo')
    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    # Update the Google Sheet (Column 4 is CheckInTime)
    update_cell(client, "Event_Check-in", "Sheet1", row_index, 4, timestamp)

    # Set the cookie to block further check-ins from this device.
    cookies['event_checked_in'] = "true"
    cookies.save()

    st.success(f"報到成功！歡迎 {name}，您的桌號在 {table_no} / Check-in successful! Welcome {name}, your table is {table_no}")


def handle_check_out(employee_data, row_index, client):
    check_out_time = employee_data.get('CheckOutTime', '')
    if check_out_time and str(check_out_time).strip(): # Check if not None and not empty
        st.warning("您已完成簽退 / You have already checked out.")
        return

    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    # Update the Google Sheet (Column 5 is CheckOutTime)
    update_cell(client, "Event_Check-in", "Sheet1", row_index, 5, timestamp)
    st.success("簽退成功，祝您有個美好的一天！ / Check-out successful, have a nice day!")


if __name__ == "__main__":
    main()
