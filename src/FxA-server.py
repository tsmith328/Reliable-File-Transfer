import RxP
import argparse
from FxAconnections import Command_Parser

def argparser():
    """Parse arguments
    Return:
        named tuple of arguments
    """
    parser = argparse.ArgumentParser(description="Set up a file transfer server using Reliable Transfer Protocol")
    parser.add_argument("X", type=int, help="Enter port number for server setup")
    parser.add_argument("A", help="Enter IP of NetEmu")
    parser.add_argument("P", type=int, help="Enter port number of NetEmu")
    return parser.parse_args()

def main():
    args = argparser()
    print("Listening for connections...")
    conn = RxP.accept()
    parser = Command_Parser(args.X, args.A, args.P, conn)
    print("Connection established!")
    running = True
    while running:
        cmd = input("Command: ")
        running = parser.parse_command(cmd)

if __name__ == '__main__':
    main()
