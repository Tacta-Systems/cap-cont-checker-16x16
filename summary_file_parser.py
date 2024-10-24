import csv
import glob
import os
import os.path
import datetime as dt
import numpy as np
import re
from collections import defaultdict

# To install Google Python libraries, run this command:
# pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http


# TODO: add code that detects the assembly stage of the array
# TODO: add duplication detection for GSheets based on timestamp

# Google Sheets integration
# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1U0fXZTtxtd9mQf37cgzLy9CH4UH5T_lKMpFjCBX9qVs" # Currently the test sheet
OUT_SHEET_NAME = "Tester Output"

# Dictionary linking summary file keywords to Google Sheets keywords
DICT_SUMMARY_TO_GSHEETS_KEYWORD = {
    "Col to PZBIAS Continuity Detection with TFT's ON" : "Col to PZBIAS with TFT's ON (# shorts)",
    "CAP_COL_TO_PZBIAS"     : "Cap Col to PZBIAS (# pass)",
    "Row to Col"            : "Row to Col (# shorts)",
    "Col to Row"            : "Row to Col (# shorts)",
    "Row to PZBIAS"         : "Row to PZBIAS (# shorts)",
    "PZBIAS to Row"         : "Row to PZBIAS (# shorts)",
    "CONT_ROW_TO_PZBIAS"    : "Row to PZBIAS (# shorts)",
    "Row to SHIELD"         : "Row to SHIELD (# shorts)",
    "SHIELD to Row"         : "Row to SHIELD (# shorts)",
    "CONT_ROW_TO_SHIELD"    : "Row to SHIELD (# shorts)",
    "Col to PZBIAS"         : "Col to PZBIAS (# shorts)",
    "PZBIAS to Col"         : "Col to PZBIAS (# shorts)",
    "CONT_COL_TO_PZBIAS"    : "Col to PZBIAS (# shorts)",    
    "SHIELD to Col"         : "Col to SHIELD (# shorts)",
    "Col to SHIELD"         : "Col to SHIELD (# shorts)",
    "CONT_COL_TO_SHIELD"    : "Col to SHIELD (# shorts)",
    "PZBIAS to Shield"      : "SHIELD to PZBIAS (ohm)",
    "Shield to PZBIAS"      : "SHIELD to PZBIAS (ohm)",
    "CONT_SHIELD_TO_PZBIAS" : "SHIELD to PZBIAS (ohm)",
    # 3T-exclusive test functions below
    "Rst to Col"            : "Rst to Col (# shorts)",
    "Col to Rst"            : "Rst to Col (# shorts)",
    "Vdd to Column"         : "Col to Vdd (# shorts)",
    "Column to Vdd"         : "Col to Vdd (# shorts)",
    "CONT_COL_TO_VDD"       : "Col to Vdd (# shorts)",
    "Vrst to Column"        : "Col to Vrst (# shorts)",
    "Column to Vrst"        : "Col to Vrst (# shorts)",
    "CONT_COL_TO_VRST"      : "Col to Vrst (# shorts)",
    "Rst to SHIELD"         : "Rst to SHIELD (# shorts)",
    "SHIELD to Rst"         : "Rst to SHIELD (# shorts)",
    "CONT_RST_TO_SHIELD"    : "Rst to SHIELD (# shorts)",
    "Rst to PZBIAS"         : "Rst to PZBIAS (# shorts)",
    "PZBIAS to Rst"         : "Rst to PZBIAS (# shorts)",
    "CONT_RST_TO_PZBIAS"    : "Rst to PZBIAS (# shorts)",
    "Vdd to Shield"         : "Vdd to SHIELD (ohm)",
    "Shield to Vdd"         : "Vdd to SHIELD (ohm)",
    "CONT_VDD_TO_SHIELD"    : "Vdd to SHIELD (ohm)",
    "Vdd to PZBIAS"         : "Vdd to PZBIAS (ohm)",
    "PZBIAS to Vdd"         : "Vdd to PZBIAS (ohm)",
    "CONT_VDD_TO_PZBIAS"    : "Vdd to PZBIAS (ohm)",
    "Vrst to Shield"        : "Vrst to SHIELD (ohm)",
    "Shield to Vrst"        : "Vrst to SHIELD (ohm)",
    "CONT_VRST_TO_SHIELD"   : "Vrst to SHIELD (ohm)",
    "Vrst to PZBIAS"        : "Vrst to PZBIAS (ohm)",
    "PZBIAS to Vrst"        : "Vrst to PZBIAS (ohm)",
    "CONT_VRST_TO_PZBIAS"   : "Vrst to PZBIAS (ohm)"
}

ARRAY_ASSY_TYPES = {
    1: "Backplanes",
    2: "Sensor Arrays",
    3: "Sensor Modules"
}

'''
Dictionary used to store results from tests
Results are uploaded to Google Sheets in this order
Tests that were not run will be uploaded to GSheets as blank.
'''
output_payload_gsheets_dict = {
    "Timestamp"            : "",
    "Tester Serial Number" : "",
    "Array Serial Number"  : "",
    "Array Type"           : "",
    "Array Module Stage"   : "",
    "TFT Type"             : "",
    "Loopback One (ohm)"   : "",
    "Loopback Two (ohm)"   : "",
    "Cap Col to PZBIAS (# pass)"   : "",
    "Col to PZBIAS with TFT's ON (# shorts)" : "",
    "Row to Col (# shorts)"    : "",
    "Rst to Col (# shorts)"    : "",
    "Row to PZBIAS (# shorts)" : "",
    "Row to SHIELD (# shorts)" : "",
    "Col to PZBIAS (# shorts)" : "",
    "Col to SHIELD (# shorts)" : "",
    "Col to Vdd (# shorts)"    : "",
    "Col to Vrst (# shorts)"   : "",
    "Rst to SHIELD (# shorts)" : "",
    "Rst to PZBIAS (# shorts)" : "",
    "SHIELD to PZBIAS (ohm)"   : "",
    "Vdd to SHIELD (ohm)"      : "",
    "Vdd to PZBIAS (ohm)"      : "",
    "Vrst to SHIELD (ohm)"     : "",
    "Vrst to PZBIAS (ohm)"     : ""
}

# helper functions for file compare/diff
'''
Helper function that extracts the timestamp from path+filename
Parameters:
    file_name: path + filename
Returns:
    Extracted timestamp, string format (e.g. YYYY-MM-DD_HH-MM-SS)
'''
def get_timestamp_raw(file_name):
    return file_name.split("\\")[-1][:19]

'''
Helper function that extracts the timestamp from filename
Parameters:
    file_name: filename alone, no path
Returns:
    Extracted timestamp, string format (e.g. YYYY-MM-DD_HH-MM-SS)
'''
def get_timestamp_truncated(file_name):    
    return file_name[:19]

'''
Helper function that extracts the text from a string before the keyword
Parameters:
    string: Full text to split
    keyword: Text to search for in string
Returns:
    String with text leading up to keyword, or the full text string if keyword is not in string
'''
def truncate_to_keyword(string, keyword):
    if keyword in string:
        index_val = string.index(keyword)
        return string[:index_val]
    else:
        return string

'''
Opens a text file and splits it into "chunks" based on line breaks
To access each line in each chunk, run the following:
for chunk in chunks:
    for line in chunk:
        print(line)
Parameters:
    file_in: path to the text file, including the filename
Returns:
    List of raw text "chunks", which themselves are lists of each line in the chunk
    e.g. [['chunk1_line', 'chunk1_line', 'chunk1_line'], ['chunk2_line', 'chunk2_line', 'chunk2_line']]
'''
def split_file_into_chunks(file_in):
    try:
        with open(file_in) as file:
            file_list = file.readlines()
            file_chunk_indices = [0]
            file_chunk_tuples = []
            file_chunks_raw = []

            # detects the indices of line breaks in the file, then appends them to another list
            for i in range(len(file_list)):
                if file_list[i] in ['\n', '\r\n']:
                    file_chunk_indices.append(i)
            file_chunk_indices.append(len(file_list))

            # creates a list of tuples with (start, end) indices for each chunk
            for i in range(1, len(file_chunk_indices)):
                file_chunk_tuples.append((file_chunk_indices[i-1], file_chunk_indices[i]))

            # all tuples except the first one have a leading "\n", so this is handled here
            # also handles empty lines
            # appends chunks (list type) to the output list
            for tuple in file_chunk_tuples:
                if (tuple[1]-tuple[0] > 1):
                    if (file_list[tuple[0]] == "\n"):
                        file_chunks_raw.append(file_list[tuple[0]+1:tuple[1]])    
                    else:
                        file_chunks_raw.append(file_list[tuple[0]:tuple[1]])
            return file_chunks_raw
    except Exception as e:
        print("Error: " + e)
        return None # if can't open file

'''
Checks to see if any of the keys in a dictionary are in a string
Parameters:
    string_in: String to search in
    dict: Dictionary with keys to search in
Returns:
    Tuple, with following parameters:
        True if string has any of the keys, False otherwise
        String of the key that's in the string, or None otherwise
'''
def check_str_in_dict_keys(string_in, dict=DICT_SUMMARY_TO_GSHEETS_KEYWORD):
    for key in list(dict.keys()):
        if (key in string_in):
            return (True, key)
    return (False, None)

'''
Extracts number(s) (scientific notation or number) from a string
Parameters:
    string_in: String to search in
Returns:
    List of numbers as floats
'''
def extract_num_from_str(string_in):
    out_array = []
    for str in string_in.split():
        try:
            out_array.append(float(str.replace(",","")))
        except ValueError:
            pass
    return out_array

'''
Extracts the header (timestamp, arrayid, arraytype)
Parameters:
    chunk: should be the first chunk from the file, containing timestamp, arrayid, arraytype
Returns:
    Array with tuples of "timestamp", "Array Serial Number", "TFT Type" and their corresponding values
'''
def extract_header_from_chunk(chunk):
    timestamp = chunk[0][:-1]
    array_id   = chunk[1][10:-1]
    tft_type = chunk[2][12:-1]
    return [("Timestamp", timestamp), ("Array Serial Number", array_id), ("TFT Type", tft_type)]

'''
Extracts the (key, value) from each chunk in a list of chunks (from the split_file_into_chunks() function).
Does not work on loopback checks in older files, and doesn't extract the header information (in first chunk)
Parameters:
    chunks: a list of raw text "chunks", which themselves are lists of each line in the chunk
    e.g. [['chunk1_line', 'chunk1_line', 'chunk1_line'], ['chunk2_line', 'chunk2_line', 'chunk2_line']]
    dict: dictionary to lookup the key to, in this case to link to the Google Sheets header
Returns:
    Array with tuples of (Google Sheets header from dictionary, value)
'''
def extract_vals_from_chunks(chunks, dict=DICT_SUMMARY_TO_GSHEETS_KEYWORD):
    out_array = [] # store values here in tuple form
    for chunk in chunks:
        if (len(chunk) > 1):
            str_in_dict_keys = check_str_in_dict_keys(chunk[0])
            if (str_in_dict_keys[0] and "Sensor" in chunk[0] or "Ran" in chunk[0] and len(chunk)>1):
                value = extract_num_from_str(chunk[1])[0] # extracts the first number from the second line of the chunk
                out_array.append((dict[str_in_dict_keys[1]], value))
    return out_array

'''
Extracts loopback values from a list of chunks from the split_file_into_chunks() function
Distinguishes between three types of outputs:
Sensor modules:
- Before October 2024 -- "Loopback 1A/1B resistance: [x]" and "Loopback 2A/2B resistance: [x]" on two lines
- After October 2024 -- Loopbacks printed in two separate chunks
Sensor arrays/backplanes:
- All -- "Loopback 1 resistance: [x]" and "Loopback 2 resistance: [x]" on two lines
Parameters:
    chunks: a list of raw text "chunks", which themselves are lists of each line in the chunk
    e.g. [['chunk1_line', 'chunk1_line', 'chunk1_line'], ['chunk2_line', 'chunk2_line', 'chunk2_line']]
Returns:
    Array with tuples of ("Loopback resistance", value)
'''
def extract_loopbacks_from_chunks(chunks):
    chunk1 = chunks[2]
    chunk2 = chunks[3]
    loopback_one = -1
    loopback_two = -1
    # if chunk1 lines 1 and 2 have "Loopback" in them, parse it one way using only the first chunk
    # if not, parse the loopbacks using both chunk1 and chunk2 (second line of each)
    if ("Loopback" in chunk1[0] and "Loopback" in chunk1[1]):
        loopback_one_arr = extract_num_from_str(chunk1[0])
        loopback_two_arr = extract_num_from_str(chunk1[1])
        if (len(loopback_one_arr) == 1 or len(loopback_two_arr) == 1):
            loopback_one = loopback_one_arr[0]
            loopback_two = loopback_two_arr[0]
        else:
            loopback_one = loopback_one_arr[1]
            loopback_two = loopback_two_arr[1]
    else:
        loopback_one = extract_num_from_str(chunk1[1])[0]
        loopback_two = extract_num_from_str(chunk2[1])[0]
    return [("Loopback One (ohm)", loopback_one), ("Loopback Two (ohm)", loopback_two)]

'''
Extracts the module stage of a sensor module from the given input string
If the sensor module doesn't have a stage, or if it's an array or a backplane,
returns an empty string
Parameters:
    string_in: the string to look through
Outputs:
    Array with tuple of ("Array module stage", stage); stage is empty is not a module/no stage string
'''
def extract_stage_from_serial_number(string_in):
    out = ""
    indices = []
    for i in range(len(string_in)):
        if (string_in[i] == '_'):
            indices.append(i)
    if (len(indices) > 2):
        out = string_in[indices[2]+1:]
    return [("Array Module Stage", out)]

'''
Extracts the assembly type of a sensor (backplane, array, module) from the given input string
Looks it up in a dictionary that's ARRAY_ASSY_TYPES by default
Parameters:
    string_in: the string to look through
Outputs:
    Array with tuple of ("Array type", type)
'''
def extract_type_from_serial_number(string_in, dict=ARRAY_ASSY_TYPES):
    out = ""
    string_segments = list(filter(None, string_in.split("_")))
    return [("Array Type", dict[min(3,len(string_segments))])]

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
    spreadsheet_id : The Google Sheets spreadsheet ID, extracted from the URL (docs.google.com/spreadsheets/d/***)
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
'''
def check_for_duplicate_timestamp(creds, query, search_col='A',
                                  spreadsheet_id=SPREADSHEET_ID, sheet_name=OUT_SHEET_NAME):
    if (type(query) is not str):
        print("ERROR: query is not a string...")
        return False
    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        # Define the range (A1 notation) to append the data at the end of the sheet
        range_name = f'{sheet_name}!' + search_col + ':' + search_col
        result = (
            sheet.values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        values_result = result.get("values", [])
        for value in values_result:
            if (value[0] == query):
                return True
        return False
    except HttpError as err:
        print(err)
        return False

def main():
    # new 1T backplane
    filename = "G:\\Shared drives\\Sensing\\Testing\\Backplanes\\E2408-001-004-C6\\"
    filename += "2024-10-18_11-35-42_E2408-001-004-C6__summary.txt"

    # old 1T module with cap/TFT
    #filename = "G:\\Shared drives\\Sensing\\Testing\\Sensor Modules\\E2421-002-001-D5_T1_S-12\\"
    #filename += "2024-09-24_11-32-10_E2421-002-001-D5_T1_S-12_Post_Flex_Bond_ETest_summary.txt"

    # new 1T module with cap/TFT
    #filename = "G:\\Shared drives\\Sensing\\Testing\\Sensor Modules\\E2421-002-001-D5_T1_S-12\\"
    #filename += "2024-10-18_13-23-37_E2421-002-001-D5_T1_S-12_test_summary.txt"

    # old 3T module
    #filename = "G:\\Shared drives\\Sensing\\Testing\\Sensor Modules\\E2421-002-001-D6_T1_S-13\\"
    #filename += "2024-09-24_11-36-36_E2421-002-001-D6_T1_S-13_Post_Flex_Bond_ETest_summary.txt"

    # new 3T module
    #filename = "G:\\Shared drives\\Sensing\\Testing\\Sensor Modules\\E2421-002-001-D6_T1_S-13\\"
    #filename += "2024-10-16_16-37-20_E2421-002-001-D6_T1_S-13_test_summary.txt"
    
    # Initialize Google Sheets object
    creds = get_creds()
    chunks = split_file_into_chunks(filename)
    header_vals = extract_header_from_chunk(chunks[0])
    array_type = extract_type_from_serial_number(header_vals[1][1])
    stage = extract_stage_from_serial_number(header_vals[1][1])
    loopback_vals = extract_loopbacks_from_chunks(chunks)
    test_vals = extract_vals_from_chunks(chunks)
    
    all_vals = header_vals + array_type + stage + loopback_vals + test_vals
    
    exists_in_sheet = check_for_duplicate_timestamp(creds, header_vals[0][1])
    if (not exists_in_sheet):
        for val in all_vals:
            output_payload_gsheets_dict[val[0]] = val[1]
        output_payload_gsheets = list(output_payload_gsheets_dict.values())
        write_success = write_to_spreadsheet(creds, output_payload_gsheets)
        if (write_success):
            print("Successfully wrote data to Google Sheets!")
        else:
            print("ERROR: Could not write data to Google Sheets")
    else:
        print("Data already exists in the spreadsheet.\n" +
              "Skipping test from array " + header_vals[1][1] + " at time " + header_vals[0][1])

if (__name__ == "__main__"):
    main()