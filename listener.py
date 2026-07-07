import socket
import logging
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('C:\Scripts\Listeners\MagicPacketHandler\output.log'),
        logging.StreamHandler(),
    ]
)

LISTEN_PORT = 40002
QUEEN_IP = '192.168.0.247'


def parse_magic_packet(data):
    if len(data) < 102:
        return None, "Packet too short to be a valid magic packet"
    if data[:6] != b'\xff\xff\xff\xff\xff\xff':
        return None, "Missing sync stream (FF FF FF FF FF FF)"
    mac_bytes = data[6:12]
    for i in range(16):
        if data[6 + i * 6:12 + i * 6] != mac_bytes:
            return None, "MAC repetitions inconsistent — not a valid magic packet"
    mac = ':'.join(f'{b:02x}' for b in mac_bytes)
    return mac, None


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', LISTEN_PORT))

logging.info(f"Shutdown listener started — listening on UDP port {LISTEN_PORT}")
logging.info(f"Accepting shutdown signals from Queen only ({QUEEN_IP})")

while True:
    data, addr = sock.recvfrom(1024)
    logging.info(f"[RECEIVED] Packet from {addr[0]}:{addr[1]} — {len(data)} bytes")

    if addr[0] != QUEEN_IP:
        logging.warning(f"[REJECTED] Packet from unknown source {addr[0]} — only accepting from Queen ({QUEEN_IP})")
        continue

    mac, err = parse_magic_packet(data)
    if err:
        logging.warning(f"[INVALID]  {err} — dropping")
        continue

    logging.info(f"[VALID]    Magic packet verified — target MAC: {mac}")
    logging.info(f"[SHUTDOWN] Shutdown command received from Queen")
    subprocess.run(['shutdown', '/s', '/t', '5', '/c', 'Remote shutdown triggered'])
    logging.info(f"[SHUTDOWN] Shutdown initiated")
