"""
WebSocket-Consumer für WebRTC-Signaling und Whiteboard-Synchronisation.
"""

import html
import json
import logging
import time
import uuid
from collections import deque

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class MeetingConsumer(AsyncWebsocketConsumer):
    """
    Signaling-Server für ein einzelnes Meeting-Zimmer.

    Nachrichten-Typen vom Client:
      join        – Raum betreten (name)
      offer       – WebRTC Offer  (sdp, target_peer_id)
      answer      – WebRTC Answer (sdp, target_peer_id)
      ice         – ICE Candidate (candidate, target_peer_id)
      wb_event    – Whiteboard-Ereignis (action, data)
      chat        – Text-Nachricht  (text)
      kick        – Teilnehmer entfernen (target_peer_id) – nur Tutor
      doc_notify  – Neues Dokument  (name, url, date, doc_id)
      leave       – Raum verlassen

    Nachrichten vom Server:
      joined        – { peer_id, peers: [...] }
      peer_joined   – { peer_id, name }
      peer_left     – { peer_id, name }
      offer/answer/ice – weitergeleitet
      wb_event      – an alle außer Sender
      chat          – an alle
      kicked        – du wurdest entfernt
      doc_added     – { name, url, date, doc_id }
      error         – { message }
    """

    # Peers pro Raum: group_name -> {peer_id: name}
    _room_locks: dict = {}
    _rooms_data: dict[str, dict[str, str]] = {}
    # User-Token-Dedup: group_name -> {user_token: channel_name}
    _user_channels_data: dict[str, dict[str, str]] = {}

    @database_sync_to_async
    def _load_room_and_authorize(self, token, user, portal_user_id=None):
        from apps.meeting.models import MeetingRoom
        from apps.portal.models import ParentStudentLink, PortalUser, StudentPortalLink

        try:
            room = MeetingRoom.objects.select_related("lesson__contract__user").get(token=token)
        except MeetingRoom.DoesNotExist:
            return None, False, None, False

        if not room.is_active:
            return room, False, None, False

        contract = room.lesson.contract

        if not user.is_anonymous:
            if contract.user_id == user.pk:
                return room, True, None, True

        if portal_user_id is None:
            return room, False, None, False

        try:
            pu = PortalUser.objects.get(pk=portal_user_id)
        except PortalUser.DoesNotExist:
            return room, False, None, False

        has_access = (
            StudentPortalLink.objects.filter(
                portal_user=pu, contract=contract, is_active=True
            ).exists()
            or ParentStudentLink.objects.filter(
                parent=pu, contract=contract, is_active=True
            ).exists()
        )
        if not has_access:
            return room, False, None, False

        return room, True, pu, False

    async def connect(self):
        self.token = str(self.scope["url_route"]["kwargs"]["token"])
        self.group_name = f"meeting_{self.token.replace('-', '')}"
        self.peer_id = str(uuid.uuid4())
        self.display_name = "Gast"
        self.is_tutor = False
        self.user_token = ""
        self._portal_user = None
        self._joined = False
        self._msg_timestamps: deque = deque(maxlen=60)

        user = self.scope.get("user")
        session = self.scope.get("session")
        portal_user_id = session.get("portal_user_id") if session else None

        if (user is None or user.is_anonymous) and not portal_user_id:
            logger.warning(
                "WS connect: Anonymer oder fehlender Benutzer token=%s",
                self.token,
            )
            await self.close(code=4403)
            return

        room, has_access, portal_user, is_tutor = await self._load_room_and_authorize(
            self.token, user, portal_user_id=portal_user_id
        )
        if room is None or not room.is_active:
            logger.warning(
                "WS connect: Raum nicht gefunden/inaktiv token=%s user=%s",
                self.token,
                user,
            )
            await self.close(code=4404)
            return
        if not has_access:
            logger.warning(
                "WS connect: Kein Zugriff token=%s user=%s",
                self.token,
                user,
            )
            await self.close(code=4403)
            return

        self.is_tutor = is_tutor
        self._portal_user = portal_user

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        cls = self.__class__
        lock = await cls._get_room_lock(self.group_name)
        async with lock:
            # Dedup-Eintrag entfernen (nur wenn noch aktuell)
            if self.group_name in cls._user_channels_data and self.user_token:
                if (
                    cls._user_channels_data[self.group_name].get(self.user_token)
                    == self.channel_name
                ):
                    del cls._user_channels_data[self.group_name][self.user_token]
                if not cls._user_channels_data[self.group_name]:
                    del cls._user_channels_data[self.group_name]

            # Prüfe ob Peer tatsächlich im Raum war (Race-Condition-sicher)
            peer_was_in_room = self.peer_id in cls._rooms_data.get(self.group_name, {})

            if self.group_name in cls._rooms_data:
                cls._rooms_data[self.group_name].pop(self.peer_id, None)
                room_empty = not cls._rooms_data[self.group_name]
                if room_empty:
                    del cls._rooms_data[self.group_name]
            else:
                room_empty = True

        if peer_was_in_room:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "peer_left_event",
                    "peer_id": self.peer_id,
                    "name": self.display_name,
                },
            )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        # Lock aufräumen wenn Raum leer (außerhalb des Locks, aber threadsicher genug)
        if room_empty and self.group_name in cls._room_locks:
            # Nur löschen wenn niemand mehr wartet (best effort)
            try:
                room_lock = cls._room_locks[self.group_name]
                if not room_lock.locked():
                    del cls._room_locks[self.group_name]
            except KeyError:
                pass

    async def receive(self, text_data):
        # Rate-Limit: max. 60 Nachrichten in 10 Sekunden pro Verbindung
        now = time.monotonic()
        self._msg_timestamps.append(now)
        if len(self._msg_timestamps) == 60 and (now - self._msg_timestamps[0]) < 10.0:
            logger.warning(
                "WS rate-limit überschritten token=%s peer_id=%s",
                self.token,
                self.peer_id,
            )
            await self.close(code=4008)
            return

        if len(text_data) > 65_536:
            await self.close(code=4009)
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")
        cls = self.__class__

        if msg_type != "join":
            lock = await cls._get_room_lock(self.group_name)
            async with lock:
                if self.peer_id not in cls._rooms_data.get(self.group_name, {}):
                    return

        if msg_type == "join":
            if self._joined:
                return

            raw_name = str(data.get("name", "Gast"))[:60]
            self.display_name = html.escape(raw_name)

            user_pk = self.scope["user"].pk
            if self.is_tutor:
                self.user_token = f"tutor_{user_pk}"
            elif self._portal_user is not None:
                self.user_token = f"portal_{self._portal_user.pk}"
            else:
                self.user_token = f"user_{user_pk}"

            old_channel = None
            existing_peers = {}

            lock = await cls._get_room_lock(self.group_name)
            async with lock:
                if self.user_token:
                    if self.group_name not in cls._user_channels_data:
                        cls._user_channels_data[self.group_name] = {}
                    old_channel = cls._user_channels_data[self.group_name].get(self.user_token)
                    if old_channel == self.channel_name:
                        old_channel = None
                    cls._user_channels_data[self.group_name][self.user_token] = self.channel_name

                if self.group_name not in cls._rooms_data:
                    cls._rooms_data[self.group_name] = {}
                existing_peers = dict(cls._rooms_data[self.group_name])
                cls._rooms_data[self.group_name][self.peer_id] = self.display_name
                self._joined = True

            if old_channel:
                try:
                    await self.channel_layer.send(
                        old_channel,
                        {"type": "force_disconnect_event"},
                    )
                except Exception:  # noqa: S110
                    pass

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
            target = data.get("target_peer_id")
            if target:
                try:
                    uuid.UUID(str(target))
                except ValueError:
                    return

                lock = await cls._get_room_lock(self.group_name)
                async with lock:
                    if target not in cls._rooms_data.get(self.group_name, {}):
                        return  # Peer nicht im Raum — still drop

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
            # Whitelist erlaubter Whiteboard-Felder zum Schutz vor Payload-Injection
            allowed_wb_fields = {
                "type",
                "action",
                "x",
                "y",
                "color",
                "size",
                "path",
                "shape",
                "tool",
                "points",
            }
            sanitized_payload = {k: v for k, v in data.items() if k in allowed_wb_fields}
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "wb_broadcast_event",
                    "payload": sanitized_payload,
                    "sender_channel": self.channel_name,
                },
            )

        elif msg_type == "chat":
            text = html.escape(str(data.get("text", ""))[:500])
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat_event",
                    "peer_id": self.peer_id,
                    "name": self.display_name,
                    "text": text,
                },
            )

        elif msg_type == "kick":
            target = data.get("target_peer_id")
            if target and self.is_tutor:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "kick_event",
                        "target_peer_id": target,
                        "kicked_by": self.display_name,
                    },
                )

        elif msg_type == "doc_notify":
            if not self.is_tutor:
                return
            try:
                doc_id = int(data.get("doc_id", 0))
            except (ValueError, TypeError):
                return

            from apps.lessons.models import SessionDocument

            doc = await SessionDocument.objects.filter(
                pk=doc_id,
                session=await self._get_session(),
            ).afirst()
            if doc is None:
                return

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "doc_event",
                    "payload": {
                        "type": "doc_added",
                        "name": doc.name,
                        "url": doc.file.url,
                        "date": str(data.get("date", "")),
                        "doc_id": doc_id,
                    },
                    "sender_channel": self.channel_name,
                },
            )

        elif msg_type == "doc_delete":
            if not self.is_tutor:
                return
            try:
                doc_id = int(data.get("doc_id", 0))
            except (ValueError, TypeError):
                return
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "doc_event",
                    "payload": {
                        "type": "doc_removed",
                        "doc_id": doc_id,
                    },
                    "sender_channel": self.channel_name,
                },
            )

        elif msg_type == "leave":
            await self.close(code=1000)

    @database_sync_to_async
    def _get_session(self):
        from apps.meeting.models import MeetingRoom

        return MeetingRoom.objects.select_related("lesson").get(token=self.token).lesson

    async def peer_joined_event(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(
            json.dumps({"type": "peer_joined", "peer_id": event["peer_id"], "name": event["name"]})
        )

    async def peer_left_event(self, event):
        await self.send(
            json.dumps({"type": "peer_left", "peer_id": event["peer_id"], "name": event["name"]})
        )

    async def relay_event(self, event):
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

    async def kick_event(self, event):
        if event.get("target_peer_id") == self.peer_id:
            await self.send(json.dumps({"type": "kicked", "by": event.get("kicked_by", "")}))

    async def doc_event(self, event):
        await self.send(json.dumps(event["payload"]))

    async def force_disconnect_event(self, event):
        """Erzwingt Trennung bei Dedup (gleicher User meldet sich erneut an)."""
        await self.send(json.dumps({"type": "kicked", "by": "__reconnect__"}))
        await self.close()
