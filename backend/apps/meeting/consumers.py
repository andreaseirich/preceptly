"""
WebSocket-Consumer für WebRTC-Signaling und Whiteboard-Synchronisation.
"""

import json
import logging
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class MeetingConsumer(AsyncWebsocketConsumer):
    """
    Signaling-Server für ein einzelnes Meeting-Zimmer.

    Nachrichten-Typen vom Client:
      join        – Raum betreten (name, peer_id)
      offer       – WebRTC Offer  (sdp, target_peer_id)
      answer      – WebRTC Answer (sdp, target_peer_id)
      ice         – ICE Candidate (candidate, target_peer_id)
      wb_event    – Whiteboard-Ereignis (action, data)
      chat        – Text-Nachricht  (text)
      leave       – Raum verlassen

    Nachrichten vom Server (broadcastet oder direkt):
      peer_joined   – { peer_id, name, peers: [...] }
      peer_left     – { peer_id, name }
      offer/answer/ice – weitergeleitet an Zielpeer
      wb_event      – an alle außer Sender
      chat          – an alle
      error         – { message }
    """

    # Peers pro Raum: token -> {peer_id: name}
    rooms: dict[str, dict[str, str]] = {}

    async def connect(self):
        self.token = str(self.scope["url_route"]["kwargs"]["token"])
        self.group_name = f"meeting_{self.token.replace('-', '')}"
        self.peer_id = str(uuid.uuid4())
        self.display_name = "Gast"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.group_name in self.rooms:
            self.rooms[self.group_name].pop(self.peer_id, None)
            if not self.rooms[self.group_name]:
                del self.rooms[self.group_name]

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "peer_left_event",
                "peer_id": self.peer_id,
                "name": self.display_name,
            },
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")

        if msg_type == "join":
            self.display_name = data.get("name", "Gast")[:60]
            if self.group_name not in self.rooms:
                self.rooms[self.group_name] = {}
            existing_peers = dict(self.rooms[self.group_name])
            self.rooms[self.group_name][self.peer_id] = self.display_name

            # Send back own peer_id + list of existing peers
            await self.send(
                json.dumps(
                    {
                        "type": "joined",
                        "peer_id": self.peer_id,
                        "peers": [
                            {"peer_id": pid, "name": name} for pid, name in existing_peers.items()
                        ],
                    }
                )
            )

            # Notify others
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "peer_joined_event",
                    "peer_id": self.peer_id,
                    "name": self.display_name,
                    "sender_channel": self.channel_name,
                },
            )

        elif msg_type in ("offer", "answer", "ice"):
            # Forward to specific peer
            target = data.get("target_peer_id")
            if target:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "relay_event",
                        "payload": data,
                        "sender_peer_id": self.peer_id,
                        "target_peer_id": target,
                        "sender_channel": self.channel_name,
                    },
                )

        elif msg_type == "wb_event":
            # Broadcast whiteboard events to all (except sender)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "wb_broadcast_event",
                    "payload": data,
                    "sender_channel": self.channel_name,
                },
            )

        elif msg_type == "chat":
            text = str(data.get("text", ""))[:500]
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat_event",
                    "peer_id": self.peer_id,
                    "name": self.display_name,
                    "text": text,
                },
            )

        elif msg_type == "leave":
            await self.disconnect(1000)

    # ── Channel layer event handlers ──────────────────────────────────────────

    async def peer_joined_event(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(
            json.dumps(
                {
                    "type": "peer_joined",
                    "peer_id": event["peer_id"],
                    "name": event["name"],
                }
            )
        )

    async def peer_left_event(self, event):
        await self.send(
            json.dumps(
                {
                    "type": "peer_left",
                    "peer_id": event["peer_id"],
                    "name": event["name"],
                }
            )
        )

    async def relay_event(self, event):
        # Only deliver to the target peer
        if event.get("target_peer_id") != self.peer_id:
            return
        payload = dict(event["payload"])
        payload["sender_peer_id"] = event["sender_peer_id"]
        await self.send(json.dumps(payload))

    async def wb_broadcast_event(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(json.dumps(event["payload"]))

    async def chat_event(self, event):
        await self.send(
            json.dumps(
                {
                    "type": "chat",
                    "peer_id": event["peer_id"],
                    "name": event["name"],
                    "text": event["text"],
                }
            )
        )
