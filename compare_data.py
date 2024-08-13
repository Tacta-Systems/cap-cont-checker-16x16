import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

path = "G:\\Shared drives\\Engineering\\Projects\\Testing\\16x16_Array_E_Test\\Phase_1EFG_Array\\"

onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]

index = -1
while True:
    try:
        for i in range(len(onlyfiles)):
            print("- " + str(i) + " for " + onlyfiles[i])
        index = int(input("Please select file 1: "))
    except ValueError:
        print("Sorry, please select a valid file number between 0 and " + str(len(onlyfiles)-1))
        continue
    if (index > (len(onlyfiles)-1) or index < 0):
        print("Sorry, please select a valid test between 0 and " + str(len(onlyfiles)-1))
        continue
    else:
        break

compare_path_1 = path + onlyfiles[index]

while True:
    try:
        for i in range(len(onlyfiles)):
            print("- " + str(i) + " for " + onlyfiles[i])
        index = int(input("Please select file 2: "))
    except ValueError:
        print("Sorry, please select a valid file number between 0 and " + str(len(onlyfiles)-1))
        continue
    if (index > (len(onlyfiles)-1) or index < 0):
        print("Sorry, please select a valid test between 0 and " + str(len(onlyfiles)-1))
        continue
    else:
        break

compare_path_2 = path + onlyfiles[index]
compare_cols = ["Resistance (ohm)"]

compare_1 = pd.read_csv(compare_path_1)
compare_2 = pd.read_csv(compare_path_2)

compare_1 = compare_1.values
compare_2 = compare_2.values

if (compare_1.shape != compare_2.shape):
    print("ERROR: Files must be from the same test type/have matching dimensions!")
    exit()

out = compare_1

if (np.array_equal(compare_1, compare_2)):
    print("Arrays are equal!")
else:
    diffs = []
    for i in range(out.shape[0]):
        if (compare_1[i][2] != compare_2[i][2]):
            if ("pzbias" in compare_path_1):
                diffs.append((out[i][1], "1 greater" if compare_1[i][2] > compare_2[i][2] else "2 greater"))
            else:
                diffs.append((out[i][0], out[i][1], "1 greater" if compare_1[i][2] > compare_2[i][2] else "2 greater"))
    print("Differences: ")
    for diff in diffs:
        print(diff)