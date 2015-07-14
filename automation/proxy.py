import socket

UDP_IP = '192.168.0.255' # Leave empty for Broadcast support
LED_PORT = 48899

sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
sock.bind((UDP_IP, LED_PORT))

RETURN = "192.168.0.40,d8fc93a9172b,"

while True:
	data, addr = sock.recvfrom(64)
	print addr
	print data

	sock.sendto(unicode(RETURN),addr)
