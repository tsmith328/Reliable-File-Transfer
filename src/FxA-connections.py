import threading
import RxP

#Endpoint types
CLIENT = 0
SERVER = 1

class Command_Parser(object):
    def __init__(self, X, A, P, conn=None):
        self.type = SERVER if conn else CLIENT
        self.X = X
        self.P = P
        self.A = A
        self.conn = conn

    def parse_command(self, inp):
        inp = inp.split(' ')
        if len(inp) > 2:
            print("Invalid syntax")
        cmd = inp[0].lower()
        param = inp[1]
        if self.type == CLIENT:
            cmds = ["get", "post", "connect", "window", "disconnect"]
            if cmd != "connect" and not self.conn:
                print("You need to connect first!")
            elif cmd == connect:
                print("Connecting...")
                self.conn = RxP.connect((A, P), X)
                if self.conn:
                    print("Connected!")
                else:
                    print("Connection Failed")
            elif cmd == "window":
                try:
                    win = int(param)
                    self.conn.setWindow(win)
                    print("Window set to: " + param)
                except:
                    print("Invalid window size!")
            elif cmd == "disconnect":
                print("Attempting to close the connection")
                self.conn.close()
                print("Connection closed")
            elif cmd == "get" or cmd == "post":
                print(cmd + " for file: " + param)
                msg = cmd + " " + param
                #spawn thread for sending
            else:
                print("Invalid command: " + cmd)
                print("Valid commands: ")
                for c in cmds:
                    print(c, end=' ')
                print("")
        elif self.type == SERVER:
            cmds = ["window", "terminate"]
            if cmd == "window":
                try:
                    win = int(param)
                    self.conn.setWindow(win)
                    print("Window set to: " + param)
                except:
                    print("Invalid window size!")
            elif cmd == "terminate":
                print("Attempting to close the connection")
                self.conn.close()
                print("Connection closed")

class server_thread(threading.thread):
    def __init__(self):
        
