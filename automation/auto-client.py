#!/usr/bin/python

import json
import socket
import argparse
import sys

HOST = "127.0.0.1"
PORT = 4444


def send_command(command, verbose=False):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    if verbose:
        print "sent: " + json.dumps(command)

    s.sendall(json.dumps(command))
    response = s.recv(1024)
    s.close()

    if verbose:
        print "response: " + response

    try:
        return json.loads(response)
    except:
        return {}


parser = argparse.ArgumentParser()

parser.add_argument('zone', action='store')
gargcolor = parser.add_mutually_exclusive_group()
gargcolor.add_argument('--color', default=None, action="store", type=int)
gargcolor.add_argument('--white', action="store_const", const=True, default=False)
parser.add_argument('--brightness', default=None, action="store", type=int)
parser.add_argument('--noon', action="store_const", const=True, default=False)
parser.add_argument('--force', action="store_const", const=True, default=False)
parser.add_argument('--on', action="store_const", const=True, default=False)
parser.add_argument('--off', action="store_const", const=True, default=False)
parser.add_argument('--duration', default=0, action="store", type=int)
parser.add_argument('--verbose', action="store_const", const=True, default=False)

arguments = parser.parse_args()

status = send_command({"command": "get", "zone": arguments.zone}, arguments.verbose)

if arguments.noon:
    if not status["on"]:
        if arguments.verbose:
            print "no-on: Zone is currently off, exiting"
        sys.exit()

if arguments.on:
    if not status["on"]:
        send_command({"command": "on", "zone": arguments.zone, "force": arguments.force}, arguments.verbose)
    elif arguments.verbose:
        print "on: Zone is already on"

if arguments.off:
    if status["on"]:
        send_command({"command": "off", "zone": arguments.zone, "force": arguments.force}, arguments.verbose)
    elif arguments.verbose:
        print "off: Zone is already off"

if arguments.brightness is not None and (arguments.color is None or not arguments.white):
    send_command({"command": "set", "brightness": int(arguments.brightness), "zone": arguments.zone,
                  "duration": arguments.duration, "force": arguments.force}, arguments.verbose)

if arguments.color is not None and arguments.brightness is None:
    send_command({"command": "set", "color": int(arguments.color), "zone": arguments.zone,
                  "duration": arguments.duration, "force": arguments.force}, arguments.verbose)

if arguments.white and arguments.brightness is None:
    status["color"] = -1
    send_command({"command": "set", "color": -1, "zone": arguments.zone,
                  "duration": arguments.duration, "force": arguments.force}, arguments.verbose)

if (arguments.color is not None or arguments.white) and arguments.brightness is not None:
    send_command(
        {"command": "set", "color": status["color"], "brightness": status["brightness"], "duration": arguments.duration,
         "zone": arguments.zone, "force": arguments.force}, arguments.verbose)
