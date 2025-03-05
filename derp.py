from test_helper_functions import *

def print_dict(dict_in):
    for key in dict_in:
        print(key + ": " + str(dict_in[key]))

'''
Merges dictionary B into dictionary A, given both dictionaries have the same keys,
and ignores empty keys (None or "")
Intended for combining output dictionaries from multiple test routines
(e.g. cont_1T and cap_1T) to output to Google Drive all at once.
Parameters:
    dict_a: The array to be merged into
    dict_b: The array to merge into dict_a
Returns:
    dict_out: Merged dictionary, or None if both dictionaries' keys aren't exactly the same
'''
def merge_dict_b_into_a(dict_a, dict_b):
    if dict_a.keys() != dict_b.keys():
        print("ERROR: Dictionaries do not have matching keys...")
        return None
    dict_out = dict_a
    for key in dict_out:
        if (dict_b[key] is not None and dict_b[key] != ""):
            dict_out[key] = dict_b[key]
    return dict_out

out_cont_dict = dict()
out_cap_dict = dict()
for key in OUT_COLUMN_FIELDS:
    out_cont_dict[key] = None
    out_cap_dict[key] = None

out_cont_dict["Row to Col (# shorts)"] = 256
#print_dict(out_cont_dict)

out_cap_dict["Cap Col to PZBIAS (# pass)"] = 128
out_cap_dict["Col to PZBIAS with TFT's ON (# shorts)"] = ""
#print_dict(out_cap_dict)

out_dict = merge_dict_b_into_a(out_cont_dict, out_cap_dict)
print_dict(out_dict)

out_dict["Timestamp"] = "Invalid"

creds = get_creds()
output_payload_gsheets = list(out_dict.values())
write_success = write_to_spreadsheet(creds, output_payload_gsheets)
print(write_success)