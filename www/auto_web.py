from miclass import milight
import json
import socket

from flask import Flask, request, render_template
app = Flask(__name__)

host = '127.0.0.1'
port = 4444

@app.route("/")
def index():
    return render_template('index.html',roomlist=['living','living-side','chris', 'keith', 'kitchen'])

@app.route("/room/<roomid>")
def room_menu(roomid):
    return render_template('controls.html',roomid=roomid)

@app.route("/off/<zone>")
def set_off(zone):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host,port))
    s.sendall(json.dumps({"command": "off", "zone": zone, "force": True}))

    response = s.recv(1024)
    s.close()

    return response

@app.route("/on/<zone>")
def set_on(zone):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host,port))
    s.sendall(json.dumps({"command": "on", "zone": zone, "force": True}))

    response = s.recv(1024)
    s.close()

    return response

@app.route("/get/<zone>")
def get_zone(zone):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host,port))
    s.sendall(json.dumps({"command": "get", "zone": zone}))

    response = s.recv(1024)
    s.close()

    return response

@app.route("/set/<zone>/<int:color>")
@app.route("/set/<zone>/-/<int:bright>")
@app.route("/set/<zone>/-/<int:bright>/<int:duration>")
@app.route("/set/<zone>/<int:color>/<int:bright>")
@app.route("/set/<zone>/<int:color>/-/<int:duration>")
@app.route("/set/<zone>/<int:color>/<int:bright>/<int:duration>")
def set_color(zone,color=-10,bright=-10,duration=0):

    if color < 0 or bright < 0:
       s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       s.connect((host,port))

       s.sendall(json.dumps({"command": "get", "zone": zone}))

       status = json.loads(s.recv(1024))

       if color < 0:
          color = status['color']
          if color < 0:
             color = 256
       if bright < 0:
          bright = status['brightness']
          if bright < 2 or bright > 27:
             bright = 10

    #color = int(request.args['color'])
    #brightness = int(request.args['bright'])

       s.close()

    if color > 255:
       color = -1

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host,port))

    message = {"command": "set", "zone": zone, "color": color, "brightness": bright, "force": True}

    if duration > 0:
       message['duration'] = duration

    s.sendall(json.dumps(message))

    response = s.recv(1024)
    s.close()

    return response


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
