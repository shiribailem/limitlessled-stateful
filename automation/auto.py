#!/usr/bin/python

import threading
import miclass
from Queue import Queue
import json
import socket
import traceback
import sys
from os.path import exists, expanduser

# Load configuration file

config = None

for filename in [
    "milight.json",
    expanduser("~/.milight/milight.json"),
    "/etc/milight/milight.json"
]:
    if exists(filename):
        # If found, load user config to override defaults
        with open(filename,'r') as file:
            config = json.loads(file.read())
        break

if config is None:
    print("No configuration found")
    exit(1)

class ControlThread(threading.Thread):
    def run(self):
        while True:
            command = self.queue.get()

            if not self.controller.interrupt_q.empty():
                    try:
                            self.controller.interrupt_q.get(False)
                    except:
                            pass

            if command['command'] == 'set':
                if 'color' in command.keys() and 'brightness' in command.keys():
                    self.controller.set_color(command['color'], command['brightness'])
                elif 'color' in command.keys():
                    self.controller.set_color(command['color'])
                elif 'brightness' in command.keys():
                    self.controller.set_brightness(command['brightness'])
                elif 'rgb' in command.keys():
                    self.controller.set_rgb(*command['rgb'])
            elif command['command'] == 'blend':
                if not "rgb" in command.keys():
                    self.controller.blend_color(command['color'], command['brightness'], command['duration'])
                else:
                    self.controller.set_rgb(*command['rgb'], duration=command['duration'])
            elif command['command'] == 'off':
                if 'duration' in command.keys():
                    self.controller.set_off(command['duration'])
                else:
                    self.controller.set_off()
            elif command['command'] == 'on':
                self.controller.turn_on()

#zoneconfig = {'living': {'host': 'milight-hub.foggyminds.net', 'zone': 1, 'subtype': 'rgbw'},
#              'keith': {'host': 'milight-hub.foggyminds.net', 'zone': 2, 'subtype': 'rgbw'},
#              'chris': {'host': 'milight-hub.foggyminds.net', 'zone': 3, 'subtype': 'rgbw'},
#              'living-side': {'host': 'milight-hub.foggyminds.net', 'zone': 4, 'subtype': 'rgbw'},
#              'kitchen': {'host': 'milight-hub.foggyminds.net', 'zone': 1, 'subtype': 'rgb'}
#              }

bridges = [['bridge1', '192.168.0.251', 8899]]

controllers = {}
zones = {}

for bridge in config["bridges"]:
    controllers[bridge['name']] = miclass.Controller(bridge['host'], bridge['port'], refresh=bridge['refresh'])

#zones_handles = {
#    'living': controllers['bridge1'].zones['rgbw'][0],
#    'keith': controllers['bridge1'].zones['rgbw'][1],
#    'chris': controllers['bridge1'].zones['rgbw'][2],
#    'living-side': controllers['bridge1'].zones['rgbw'][3],
#    'kitchen': controllers['bridge1'].zones['rgb']
#}

    for zone in bridge['zones']:
        zones[zone['name']] = ControlThread()
        zones[zone['name']].controller = controllers[bridge['name']].zones[zone['type']][zone['zone'] - 1]
        zones[zone['name']].queue = Queue()
        zones[zone['name']].daemon = True
        zones[zone['name']].start()

#for zone in zoneconfig:
#    controllers[zone] = ControlThread()
#    controllers[zone].controller = miclass.Controller(host=zoneconfig[zone]['host'], zone=zoneconfig[zone]['zone'],
#                                                   subtype=zoneconfig[zone]['subtype'])
#    controllers[zone].queue = Queue()
#    controllers[zone].daemon = True
#    controllers[zone].start()

serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
serversocket.bind(('127.0.0.1', 4444))

while threading.active_count() > 1:
    serversocket.listen(10)
    try:
        (clientsocket, address) = serversocket.accept()

        message = clientsocket.recv(1024)
        print message

        clientsocket.setblocking(0)

        data = json.loads(message)

        if "force" in data:
            if data["force"]:
                if not zones[data['zone']].queue.empty() or zones[data['zone']].controller.running > 0:
                    print "Force requested. Queue contents found, clearing now."
                while not zones[data['zone']].queue.empty():
                    try:
                        zones[data['zone']].queue.get(False)
                    except:
                        print "Queue empty"
                # break
                zones[data['zone']].controller.running = 0
                zones[data['zone']].controller.interrupt_q.put("break")
                print "Queue cleared by force."

        if data['command'] == 'exit':
            clientsocket.sendall(json.dumps({'response': 'ok'}))
            break
        elif data['command'] == 'on':
            if data['zone'] in zones.keys():
                zones[data['zone']].queue.put({'command': 'on'})
                clientsocket.sendall(json.dumps({'response': 'ok'}))
            else:
                clientsocket.sendall(json.dumps({'response': 'fail', 'message': 'invalid zone'}))
        elif data['command'] == 'off':
            if data['zone'] in zones.keys():
                if 'duration' not in data.keys():
                    data['duration'] = 1
                zones[data['zone']].queue.put({'command': 'off', 'duration': data['duration']})
                clientsocket.sendall(json.dumps({'response': 'ok'}))
            else:
                clientsocket.sendall(json.dumps({'response': 'fail', 'message': 'invalid zone'}))
        elif data['command'] == 'set':
            if data['zone'] in zones.keys():
                message = {'command': 'set'}
                if 'duration' in data.keys():
                    message['duration'] = data['duration']
                    message['command'] = 'blend'
                if 'color' in data.keys():
                    message['color'] = data['color']
                elif 'rgb' in data.keys():
                    message['rgb'] = data['rgb']
                else:
                    message['color'] = zones[data['zone']].controller.color
                if 'brightness' in data.keys():
                    message['brightness'] = data['brightness']
                else:
                    message['brightness'] = zones[data['zone']].controller.brightness

                if 'color' in message.keys() or 'rgb' in message.keys() or 'brightness' in message.keys():
                    zones[data['zone']].queue.put(message)
                else:
                    clientsocket.sendall(json.dumps({'response': 'fail', 'message': 'invalid command - missing settings'}))
                clientsocket.sendall(json.dumps({'response': 'ok'}))
            else:
                clientsocket.sendall(json.dumps({'response': 'fail', 'message': 'invalid zone'}))
        elif data['command'] == 'get':
            if data['zone'] in zones.keys():
                controller = zones[data['zone']].controller

                reply = {'color': controller.color, 'brightness': controller.brightness,
                         'on': controller.on, 'rgb': controller.get_rgb()}

                clientsocket.sendall(json.dumps(reply))
            else:
                clientsocket.sendall(json.dumps({'response': 'fail', 'message': 'invalid zone'}))

    except KeyboardInterrupt:
        break

    except:
        print "Message error."
        traceback.print_exc(file=sys.stdout)

    clientsocket.close()
