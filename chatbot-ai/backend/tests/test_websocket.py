import uuid

import pytest

from app.websocket.manager import ConnectionManager


class _FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent: list[dict] = []
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_connection_manager_routes_messages_to_correct_user():
    manager = ConnectionManager()
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    ws_a = _FakeWebSocket()
    ws_b = _FakeWebSocket()

    await manager.connect(user_a, ws_a)
    await manager.connect(user_b, ws_b)

    await manager.send_to_user(user_a, {"title": "for A"})

    assert ws_a.sent == [{"title": "for A"}]
    assert ws_b.sent == []


@pytest.mark.asyncio
async def test_connection_manager_supports_multiple_sockets_per_user():
    manager = ConnectionManager()
    user = uuid.uuid4()
    ws1, ws2 = _FakeWebSocket(), _FakeWebSocket()

    await manager.connect(user, ws1)
    await manager.connect(user, ws2)
    await manager.send_to_user(user, {"title": "hi"})

    assert ws1.sent == [{"title": "hi"}]
    assert ws2.sent == [{"title": "hi"}]


@pytest.mark.asyncio
async def test_disconnect_removes_socket_and_stops_further_delivery():
    manager = ConnectionManager()
    user = uuid.uuid4()
    ws = _FakeWebSocket()

    await manager.connect(user, ws)
    manager.disconnect(user, ws)
    await manager.send_to_user(user, {"title": "should not arrive"})

    assert ws.sent == []


@pytest.mark.asyncio
async def test_send_to_unknown_user_is_a_noop():
    manager = ConnectionManager()
    # Should not raise even though nobody is connected for this user.
    await manager.send_to_user(uuid.uuid4(), {"title": "irrelevant"})


@pytest.mark.asyncio
async def test_broken_socket_is_dropped_without_raising():
    manager = ConnectionManager()
    user = uuid.uuid4()

    class _BrokenWebSocket(_FakeWebSocket):
        async def send_json(self, payload):
            raise ConnectionError("client went away")

    good = _FakeWebSocket()
    broken = _BrokenWebSocket()
    await manager.connect(user, good)
    await manager.connect(user, broken)

    await manager.send_to_user(user, {"title": "hello"})

    assert good.sent == [{"title": "hello"}]
    # The broken socket should have been silently removed, not left registered.
    await manager.send_to_user(user, {"title": "again"})
    assert good.sent == [{"title": "hello"}, {"title": "again"}]
