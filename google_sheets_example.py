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
ID_SHEET_NAME = "Test_Data"
OUT_SHEET_NAME = "Sheet1"

def main():
  array_id = input("Array ID please: ")
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
    sheet = service.spreadsheets()
    # Define the range (A1 notation) to append the data at the end of the sheet
    range_name_dieid = f'{ID_SHEET_NAME}!O:O'
    range_name_tfttype = f'{ID_SHEET_NAME}!Q:Q'
    range_name_out = f'{OUT_SHEET_NAME}!A:E'

    result_dieid = (
      sheet.values()
      .get(spreadsheetId=SPREADSHEET_ID, range=range_name_dieid)
      .execute()
    )
    result_tfttype = (
      sheet.values()
      .get(spreadsheetId=SPREADSHEET_ID, range=range_name_tfttype)
      .execute()
    )
    values_dieid = result_dieid.get("values", [])
    values_tfttype = result_tfttype.get("values", [])

    found_array = False
    i = 0
    tft_type="INVALID"
    for i in range(len(values_dieid)):
      if (len(values_dieid[i]) > 0):
        if (values_dieid[i][0] == array_id):
          print("Found at index " + str(i))
          found_array = True
          tft_type = values_tfttype[i][0]
          break
    if (found_array):
      print(tft_type)
    '''
    values = result.get("values", [])
    found_array = False
    for row in values:
      if (len(row) > 2):
        if (row[0] == array_id):
          row_truncated = row[2].replace('FS-', '').split('-')[0]
          print(row_truncated)
          found_array = True
    if not found_array:
      print("Array not found")
    '''
    # Get the current timestamp in the format YYYY-MM-DD HH:MM:SS
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Generate a serial number (replace with your actual logic)
    serial_number = array_id
    # The data to append (timestamp, serial number, tft type, test result)
    new_row = [timestamp, serial_number, tft_type]

    # Prepare the request body with the values to append
    body = {
        'values': [new_row]
    }

    # Call the API to append the new row
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name_out,
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body=body
    ).execute()

    #print(f"Appended new row: {new_row}")
    #print(f"Update result: {result}")
  except HttpError as err:
    print(err)

if __name__ == "__main__":
  main()