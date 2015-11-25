import RxP
import argparse
from FxA-connections import *

def argparser():
    """Parse arguments
    Return:
        named tuple of arguments
    """
    parser = argparse.ArgumentParser(description="Set up a file transfer client using Reliable Transfer Protocol")
    parser.add_argument("X", type=int, help="Enter port number for client setup")
    parser.add_argument("A", type=int, help="Enter IP of NetEmu")
    parser.add_argument("P", type=int, help="Enter port number of NetEmu")
    return parser.parse_args()

def main():
    args = argparser()
    parser = Command_Parser(args.X, args.A, args.P)
    while True:
        cmd = input("Command: ")
        parser.parse_command(cmd)
if __name__ == '__main__':
    main()
