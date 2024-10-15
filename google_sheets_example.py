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
ID_SHEET_NAME = "Sensor Modules"
OUT_SHEET_NAME = "Tester Output"

ARRAY_ASSY_TYPES = {
    1: "Backplanes",
    2: "Sensor Arrays",
    3: "Sensor Modules"
}

''' 
Function that pulls the array TFT type from the sheet 'Sensing Inventory'/'Sensor Modules'/'Sensor Module SN'
It queries the spreadsheet in column 'A' (default) and auto-parses the input array_id regardless of type
(backplane, array, module). It then looks in the corresponding column 'Q' (default) and pulls TFT type (1 or 3)
Parameters:
  creds:      Initialized Google Apps credential, with token.json initialized. Refer to 'main()' in
              'google_sheets_example.py' for initialization example
  array_id:   The query, can be a backplane, assembly, or module id, in the format 'E2421-002-001-E5_T1_R1-103'
  dieid_cols: The column in which to search for the query, by default column 'A'
  dieid_tfts: The column with the corresponding TFT count, by default column 'Q'
  spreadsheet_id: The Google Sheets spreadsheet ID, extracted from the URL (docs.google.com/spreadsheets/d/***)
  id_sheet_name : The name of the sheet to search in for array_id, by default set by global variable
Returns:
  String with '1' for 1T array or '3' for 3T array, or NoneType object if not found/error
'''
def get_array_transistor_type(creds, array_id, dieid_cols='A', dieid_tfts='Q', 
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
        if (values_dieid[i][0].rstrip("_").upper().split('_')[0] == array_id.upper().split('_')[0]):
          # print("Found at index " + str(i))
          found_array = True
          tft_type = values_tfttype[i][0]
          break
    if (found_array):
      if (tft_type.split('-')[0] == 'FS'):
        return tft_type.split('-')[1][0]
      else:
        return tft_type.split('-')[0][0]
    else:
      print("Array not found!")
      return None
  except HttpError as err:
    print(err)
    return None

''' 
Writes a row to a spreadsheet, in particular the results sheet of the 'Sensing Inventory' spreadsheet.
This payload is a 1D row array containing the desired values to write to the sheet.
Data is appended after the last data-containing row of the spreadsheet.
Parameters:
  creds:      Initialized Google Apps credential, with token.json initialized. Refer to 'main()' in
              'google_sheets_example.py' for initialization example
  payload:    a 1D array containing the data to write to the spreadsheet, in string format
  range_out_start_col: The first (leftmost) column to start writing to
  range_out_end_Col  : The last (rightmost) column to end writing to
  spreadsheet_id: The Google Sheets spreadsheet ID, extracted from the URL (docs.google.com/spreadsheets/d/***)
  out_sheet_name : The name of the sheet to write in, by default set to global variable
Returns:
  True if successfully written, or False otherwise
'''
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

'''
Returns a Python OAuth credential object that can be used to access Google Apps services,
in particular Google Sheets.
Parameters:
  token_filename : String path to the OAuth token, generated in Google Apps
  cred_filename  : String path to the OAuth secret credential file, which MUST BE KEPT PRIvATE
  scopes         : List containing link to the Google application to access
Returns:
  Python OAuth credentials object, or None if initialization error
'''
def get_creds(token_filename="token.json", cred_filename="credentials.json", scopes=SCOPES):
  try:
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_filename):
      creds = Credentials.from_authorized_user_file(token_filename, scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
      else:
        flow = InstalledAppFlow.from_client_secrets_file(
            cred_filename, scopes
        )
        creds = flow.run_local_server(port=0)
      # Save the credentials for the next run
      with open(token_filename, "w") as token:
        token.write(creds.to_json())
    return creds
  except HttpError as err:
    print(err)
    return None

def main():
  array_id = input("Array ID please: ")
  array_stage = ARRAY_ASSY_TYPES[len(array_id.rstrip('_').split('_'))]
  
  creds = get_creds()
  if creds is None:
    print("ERROR: Could not initialize Google Sheets...")
    return -1
  tft_type = get_array_transistor_type(creds, array_id)
  print(tft_type)
  # Add check that tft_type is not None
  timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  payload = [timestamp, array_id, array_stage, tft_type, "herp", "terp", "erp"]
  write_to_spreadsheet(creds, payload)

if __name__ == "__main__":
  main()