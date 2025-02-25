import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# ---- osu! API Credentials ----
CLIENT_ID = '38538'  # Your osu! API Client ID
CLIENT_SECRET = '1Eoq9oBjODYkT3VFfwDcJZq4iLkD76dEP1QCUDge'  # Your osu! API Client Secret

# ---- Google Sheets Setup ----
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "D:\\Python Code\\For Fun\\osu-sheet-automation.json"  # Path to your Google Service Account JSON

# Authenticate and connect to Google Sheets
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
client = gspread.authorize(creds)

# Open your Google Spreadsheet
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1cq9qz1DhXhHtFONJgVPReEeilkn0eSep0gk3kDGSoHk/edit?gid=1169400080#gid=1169400080"
spreadsheet = client.open_by_url(SPREADSHEET_URL)

# List of valid sheet names
VALID_SHEETS = [
    "Qualifiers", "Group Stage", "Round of 128", "Round of 64", "Round of 32",
    "Round of 16", "Quarterfinals", "Semifinals", "Finals", "Grand Finals"
]

# Cache for usernames to minimize API calls
username_cache = {}

# ---- Step 1: Get osu! API Access Token ----
def get_osu_access_token(client_id, client_secret):
    token_url = 'https://osu.ppy.sh/oauth/token'
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
        'scope': 'public'
    }
    response = requests.post(token_url, json=payload)
    if response.status_code == 200:
        print("✅ Successfully authenticated with osu! API.")
        return response.json()['access_token']
    else:
        print("❌ Failed to authenticate with osu! API.")
        raise Exception(f"Failed to get access token: {response.text}")

# ---- Step 2: Fetch Match Data ----
def get_osu_match_data(match_id, access_token):
    match_url = f'https://osu.ppy.sh/api/v2/matches/{match_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(match_url, headers=headers)
    if response.status_code == 200:
        match_data = response.json()
        print("📋 Fetched Match Data.")
        return match_data
    else:
        raise Exception(f"Failed to get match data: {response.text}")

# ---- Get Username from User ID ----
def get_osu_username(user_id, access_token):
    if user_id in username_cache:
        return username_cache[user_id]
    
    url = f'https://osu.ppy.sh/api/v2/users/{user_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        username = user_data.get('username', f"Unknown User ({user_id})")
        username_cache[user_id] = username  # Cache the username
        return username
    else:
        print(f"⚠️ Failed to fetch username for user_id {user_id}: {response.text}")
        return f"Unknown User ({user_id})"

# ---- Utility Function to Extract Beatmap Title ----
def extract_beatmap_title(beatmap_info):
    beatmap_title = (beatmap_info.get('title') or
                     beatmap_info.get('title_unicode') or
                     beatmap_info.get('beatmapset', {}).get('title') or
                     beatmap_info.get('version') or
                     'Unknown Beatmap')

    beatmap_title_clean = re.sub(r'\[.*?\]', '', beatmap_title).strip().lower()
    return beatmap_title_clean

# ---- Check if Map is FM ----
def is_fm_map(row):
    if len(row) > 3:
        col_d_content = str(row[3]).strip().lower()
        return 'fm' in col_d_content
    return False

# ---- Format Accuracy ----
def format_accuracy(accuracy):
    scaled = accuracy * 100
    return round(scaled, 2)

# ---- Map Beatmap Names from Google Sheet ----
def build_beatmap_rows(data):
    beatmap_rows = {}
    starting_row = 8  # Adjusted to Row 9 in Google Sheets (0-indexed as 8)

    print("\n🔍 Building Beatmap Rows Mapping:")
    for row_idx in range(starting_row, len(data), 3):  # Increase by 3 for each map
        beatmap_name_row = row_idx  # Beatmap name is in the first row of each block

        # Debug: Print entire row to verify contents
        print(f"Row {beatmap_name_row + 1} Content: {data[beatmap_name_row]}")

        if len(data[beatmap_name_row]) > 4:
            beatmap_full_name = str(data[beatmap_name_row][4]).strip()  # Assuming beatmap name is in Column E
            print(f"Row {beatmap_name_row + 1}: Raw Beatmap Name -> '{beatmap_full_name}'")  # Debug

            if beatmap_full_name:
                # Strip mapper name and clean beatmap title
                beatmap_title = beatmap_full_name.split(" - ", 1)[-1].strip()
                beatmap_title_clean = re.sub(r'\[.*?\]', '', beatmap_title).strip().lower()

                print(f"Processed Beatmap Name -> '{beatmap_title_clean}'")  # Debug

                # Add to mapping with the score row (beatmap name row + 1)
                beatmap_rows[beatmap_title_clean] = beatmap_name_row + 1
            else:
                print(f"⚠️ No beatmap name found in Row {beatmap_name_row + 1}")
        else:
            print(f"⚠️ Row {beatmap_name_row + 1} does not have enough columns.")

    print("\n🎵 Final Beatmap Rows Mapping:", beatmap_rows)
    return beatmap_rows

# ---- Step 3: Update Selected Google Sheet with Match Data ----
def update_google_sheet_with_match_data(sheet, match_data, access_token):
    data = sheet.get_all_values()

    # Get player names from row 4 starting from column G
    player_columns = {}
    for col_idx in range(6, len(data[3])):  # Column G is index 6
        player_name = str(data[3][col_idx]).strip().lower()
        if player_name:
            player_columns[player_name] = col_idx

    print("👥 Player columns mapping:", player_columns)

    # Build beatmap rows mapping
    beatmap_rows = build_beatmap_rows(data)

    # Process games from match data
    events = match_data.get('events', [])
    for event in events:
        game = event.get('game', None)
        if not game:
            continue

        beatmap_info = game.get('beatmap', {})
        beatmap_name = extract_beatmap_title(beatmap_info)
        print(f"🎯 Processing Beatmap: {beatmap_name}")

        if beatmap_name not in beatmap_rows:
            print(f"⚠️ Beatmap '{beatmap_name}' not found in sheet. Skipping...")
            continue

        beatmap_row_index = beatmap_rows[beatmap_name]
        fm_map = is_fm_map(data[beatmap_row_index - 1])  # Check FM status from beatmap name row

        scores = game.get('scores', [])
        for score_entry in scores:
            user_id = score_entry.get('user_id')
            if not user_id:
                continue

            username = get_osu_username(user_id, access_token).strip().lower()
            print(f"🏅 Processing Score for Player: {username}")

            if username not in player_columns:
                print(f"⚠️ Player '{username}' not found in sheet headers. Skipping...")
                continue

            player_col_start = player_columns[username]

            # Use accuracy or score based on FM map check
            if fm_map:
                raw_accuracy = score_entry.get('accuracy', 0)
                score_value = format_accuracy(raw_accuracy)
                print(f"🎯 FM Map - Using Accuracy: {score_value}%")
            else:
                score_value = score_entry.get('score', 0)
                print(f"🎯 Regular Map - Using Score: {score_value}")

            # Place scores in consecutive columns on the same row
            max_score_slots = 4  # Limit to 4 scores per player per map
            for slot in range(max_score_slots):
                current_col = player_col_start + slot
                try:
                    cell_value = str(data[beatmap_row_index][current_col])
                except IndexError:
                    cell_value = ''
                existing_score = float(cell_value) if cell_value.replace('.', '', 1).isdigit() else 0

                if existing_score == 0:
                    sheet.update_cell(beatmap_row_index + 1, current_col + 1, score_value)
                    print(f"➕ Inserted new score for {username} on '{beatmap_name}': {score_value}")
                    break
            else:
                # All slots filled; replace the lowest if the new score is higher
                existing_scores = []
                for slot in range(max_score_slots):
                    current_col = player_col_start + slot
                    cell_value = str(data[beatmap_row_index][current_col])
                    existing_score = float(cell_value) if cell_value.replace('.', '', 1).isdigit() else 0
                    existing_scores.append((existing_score, current_col))

                min_score, min_col = min(existing_scores, key=lambda x: x[0])
                if score_value > min_score:
                    sheet.update_cell(beatmap_row_index + 1, min_col + 1, score_value)
                    print(f"✅ Updated {username}'s score on '{beatmap_name}': {min_score} → {score_value}")
                else:
                    print(f"ℹ️ No update needed for {username} on '{beatmap_name}' (Score: {score_value})")

# ---- Main Execution ----
if __name__ == "__main__":
    match_id = "117297949"  # osu! multiplayer match ID

    try:
        # Step 1: Authenticate with osu! API
        access_token = get_osu_access_token(CLIENT_ID, CLIENT_SECRET)

        # Step 2: Prompt user for sheet selection
        print("Available sheets:")
        for idx, sheet_name in enumerate(VALID_SHEETS):
            print(f"{idx + 1}. {sheet_name}")

        selected_index = int(input("Enter the number corresponding to the sheet you want to update: ")) - 1

        if 0 <= selected_index < len(VALID_SHEETS):
            selected_sheet_name = VALID_SHEETS[selected_index]
            sheet = spreadsheet.worksheet(selected_sheet_name)
            print(f"🗂️ Selected sheet: {selected_sheet_name}")
        else:
            print("❌ Invalid selection. Exiting.")
            exit()

        # Step 3: Fetch match data
        match_data = get_osu_match_data(match_id, access_token)
        print(f"📋 Retrieved match data for match ID {match_id}.")

        # Step 4: Update the selected Google Sheet
        update_google_sheet_with_match_data(sheet, match_data, access_token)
        print(f"✅ Google Sheet '{selected_sheet_name}' updated successfully.")

    except Exception as e:
        print("❌ Error:", e)
