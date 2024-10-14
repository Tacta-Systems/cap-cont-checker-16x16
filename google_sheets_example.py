import datetime
import os.path
import random

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Spreadsheet ID
SPREADSHEET_ID = "1U0fXZTtxtd9mQf37cgzLy9CH4UH5T_lKMpFjCBX9qVs"
ID_SHEET_NAME = "Test_Data"
OUT_SHEET_NAME = "Sheet1"

def get_array_transistor_type(creds, array_id, dieid_cols='O', dieid_tfts='Q', 
                              spreadsheet_id=SPREADSHEET_ID, id_sheet_name=ID_SHEET_NAME):
  try:
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    # Define the range (A1 notation) to append the data at the end of the sheet
    range_name_dieid = f'{id_sheet_name}!' + dieid_cols + ':' + dieid_cols
    range_name_tfttype = f'{id_sheet_name}!' + dieid_tfts + ':' + dieid_tfts
    result_dieid = (
      sheet.values()
      .get(spreadsheetId=spreadsheet_id, range=range_name_dieid)
      .execute()
    )
    result_tfttype = (
      sheet.values()
      .get(spreadsheetId=spreadsheet_id, range=range_name_tfttype)
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
          # print("Found at index " + str(i))
          found_array = True
          tft_type = values_tfttype[i][0]
          break
    if (found_array):
      return tft_type.split('-')[1][0]
    else:
      return None
  except HttpError as err:
    print(err)
    return None

def write_to_spreadsheet(creds, payload, range_out_start_col='A', range_out_end_col='E', 
                         spreadsheet_id=SPREADSHEET_ID, out_sheet_name=OUT_SHEET_NAME):
  if (type(payload) is not list):
    print("ERROR: payload is not a list...")
    return False
  try:
    service = build("sheets", "v4", credentials=creds)
     # Prepare the request body with the values to append
    body_out = {
        'values': [payload]
    }
    range_name_out = f'{out_sheet_name}!' + range_out_start_col + ':' + range_out_end_col
    print(range_name_out)
    # Call the API to append the new row
    sheet = service.spreadsheets()
    result = sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name_out,
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body=body_out
    ).execute()
    return True
  except HttpError as err:
    print(err)
    return False

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
  #tft_type = get_array_transistor_type(creds, array_id)
  #print(tft_type)
  timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  payload = [timestamp, array_id, "derp"]
  write_to_spreadsheet(creds, payload)

if __name__ == "__main__":
  main()