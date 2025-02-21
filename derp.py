from derp_sub import *
def main():
    try:
        while(True):
            test()
    except KeyboardInterrupt:
        print("Keyboard exception at derp")
        pass


if (__name__ == "__main__"):
    main()