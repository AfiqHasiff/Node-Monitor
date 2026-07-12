import socket
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('C:\\Relays\\output.log'),
        logging.StreamHandler(),
    ]
)

WAKE_PORT = 8
SHUTDOWN_PORT = 9
BROADCAST_IP = '192.168.0.255'
BROADCAST_PORT = 7          # target node's WOL listener port
WORKER_IP = '192.168.0.192'
WORKER_IP_SHUTDOWN_PORT = 40002


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


def handle_wake():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', WAKE_PORT))

    broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    logging.info(f"[WAKE]     Listening on UDP port {WAKE_PORT}")

    while True:
        data, addr = sock.recvfrom(1024)
        logging.info(f"[WAKE]     [RECEIVED] Packet from {addr[0]}:{addr[1]} — {len(data)} bytes")

        mac, err = parse_magic_packet(data)
        if err:
            logging.warning(f"[WAKE]     [INVALID]  {err} — dropping")
            continue

        logging.info(f"[WAKE]     [VALID]    Magic packet verified — target MAC: {mac}")
        logging.info(f"[WAKE]     [SENDING]  Broadcasting to {BROADCAST_IP}:{BROADCAST_PORT}...")
        broadcast_sock.sendto(data, (BROADCAST_IP, BROADCAST_PORT))
        logging.info(f"[WAKE]     [DONE]     Magic packet rebroadcast successfully")


def handle_shutdown():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', SHUTDOWN_PORT))

    forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    logging.info(f"[SHUTDOWN] Listening on UDP port {SHUTDOWN_PORT}")

    while True:
        data, addr = sock.recvfrom(1024)
        logging.info(f"[SHUTDOWN] [RECEIVED] Packet from {addr[0]}:{addr[1]} — {len(data)} bytes")

        mac, err = parse_magic_packet(data)
        if err:
            logging.warning(f"[SHUTDOWN] [INVALID]  {err} — dropping")
            continue

        logging.info(f"[SHUTDOWN] [VALID]    Magic packet verified — target MAC: {mac}")
        logging.info(f"[SHUTDOWN] [SENDING]  Forwarding shutdown signal to {WORKER_IP}:{WORKER_IP_SHUTDOWN_PORT}...")
        forward_sock.sendto(data, (WORKER_IP, WORKER_IP_SHUTDOWN_PORT))
        logging.info(f"[SHUTDOWN] [DONE]     Shutdown signal forwarded to target node")


logging.info("WOL relay starting...")

wake_thread = threading.Thread(target=handle_wake, daemon=True)
shutdown_thread = threading.Thread(target=handle_shutdown, daemon=True)

wake_thread.start()
shutdown_thread.start()

logging.info("WOL relay running — wake on port 8, shutdown relay on port 9")

wake_thread.join()
shutdown_thread.join()
