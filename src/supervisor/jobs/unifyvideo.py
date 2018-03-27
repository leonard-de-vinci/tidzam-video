import urllib3
import urllib3.request
import json
import traceback
import threading
import collections
import numpy as np

from worker import Job
from utils.custom_logging import debug,error,warning,ok, _DEBUG_LEVEL
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from jobs.multistreamer import checkStreamerConfigSanity

requests    = collections.deque()
clients     = []
class Unifyvideo(Job):

    def unify(self, parameters):
        try:
            response = self.http.request("GET", parameters["unify"] + '/api/2.0/recording',fields=parameters)
            items = json.loads(response.data.decode('utf8'))
            debug("Connected to " + parameters["unify"] + "("+str(len(items['data']))+" available videos)",1)
        except:
            debug("Unable to connect to " + parameters["unify"],0)
            return None

        return items['data']

    def setup(self, conf):
        self.http   = urllib3.PoolManager()
        self.conf = conf

        # Start web socket server for incoming configuration
        self.thread = threading.Thread(target = start_server, args=(self.conf["port-ws"],))
        self.thread.start()

        # Load the
        for req in conf["streams"]:
            if "unify" in req:
                rsp = self.unify(req)
                if rsp is not None:
                    for r in rsp:
                        if "locked" in req:
                            if req["locked"] == True and r["locked"] == False:
                                continue
                        requests.append({
                                "name":r["meta"]["cameraName"]+"-"+str(r["endTime"]),
                                "url":req["unify"] + '/api/2.0/recording/'+r["_id"]+'/download?apiKey='+req["apiKey"],
                                "startTime":r["startTime"],
                                "endTime":r["endTime"]
                                })
            else:
                requests.append(req)

    def loop(self, data):
        try:
            r = requests.pop()
            
            return r
        except IndexError:
            pass

        return

    def requireData(self):
        return False

    def destroy(self):
        return


# Register all websocket clients
class WSserver(WebSocket):

    def handleMessage(self):
        try:
            if(not checkStreamerConfigSanity(self.data)):
                self.sendMessage({"error":"Bad request", req:self.data})
            else:
                requests.append(json.loads(self.data))
        except:
            debug("Bad configuration recevied on unify websocket" + self.data)
            traceback.extract_stack()


    def handleConnected(self):
        debug(str(self.address) + ' connected on ' + str(self.request.path), 1)
        if self.request.path == '/unify/':
            clients.append(self)

    def handleClose(self):
        debug(str(self.address) + ' closed', 1)
        if self in clients:
            clients.remove(self)

def start_server(port):
    ok("Web Socket server on "+str(port)+" [STARTED]")
    server = SimpleWebSocketServer('', port, WSserver)
    server.serveforever()
