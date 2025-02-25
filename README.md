# osu! Google Sheet Updater

A Python application to update Google Sheets with osu! match data.

## 📋 Features

- Fetch osu! match data using the osu! API.
- Update Google Sheets with player scores.
- Simple GUI for ease of use.

## ⚙️ Setup Instructions

### 1️⃣ **Prerequisites**
- Python 3.x installed on your system.
- Create the json file through the steps below
  1.) Open this link: https://console.cloud.google.com/ and login with your google account
  2.) Create a New Project (Which you can name whatever you want, but it might be good to relate it to this)
  3.) Go to APIs & Services in the menu on the left, search Google Sheets API, and enable it. Repeat for Google Drive API
  4.) Go to APIs & Services, then credentials in that. Click "Create Credentials" and Service Account. Name this whatever you want, and fillin the rest (just hit continue)
  5.) Go to the service account you just created, then go to keys and create new key. Then download the JSON
  6.) Save the JSON to a place you will rememember, it will be where you go to upload the json file and access info

### 2️⃣ **Google Sheets Setup**
1. Share your Google Spreadsheet with the **@osu-sheet-automation.iam.gserviceaccount.com** found in the JSON file.
2. Grant **Editor** access.

### 3️⃣ **Running the App**
1. Install dependencies:

   ```bash
   pip install -r requirements.txt
(This would be run in the terminal in whatever you use to run python)
