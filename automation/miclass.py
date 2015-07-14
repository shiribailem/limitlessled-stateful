from datetime import datetime, timedelta
from time import sleep
from Queue import Queue
import threading
import socket

verbose = True

message_queue = Queue()

rgbw_zone_list = [0x42,
                0x45,
                0x47,
                0x49,
                0x4B,
                ]

rgbw_zone_white_list = [0xC2,
                0xC5,
                0xC7,
                0xC9,
                0xCB
                ]

white_zone_on_list = [0x35,
                0x38,
                0x3D,
                0x37,
                0x32
                ]

white_zone_off_list = [0x39,
                0x3B,
                0x33,
                0x3A,
                0x36
                ]

class Zone:
    def __init__(self, host, zone, subtype, port=8899, queue=None):
        self.host = host
        self.zone = zone
        self.port = port
        self.subtype = subtype
        self.queue = queue

        self.running = 0

        self.color = -1.0
        self.brightness = 1.0
        self.on = False

        self.interrupt_q = Queue()

    def __command_dict(self):
        return {"host": self.host, "port": self.port, "zone": self.zone, "type": self.subtype}

    def turn_on(self):
        message = self.__command_dict()
        message["command"] = "on"
        self.queue.put(message)
        self.on = True
        return True

    def set_color(self, color, brightness=None, refresh=True):
        if not self.on:
            self.on = True
            self.turn_on()

        if not float(color) == self.color or refresh:
            if color == -1:
                message = self.__command_dict()
                if not self.subtype == "rgb" or (not self.color == -1):
                    message["command"] = "white"
                    self.queue.put(message)
            else:
                message = self.__command_dict()
                message["command"] = "color"
                message["color"] = int(color)
                self.queue.put(message)

        if not brightness is None:
            self.set_brightness(brightness, refresh)

        self.color = float(color)

        return True

    def set_brightness(self, brightness, refresh=True):
        if not float(brightness) == self.brightness or refresh:
            message = self.__command_dict()
            message["command"] = "bright"
            message["bright"] = int(brightness)
            self.queue.put(message)
            self.brightness = float(brightness)
        return True

    def refresh(self):
        if self.on:
            self.set_color(self.color,self.brightness,refresh=True)
        else:
            self.set_off()

    def blend_color(self, color, brightness, duration=10):
        if duration == 0:
            duration = 1

            if not self.on:
                self.set_color(color,2)

        if self.on and int(round(self.color)) == int(round(color)) and int(round(self.brightness)) == int(round(brightness)):
            return 0

        if self.color == -1 and color >= 0:
            if color == 142 and brightness == 27:
                return self.blend_from_white(duration)
            duration -= self.blend_from_white(duration/2)

        elif self.color >= 0 and color == -1:
            if brightness == 10:
                return self.blend_to_white(duration)
            duration -= self.blend_to_white(duration/2)

        if (self.color >= 0 and color >= 0) or (self.color == -1 and self.color == -1):
            cdifference = self.color - color

            if abs(cdifference) > 128:
                if cdifference > 0:
                    cdifference = self.color - (color + 255)
                else:
                    cdifference = self.color + (255 - color)

            bdifference = self.brightness - brightness

            if abs(cdifference) >= abs(bdifference):
                steps = abs(cdifference)
            else:
                steps = abs(bdifference)

            if steps == 0:
                tinc = 1
            else:
                tinc = float(duration) / float(steps)

            cinc = float(cdifference) / (duration / tinc)
            binc = float(bdifference) / (duration / tinc)

            self.running += 1

            while not int(round(self.brightness)) == int(round(brightness)) or not int(round(self.color)) == int(round(color)):
                if self.running < 1:
                    break                

                starttime = datetime.now()
                if not int(round(self.brightness)) == int(round(brightness)):
                    newbrightness = self.brightness - binc
                else:
                    newbrightness = round(brightness)

                if binc < 0:
                    if newbrightness > brightness:
                        newbrightness = round(brightness)
                else:
                    if newbrightness < brightness:
                        newbrightness = round(brightness)

                if not int(round(self.color)) == int(round(color)):
                    newcolor = self.color - cinc
                else:
                    newcolor = round(color)

                if color > -1:
                    if newcolor > 255:
                        newcolor = newcolor - 255.0
                    elif newcolor < 0 and not color == 0:
                        newcolor = 255.0 + newcolor
                    elif newcolor < 0 and color == 0:
                        color = 0

                    cdifference = self.color - color

                    if abs(cdifference) < 128:
                        if cinc < 0:
                            if newcolor > color:
                                newcolor = color
                        else:
                            if newcolor < color:
                                newcolor = color

                self.set_color(newcolor,newbrightness)
                delta = datetime.now() - starttime

                if not delta.total_seconds() > tinc:
                    try:
                        self.interrupt_q.get(True, tinc - delta.total_seconds())
                    except:
                        pass

        if self.running > 0:
            self.running -= 1

        return duration

    def set_off(self,duration=5):
        if duration > 0:
            self.blend_color(self.color,2,duration)
        message = self.__command_dict()
        message["command"] = "off"
        self.queue.put(message)
        self.on = False

    def blend_to_white(self, duration):
        if self.color == -1:
            return 0

        whitematch = 2
        brightness = 6

        if self.brightness > 6:
            whitematch = float(10.0/27.0) * self.brightness
            brightness = self.brightness

        self.running += 1
        self.blend_color(142, brightness,duration)

        if self.running > 0:
            self.set_color(-1, whitematch)
            self.running -= 1

        return duration

    def blend_from_white(self, duration):
        if self.color >= 0:
            return 0

        if self.brightness < 10:
            self.set_color(142,2.7 * self.brightness)
            return 0

        self.running += 1
        self.blend_color(-1,10,duration)

        if self.running > 0:
            self.set_color(142,27)
            self.running -= 1

        return duration

class message_handler(threading.Thread):
    def run(self):
        while True:
            command = None
            try:
                command = self.queue.get(True,30)
            except:
                if verbose:
                    print "Refresh"
                for item in self.parent.zones['rgbw']:
                    item.refresh()
                for item in self.parent.zones['white']:
                    item.refresh()
                self.parent.zones['rgb'].refresh()

            if command is not None:
                if command["command"] == "on":
                    self.parent.__on__(command["type"], command["zone"])
                elif command["command"] == "off":
                    self.parent.off(command["type"], command["zone"])
                elif command["command"] == "color":
                    self.parent.set_color(command["type"], command["zone"], command["color"])
                elif command["command"] == "bright":
                    self.parent.set_brightness(command["type"], command["zone"], command["bright"])
                elif command["command"] == "white":
                    self.parent.set_white(command["type"], command["zone"])
                else:
                    if verbose:
                        print "Invalid Command"
                if verbose:
                    print "Processed:"
                    print command

class Controller:
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.cursor = ('white',0)
        self.control_queue = Queue()
        self.last_refresh = datetime.now()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.zones = {'rgbw': [], 'rgb': None, 'white': []}

        for i in range(1,5):
            self.zones['rgbw'].append(Zone(self.host,i,'rgbw',self.port, self.control_queue))
            self.zones['white'].append(Zone(self.host,i,'white',self.port, self.control_queue))

        self.zones['rgb'] = Zone(self.host,0,'rgb',self.port, self.control_queue)

        self.__handler = message_handler()
        self.__handler.daemon = True
        self.__handler.queue = self.control_queue
        self.__handler.parent = self
        self.__handler.start()

    def __message__(self, part1, part2=0x00, repeat=3):
        for i in range(0, repeat):
            message = bytearray([part1, part2, 0x55])

        self.sock.sendto(message, (self.host, self.port))

    def __on__(self, subtype, zone):
        if subtype == "rgb":
            self.__message__(0x22)
        elif subtype == "rgbw":
            self.__message__(rgbw_zone_list[zone])
        sleep(0.1)

        self.cursor = (subtype, zone)

    def off(self, subtype, zone):
        for i in range(1,3):
            if subtype == "rgb":
                self.__message__(0x21)
            elif subtype == "rgbw":
                self.__message__(rgbw_zone_list[zone]+1)

        self.cursor = (subtype, zone)

    def set_white(self, subtype, zone):
        if not (self.cursor[0] == subtype and self.cursor[1] == zone) and not subtype == 'rgb':
            self.__on__(subtype, zone)

        if subtype == "rgbw":
            self.__message__(rgbw_zone_white_list[zone])
        elif subtype == "rgb":
            self.__message__(0x27)

    def set_color(self, subtype, zone, color):
        if not (self.cursor[0] == subtype and self.cursor[1] == zone) and not subtype == 'rgb':
            self.__on__(subtype, zone)

        if subtype == "rgbw":
            self.__message__(0x40, color)
        elif subtype == "rgb":
            self.__message__(0x20, color)

    def set_brightness(self, subtype, zone, brightness):
        if not (self.cursor[0] == subtype and self.cursor[1] == zone) and not subtype == 'rgb':
            self.__on__(subtype, zone)

        if subtype == "rgbw":
            self.__message__(0x4E, brightness)

    def raise_brightness(self, subtype, zone, brightness):
        if not (self.cursor[0] == subtype and self.cursor[1] == zone) and not subtype == 'rgb':
            self.__on__(subtype, zone)

        if subtype == "white":
            self.__message__(0x3C)
        elif subtype == "rgb":
            self.__message__(0x23)

    def lower_brightness(self, subtype, zone, brightness):
        if not (self.cursor[0] == subtype and self.cursor[1] == zone) and not subtype == 'rgb':
            self.__on__(subtype, zone)

        if subtype == "white":
            self.__message__(0x34)
        elif subtype == "rgb":
            self.__message__(0x24)