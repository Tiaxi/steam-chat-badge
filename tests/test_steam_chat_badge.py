# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.machinery
import importlib.util
import json
import socket
import struct
import sys
import threading
import unittest
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "steam-chat-badge"
_loader = importlib.machinery.SourceFileLoader("steam_chat_badge", str(_path))
_spec = importlib.util.spec_from_loader("steam_chat_badge", _loader)
scb = importlib.util.module_from_spec(_spec)
sys.modules["steam_chat_badge"] = scb
_loader.exec_module(scb)

Unread, BadgeState, next_state = scb.Unread, scb.BadgeState, scb.next_state


def server_frame(opcode, payload, fin=True):
    """Encode an unmasked frame, as a server sends it."""
    header = bytearray([(0x80 if fin else 0) | opcode])
    if len(payload) < 126:
        header.append(len(payload))
    elif len(payload) < 1 << 16:
        header.append(126)
        header += struct.pack(">H", len(payload))
    else:
        header.append(127)
        header += struct.pack(">Q", len(payload))
    return bytes(header) + payload


def decode_client_frame(data):
    """Decode one masked client frame; return (opcode, payload, rest)."""
    opcode = data[0] & 0x0F
    assert data[1] & 0x80, "client frames must be masked"
    length, offset = data[1] & 0x7F, 2
    if length == 126:
        length, offset = struct.unpack(">H", data[2:4])[0], 4
    elif length == 127:
        length, offset = struct.unpack(">Q", data[2:10])[0], 10
    mask = data[offset:offset + 4]
    start = offset + 4
    return opcode, scb.apply_mask(data[start:start + length], mask), data[start + length:]


class FrameTests(unittest.TestCase):
    def test_mask_round_trip(self):
        payload = bytes(range(256)) * 3
        mask = b"\x01\x02\x03\x04"
        self.assertEqual(scb.apply_mask(scb.apply_mask(payload, mask), mask), payload)
        self.assertEqual(scb.apply_mask(b"", mask), b"")

    def test_encode_lengths(self):
        for size in (0, 125, 126, 65535, 65536):
            payload = b"x" * size
            opcode, decoded, rest = decode_client_frame(scb.encode_frame(0x1, payload, b"abcd"))
            self.assertEqual((opcode, decoded, rest), (0x1, payload, b""))


class WebSocketTests(unittest.TestCase):
    def setUp(self):
        self.client_sock, self.server = socket.socketpair()
        self.client_sock.settimeout(5)
        self.server.settimeout(5)
        self.ws = scb.WebSocket(self.client_sock)

    def tearDown(self):
        self.client_sock.close()
        self.server.close()

    def test_fragmented_message_and_ping(self):
        self.server.sendall(
            server_frame(0x1, b'{"a":', fin=False)
            + server_frame(0x9, b"hi")
            + server_frame(0x0, b"1}"))
        self.assertEqual(json.loads(self.ws.recv_text()), {"a": 1})
        opcode, payload, _ = decode_client_frame(self.server.recv(1024))
        self.assertEqual((opcode, payload), (0xA, b"hi"))

    def test_close_frame_raises(self):
        self.server.sendall(server_frame(0x8, b""))
        with self.assertRaises(scb.WebSocketClosed):
            self.ws.recv_text()

    def test_eof_raises(self):
        self.server.close()
        with self.assertRaises(scb.WebSocketClosed):
            self.ws.recv_text()

    def test_handshake(self):
        def serve():
            request = b""
            while b"\r\n\r\n" not in request:
                request += self.server.recv(4096)
            key = next(line.split(b":", 1)[1].strip().decode()
                       for line in request.split(b"\r\n") if line.lower().startswith(b"sec-websocket-key"))
            accept = scb.base64.b64encode(scb.hashlib.sha1((key + scb._WS_GUID).encode()).digest())
            self.server.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                                b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"
                                + server_frame(0x1, b"ok"))

        thread = threading.Thread(target=serve)
        thread.start()
        self.ws.handshake("127.0.0.1:8080", "/devtools/page/x")
        thread.join()
        self.assertEqual(self.ws.recv_text(), "ok")

    def test_handshake_rejected(self):
        self.server.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
        with self.assertRaises(scb.WebSocketError):
            self.ws.handshake("127.0.0.1:8080", "/")


class ParseTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(
            scb.parse_unread({"chats": 2, "messages": 5, "doNotDisturb": True, "flashMode": 2}),
            Unread(2, 5, True, 2))
        self.assertIsNone(scb.parse_unread(None))
        self.assertIsNone(scb.parse_unread({"chats": "x"}))


class StateTests(unittest.TestCase):
    def test_new_message_raises_attention(self):
        state = next_state(BadgeState(), Unread(1, 2), steam_active=False)
        self.assertEqual(state, BadgeState(count=2, messages=2, attention=True))

    def test_looking_at_steam_clears_attention_but_keeps_badge(self):
        state = BadgeState(count=2, messages=2, attention=True)
        state = next_state(state, Unread(1, 2), steam_active=True)
        self.assertEqual(state, BadgeState(count=2, messages=2, attention=False))
        state = next_state(state, Unread(1, 2), steam_active=False)
        self.assertFalse(state.attention)

    def test_another_message_raises_attention_again(self):
        state = BadgeState(count=2, messages=2, attention=False)
        self.assertTrue(next_state(state, Unread(1, 3), steam_active=False).attention)

    def test_message_while_steam_active_does_not_flash(self):
        self.assertFalse(next_state(BadgeState(), Unread(1, 1), steam_active=True).attention)

    def test_read_everything_clears(self):
        state = BadgeState(count=2, messages=2, attention=True)
        self.assertEqual(next_state(state, Unread(0, 0), steam_active=False), BadgeState())
        self.assertEqual(next_state(state, None, steam_active=False), BadgeState())

    def test_never_and_do_not_disturb_keep_badge_without_flash(self):
        for unread in (Unread(1, 1, flash_mode=scb.FLASH_NEVER), Unread(1, 1, do_not_disturb=True)):
            self.assertEqual(next_state(BadgeState(), unread, steam_active=False),
                             BadgeState(count=1, messages=1, attention=False))

    def test_count_chats(self):
        self.assertEqual(next_state(BadgeState(), Unread(2, 7), False, count_mode="chats").count, 2)


class ArgsTests(unittest.TestCase):
    def test_defaults(self):
        args = scb.parse_args([])
        self.assertEqual(args.app_uri, [scb.DEFAULT_APP_URI])
        self.assertEqual(args.port, 8080)

    def test_repeatable_app_uri(self):
        args = scb.parse_args(["--app-uri", "application://a.desktop", "--app-uri", "application://b.desktop"])
        self.assertEqual(args.app_uri, ["application://a.desktop", "application://b.desktop"])


if __name__ == "__main__":
    unittest.main()
