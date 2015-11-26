import argparse
from FxAconnections import Command_Parser
# from FxAconnectionsTCP import Command_Parser
import socket

def argparser():
    """Parse arguments
    Return:
        named tuple of arguments
    """
    parser = argparse.ArgumentParser(description="Set up a file transfer client using Reliable Transfer Protocol")
    parser.add_argument("X", type=int, help="Enter port number for client setup")
    parser.add_argument("A", help="Enter IP of NetEmu")
    parser.add_argument("P", type=int, help="Enter port number of NetEmu")
    return parser.parse_args()

def main():
    args = argparser()
    # try:
        # socket.inet_aton(args.A)
    # s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # s.settimeout(1)
    # parser = Command_Parser(args.X, args.A, args.P, 0, s)
    parser = Command_Parser(args.X, args.A, args.P)
    running = True
    while running:
        cmd = input("Command: ")
        running = parser.parse_command(cmd)
    # except Exception as e:
        # print(e)
if __name__ == '__main__':
    main()
