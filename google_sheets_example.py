import datetime
import os.path
import random

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Spreadsheet ID
SPREADSHEET_ID = "1U0fXZTtxtd9mQf37cgzLy9CH4UH5T_lKMpFjCBX9qVs"
SHEET_NAME = "Sheet1"

def main():
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("sheets", "v4", credentials=creds)

    # Get the current timestamp in the format YYYY-MM-DD HH:MM:SS
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Generate a serial number (replace with your actual logic)
    serial_number = random.randint(1000, 9999)

    # Simulate a test result
    test_result = random.choice(['PASS', 'FAIL'])

    # The data to append (timestamp, serial number, test result)
    new_row = [timestamp, serial_number, test_result]

    # Define the range (A1 notation) to append the data at the end of the sheet
    range_name = f'{SHEET_NAME}!A:C'

    # Prepare the request body with the values to append
    body = {
        'values': [new_row]
    }

    # Call the API to append the new row
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body=body
    ).execute()

    print(f"Appended new row: {new_row}")
    print(f"Update result: {result}")
  except HttpError as err:
    print(err)

if __name__ == "__main__":
  main()