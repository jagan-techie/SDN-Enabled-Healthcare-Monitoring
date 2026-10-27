# scripts/local_broker.py - Lightweight standalone asyncio MQTT 3.1.1 broker for local testing
import asyncio
import logging
import struct
from typing import Dict, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [MQTT-Broker] %(message)s")
logger = logging.getLogger("MQTTBroker")

def decode_remaining_length(data: bytes, offset: int) -> Tuple[int, int]:
    multiplier = 1
    value = 0
    idx = offset
    while True:
        if idx >= len(data):
            return -1, offset
        byte = data[idx]
        idx += 1
        value += (byte & 127) * multiplier
        multiplier *= 128
        if (byte & 128) == 0:
            break
        if multiplier > 128 * 128 * 128:
            raise ValueError("Malformed remaining length in MQTT packet")
    return value, idx

def encode_remaining_length(length: int) -> bytes:
    encoded = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length > 0:
            digit |= 0x80
        encoded.append(digit)
        if length == 0:
            break
    return bytes(encoded)

def topic_matches(pattern: str, topic: str) -> bool:
    if pattern == topic or pattern == "#":
        return True
    pattern_parts = pattern.split("/")
    topic_parts = topic.split("/")
    i = 0
    while i < len(pattern_parts) and i < len(topic_parts):
        if pattern_parts[i] == "#":
            return True
        if pattern_parts[i] != "+" and pattern_parts[i] != topic_parts[i]:
            return False
        i += 1
    if i < len(pattern_parts) and pattern_parts[i] == "#":
        return True
    return i == len(pattern_parts) and i == len(topic_parts)

class MQTTClientHandler:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, broker: 'LocalMQTTBroker'):
        self.reader = reader
        self.writer = writer
        self.broker = broker
        self.client_id = ""
        self.subscriptions: Set[str] = set()

    async def handle(self):
        buffer = bytearray()
        try:
            while True:
                chunk = await self.reader.read(4096)
                if not chunk:
                    break
                buffer.extend(chunk)

                while len(buffer) >= 2:
                    packet_type = buffer[0] >> 4
                    flags = buffer[0] & 0x0F
                    rem_len, header_end = decode_remaining_length(buffer, 1)
                    if rem_len == -1 or len(buffer) < header_end + rem_len:
                        break  # Incomplete packet, wait for more data

                    packet_payload = buffer[header_end:header_end + rem_len]
                    del buffer[:header_end + rem_len]

                    await self.process_packet(packet_type, flags, packet_payload)
        except Exception as e:
            logger.debug(f"Client connection closed: {e}")
        finally:
            self.broker.remove_client(self)
            self.writer.close()
            await self.writer.wait_closed()

    async def send_packet(self, packet: bytes):
        try:
            self.writer.write(packet)
            await self.writer.drain()
        except Exception:
            pass

    async def process_packet(self, packet_type: int, flags: int, data: bytes):
        if packet_type == 1:  # CONNECT
            # Protocol Name len (2 bytes), Name, Level (1 byte), Flags (1 byte), KeepAlive (2 bytes), ClientID
            if len(data) >= 10:
                proto_len = struct.unpack("!H", data[0:2])[0]
                client_id_offset = 2 + proto_len + 4
                if len(data) >= client_id_offset + 2:
                    cid_len = struct.unpack("!H", data[client_id_offset:client_id_offset+2])[0]
                    self.client_id = data[client_id_offset+2:client_id_offset+2+cid_len].decode('utf-8', errors='ignore')
            logger.info(f"Client connected: {self.client_id or 'anonymous'}")
            # Reply CONNACK (0x20, remaining len 2, session present 0, return code 0)
            await self.send_packet(bytes([0x20, 0x02, 0x00, 0x00]))

        elif packet_type == 3:  # PUBLISH
            qos = (flags >> 1) & 0x03
            retain = flags & 0x01
            topic_len = struct.unpack("!H", data[0:2])[0]
            topic = data[2:2+topic_len].decode('utf-8', errors='ignore')
            offset = 2 + topic_len
            packet_id = 0
            if qos > 0:
                packet_id = struct.unpack("!H", data[offset:offset+2])[0]
                offset += 2
            payload = data[offset:]

            # If QoS 1, acknowledge with PUBACK
            if qos == 1:
                puback = bytearray([0x40, 0x02])
                puback.extend(struct.pack("!H", packet_id))
                await self.send_packet(bytes(puback))

            # Broadcast to subscribers
            await self.broker.publish_message(topic, payload, qos=0)

        elif packet_type == 8:  # SUBSCRIBE
            packet_id = struct.unpack("!H", data[0:2])[0]
            offset = 2
            granted_qos = []
            while offset < len(data):
                top_len = struct.unpack("!H", data[offset:offset+2])[0]
                topic_filter = data[offset+2:offset+2+top_len].decode('utf-8', errors='ignore')
                offset += 2 + top_len
                req_qos = data[offset]
                offset += 1
                self.subscriptions.add(topic_filter)
                granted_qos.append(req_qos)
                logger.info(f"Client {self.client_id} subscribed to '{topic_filter}'")

            # Reply SUBACK
            suback = bytearray([0x90])
            suback.extend(encode_remaining_length(2 + len(granted_qos)))
            suback.extend(struct.pack("!H", packet_id))
            suback.extend(granted_qos)
            await self.send_packet(bytes(suback))

        elif packet_type == 10:  # UNSUBSCRIBE
            packet_id = struct.unpack("!H", data[0:2])[0]
            unsuback = bytearray([0xB0, 0x02])
            unsuback.extend(struct.pack("!H", packet_id))
            await self.send_packet(bytes(unsuback))

        elif packet_type == 12:  # PINGREQ
            await self.send_packet(bytes([0xD0, 0x00]))  # PINGRESP

        elif packet_type == 14:  # DISCONNECT
            pass

class LocalMQTTBroker:
    def __init__(self, host: str = "0.0.0.0", port: int = 1883):
        self.host = host
        self.port = port
        self.clients: Set[MQTTClientHandler] = set()
        self.server = None

    async def client_connected(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client = MQTTClientHandler(reader, writer, self)
        self.clients.add(client)
        await client.handle()

    def remove_client(self, client: MQTTClientHandler):
        self.clients.discard(client)

    async def publish_message(self, topic: str, payload: bytes, qos: int = 0):
        # Build standard PUBLISH packet (QoS 0)
        topic_bytes = topic.encode('utf-8')
        var_header = struct.pack("!H", len(topic_bytes)) + topic_bytes
        body = var_header + payload
        packet = bytearray([0x30])  # PUBLISH, QoS 0
        packet.extend(encode_remaining_length(len(body)))
        packet.extend(body)
        raw_packet = bytes(packet)

        for client in list(self.clients):
            for sub in client.subscriptions:
                if topic_matches(sub, topic):
                    await client.send_packet(raw_packet)
                    break

    async def start(self):
        self.server = await asyncio.start_server(self.client_connected, self.host, self.port)
        logger.info(f"Local MQTT Broker listening on {self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()

if __name__ == "__main__":
    broker = LocalMQTTBroker(host="0.0.0.0", port=1883)
    try:
        asyncio.run(broker.start())
    except KeyboardInterrupt:
        logger.info("Broker stopped by user.")
