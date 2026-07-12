"""
Packet handler integration — sender and receiver logic run as daemon threads.

Sender: relays incoming WOL and shutdown magic packets to the target node.
Receiver: listens for shutdown magic packets; fires Turned On alert on start,
          Turned Off alert on valid packet, then triggers system shutdown.
"""

import asyncio
import socket
import subprocess
import threading
from typing import Callable, Awaitable

from agent.logger import make_packet_handler_logger


def _parse_magic_packet(data: bytes) -> tuple[str | None, str | None]:
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


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------

def start_sender(cfg: dict) -> None:
    """Start wake and shutdown relay threads. Non-blocking."""
    log = make_packet_handler_logger("packet_sender")

    wake_port: int = cfg["wake_listen_port"]
    shutdown_port: int = cfg["shutdown_listen_port"]
    target_ip: str = cfg["target_ip"]
    target_shutdown_port: int = cfg["target_shutdown_port"]
    broadcast_ip: str = cfg["broadcast_ip"]
    broadcast_port: int = cfg["broadcast_port"]

    def _handle_wake() -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', wake_port))

        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        log.info(f"[WAKE]     Listening on UDP port {wake_port}")

        while True:
            data, addr = sock.recvfrom(1024)
            log.info(f"[WAKE]     [RECEIVED] Packet from {addr[0]}:{addr[1]} — {len(data)} bytes")

            mac, err = _parse_magic_packet(data)
            if err:
                log.warning(f"[WAKE]     [INVALID]  {err} — dropping")
                continue

            log.info(f"[WAKE]     [VALID]    Magic packet verified — target MAC: {mac}")
            log.info(f"[WAKE]     [SENDING]  Broadcasting to {broadcast_ip}:{broadcast_port}...")
            broadcast_sock.sendto(data, (broadcast_ip, broadcast_port))
            log.info(f"[WAKE]     [DONE]     Magic packet rebroadcast successfully")

    def _handle_shutdown() -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', shutdown_port))

        forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        log.info(f"[SHUTDOWN] Listening on UDP port {shutdown_port}")

        while True:
            data, addr = sock.recvfrom(1024)
            log.info(f"[SHUTDOWN] [RECEIVED] Packet from {addr[0]}:{addr[1]} — {len(data)} bytes")

            mac, err = _parse_magic_packet(data)
            if err:
                log.warning(f"[SHUTDOWN] [INVALID]  {err} — dropping")
                continue

            log.info(f"[SHUTDOWN] [VALID]    Magic packet verified — target MAC: {mac}")
            log.info(f"[SHUTDOWN] [SENDING]  Forwarding shutdown signal to {target_ip}:{target_shutdown_port}...")
            forward_sock.sendto(data, (target_ip, target_shutdown_port))
            log.info(f"[SHUTDOWN] [DONE]     Shutdown signal forwarded to target node")

    log.info("Packet sender starting...")
    threading.Thread(target=_handle_wake, daemon=True, name="packet-sender-wake").start()
    threading.Thread(target=_handle_shutdown, daemon=True, name="packet-sender-shutdown").start()
    log.info(f"Packet sender running — wake on port {wake_port}, shutdown relay on port {shutdown_port}")


# ---------------------------------------------------------------------------
# Receiver
# ---------------------------------------------------------------------------

ActionAlertCallback = Callable[[str], Awaitable[None]]


def start_receiver(
    cfg: dict,
    loop: asyncio.AbstractEventLoop,
    action_alert_cb: ActionAlertCallback,
) -> None:
    """
    Start the shutdown receiver thread and immediately fires the Turned On alert.
    When a valid shutdown packet arrives from the authorised sender, fires the
    Turned Off alert then executes system shutdown. Non-blocking.
    """
    log = make_packet_handler_logger("packet_receiver")

    listen_port: int = cfg["listen_port"]
    sender_ip: str = cfg["sender_ip"]
    node_ip: str = cfg["node_ip"]
    node_mac: str = cfg["node_mac"]

    def _fire(action: str) -> None:
        asyncio.run_coroutine_threadsafe(action_alert_cb(action), loop)

    def _listen() -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', listen_port))

        log.info(f"Shutdown listener started — listening on UDP port {listen_port}")
        log.info(f"Node: {node_ip} ({node_mac}) — accepting signals from {sender_ip}")

        while True:
            data, addr = sock.recvfrom(1024)
            log.info(f"[RECEIVED] Packet from {addr[0]}:{addr[1]} — {len(data)} bytes")

            if addr[0] != sender_ip:
                log.warning(f"[REJECTED] Packet from unknown source {addr[0]} — only accepting from {sender_ip}")
                continue

            mac, err = _parse_magic_packet(data)
            if err:
                log.warning(f"[INVALID]  {err} — dropping")
                continue

            log.info(f"[VALID]    Magic packet verified — target MAC: {mac}")
            log.info(f"[SHUTDOWN] Shutdown command received from sender")

            _fire("Turned Off")

            subprocess.run(['shutdown', '/s', '/t', '5', '/c', 'Remote shutdown triggered'])
            log.info(f"[SHUTDOWN] Shutdown initiated")

    log.info("Packet receiver starting...")
    threading.Thread(target=_listen, daemon=True, name="packet-receiver").start()

    # Alert that this node just turned on
    _fire("Turned On")
    log.info("Packet receiver running — Turned On alert dispatched")
