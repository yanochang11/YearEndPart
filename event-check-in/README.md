# Event Check-in/out System

This is a simple web application for event check-in and check-out using Streamlit and Google Sheets as a backend database.

## Features

-   **Simple Interface**: A clean and simple interface for users to enter their EmployeeID.
-   **Admin Panel**: An admin panel to switch between "Check-in" and "Check-out" modes and to set the time window for the operations.
-   **Google Sheets Integration**: Uses a Google Sheet as the backend database to store employee information and timestamps.
-   **Caching**: Caches the Google Sheet data to minimize API calls and handle concurrent users.
-   **Cookie-based Check-in**: Sets a browser cookie to prevent duplicate check-ins.

## Setup Instructions

### 1. Google Cloud Service Account Setup

1.  **Create a Google Cloud Platform (GCP) Project**:
    -   Go to the [GCP Console](https://console.cloud.google.com/).
    -   Create a new project or select an existing one.

2.  **Enable Google Drive and Google Sheets APIs**:
    -   In your GCP project, go to "APIs & Services" > "Library".
    -   Search for and enable the "Google Drive API" and "Google Sheets API".

3.  **Create a Service Account**:
    -   Go to "APIs & Services" > "Credentials".
    -   Click "Create Credentials" and select "Service account".
    -   Fill in the service account details and grant it the "Editor" role.
    -   Click "Done".

4.  **Generate a JSON Key**:
    -   In the "Credentials" page, find your newly created service account.
    -   Click on the service account email.
    -   Go to the "Keys" tab and click "Add Key" > "Create new key".
    -   Select "JSON" as the key type and click "Create".
    -   A JSON file will be downloaded. This is your `credentials.json` file.

### 2. Google Sheet Setup

1.  **Create a new Google Sheet**:
    -   The sheet must contain the following columns in this order: `EmployeeID`, `Name`, `TableNo`, `CheckInTime`, `CheckOutTime`.

2.  **Share the Google Sheet**:
    -   Open the `credentials.json` file and find the `client_email` value.
    -   In your Google Sheet, click the "Share" button.
    -   Paste the `client_email` into the sharing settings and give it "Editor" permissions.

### 3. Application Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd event-check-in
    ```

2.  **Configure Credentials and Admin Password**:
    -   Open the `.streamlit/secrets.toml` file.
    -   Copy the contents of your downloaded `credentials.json` file and paste them into the `secrets.toml` file, matching the keys under the `[gcp_service_account]` section.
    -   Set a password for the admin panel by changing the `password` value under the `[admin]` section.

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Application**:
    > **Important:** This is a Streamlit application and must be run with the `streamlit run` command.
    ```bash
    streamlit run app.py
    ```

## Troubleshooting

### `st.cache` Deprecation Warning

You may see a warning about `st.cache` being deprecated. This is a known issue with the `streamlit-cookies-manager` library and can be safely ignored. The application will still function correctly.

## `requirements.txt`

```
streamlit
gspread
pandas
gspread-dataframe
oauth2client
streamlit-cookies-manager
```
