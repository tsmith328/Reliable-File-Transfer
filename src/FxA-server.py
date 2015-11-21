#import RxP
import argparse

def argparser():
    """Parse arguments
    Return:
        named tuple of arguments
    """
    parser = argparse.ArgumentParser(description="Set up a file transfer server using Reliable Transfer Protocol")
    parser.add_argument("X", type=int, help="Enter port number for server setup")
    parser.add_argument("A", type=int, help="Enter IP of NetEmu")
    parser.add_argument("P", type=int, help="Enter port number of NetEmu")
    return parser.parse_args()

def main():
    args = argparser()
    while True:
        cmd = input("Command: ")

if __name__ == '__main__':
    main()
