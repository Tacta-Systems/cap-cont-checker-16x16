import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import os
import glob

path = "G:\\Shared drives\\Sensing\\Testing\\"

array_types = {
    0: "Backplanes",
    1: "Sensor Arrays\\16x16",
    2: "Sensor Modules"
}
array_type_raw = 0
while True:
    try:
        array_type_raw = int(input("Please enter array type--\n- 0 for backplanes\n- 1 for sensor arrays\n- 2 for sensor modules: "))
    except ValueError:
        print("Sorry, please enter a numerical value")
        continue
    if (array_type_raw not in list(array_types.keys())):
        print("Sorry, please enter a valid response")
        continue
    else:
        break
array_type = array_types[array_type_raw]
path += array_type + "\\"

dut_id_input = ""
while True:
    try:
        dut_id_input = input("Please enter the array ID (e.g. E2408-001-2-E2_T2): ")
    except ValueError:
        print("Sorry, array ID can't be blank")
        continue
    if (len(dut_id_input) < 1):
        print("Sorry, array ID can't be blank")
        continue
    if (not os.path.exists(path + dut_id_input)):
        print("This file does not exist. Please try again.")
    else:
        break

path += dut_id_input + "\\"

filenames_raw = glob.glob(path + '*summary.txt')

def get_timestamp_raw(file_name):
    return file_name.split("\\")[-1][:19]

def get_timestamp_truncated(file_name):
    return file_name[:19]

filenames_raw = list(sorted(filenames_raw, key=get_timestamp_raw))

filenames = list({x.replace(path, '') for x in filenames_raw})
filenames = list(sorted(filenames, key=get_timestamp_truncated))

print("")
for i in range(len(filenames)):
    print(str(i) + ": " + filenames[i])
print("")

file_one_index = -1
while True:
    try:
        file_one_index = int(input("Please select file 1 to compare: "))
    except ValueError:
        print("Error: please enter a number between 0 and " + str(len(filenames)-1))
        continue
    if (file_one_index not in range(0, len(filenames))):
        print("Error: please enter a number between 0 and " + str(len(filenames)-1))
        continue
    else:
        break

file_two_index = -1
while True:
    try:
        file_two_index = int(input("Please select file 2 to compare: "))
    except ValueError:
        print("Error: please enter a number between 0 and " + str(len(filenames)-1))
        continue
    if (file_two_index not in range(0, len(filenames))):
        print("Error: please enter a number between 0 and " + str(len(filenames)-1))
        continue
    if (file_two_index == file_one_index):
        print("Error: File already selected, please select a different file")
        continue
    else:
        break
file_one = filenames_raw[file_one_index]
file_two = filenames_raw[file_two_index]

def truncate_to_keyword(string, keyword):
    if keyword in string:
        index_val = string.index(keyword)
        return string[:index_val]
    else:
        return string

with open(file_one) as f1, open(file_two) as f2:
    f1_list = f1.readlines()
    f2_list = f2.readlines()
    f1_chunk_indices = []
    f2_chunk_indices = []
    f1_chunk_tuples = []
    f2_chunk_tuples = []
    f1_chunks_raw = []
    f2_chunks_raw = []
    f1_chunks = []
    f2_chunks = []
    for i in range(len(f1_list)):
        if f1_list[i] in ['\n', '\r\n']:
            f1_chunk_indices.append(i)
    for i in range(1, len(f1_chunk_indices)):
        f1_chunk_tuples.append((f1_chunk_indices[i-1], f1_chunk_indices[i]))
    for tuple in f1_chunk_tuples:
        f1_chunks_raw.append(f1_list[tuple[0]:tuple[1]][1:])
    for chunk in f1_chunks_raw:
        chunk_output = []
        for string in chunk:
            if ("If there are shorts" not in string and "Loopback" not in string):
                if ("array" in string):
                    string = truncate_to_keyword(string, "in")
                chunk_output.append(string)
        if (len(chunk_output) > 0):
            f1_chunks.append(chunk_output)

    print("")
    for i in range(len(f2_list)):
        if f2_list[i] in ['\n', '\r\n']:
            f2_chunk_indices.append(i)
    for i in range(1, len(f2_chunk_indices)):
        f2_chunk_tuples.append((f2_chunk_indices[i-1], f2_chunk_indices[i]))
    for tuple in f2_chunk_tuples:
        f2_chunks_raw.append(f2_list[tuple[0]:tuple[1]][1:])
    for chunk in f2_chunks_raw:
        chunk_output = []
        for string in chunk:
            if ("If there are shorts" not in string and "Loopback" not in string):
                if ("array" in string):
                    string = truncate_to_keyword(string, "in")
                chunk_output.append(string)
        if (len(chunk_output) > 0):
            f2_chunks.append(chunk_output)

    if (len(f1_chunks) == len(f2_chunks)):
        num_diffs = 0
        for i in range(len(f1_chunks)):
            if (f1_chunks[i] != f2_chunks[i]):
                print("Difference detected:\nFile " + filenames[file_one_index] + ":")
                for chunk in f1_chunks[i]:
                    print(chunk, end="")
                print("")
                print("File " + filenames[file_two_index] + ":")
                for chunk in f2_chunks[i]:
                    print(chunk, end="")
                num_diffs += 1
            print("\n")
        print("There were " + str(num_diffs) + " differences detected")
    elif (len(f1_chunks) < len(f2_chunks)):
        num_diffs = 0
        for i in range(len(f1_chunks)):
            if (f1_chunks[i] != f2_chunks[i]):
                print("Difference detected:\nFile " + filenames[file_one_index] + ":")
                for chunk in f1_chunks[i]:
                    print(chunk, end="")
                print("")                    
                print("File " + filenames[file_two_index] + ":")
                for chunk in f2_chunks[i]:
                    print(chunk, end="")
                num_diffs += 1
            print("\n")
        print("There were " + str(num_diffs) + " differences detected")
    elif (len(f1_chunks) > len(f2_chunks)):
        num_diffs = 0
        for i in range(len(f2_chunks)):
            if (f1_chunks[i] != f2_chunks[i]):
                print("Difference detected:\nFile " + filenames[file_one_index] + ":")
                for chunk in f1_chunks[i]:
                    print(chunk, end="")
                print("")                    
                print("File " + filenames[file_two_index] + ":")
                for chunk in f2_chunks[i]:
                    print(chunk, end="")
                num_diffs += 1
            print("\n")
        print("There were " + str(num_diffs) + " differences detected")
    else:
        print("ERROR: File lengths are mismatched")