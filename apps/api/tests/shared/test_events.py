from dataclasses import dataclass

import pytest

from shared.events import Event, EventBus, EventHandler, publish, use_event_bus


@dataclass(frozen=True)
class UserDisabled(Event):
    user_id: str


@dataclass(frozen=True)
class Unrelated(Event):
    pass


async def test_only_subscribers_of_that_event_are_called_in_order():
    seen: list[str] = []

    async def first(event: UserDisabled) -> None:
        seen.append(f"first:{event.user_id}")

    async def second(event: UserDisabled) -> None:
        seen.append(f"second:{event.user_id}")

    async def other(_event: Unrelated) -> None:
        seen.append("other")

    bus = EventBus(
        [
            EventHandler(UserDisabled, first),
            EventHandler(Unrelated, other),
            EventHandler(UserDisabled, second),
        ]
    )
    with use_event_bus(bus):
        await publish(UserDisabled("u1"))
    assert seen == ["first:u1", "second:u1"]


async def test_a_handler_can_veto_the_operation_by_raising():
    async def veto(_event: UserDisabled) -> None:
        raise ValueError("still has open orders")

    with use_event_bus(EventBus([EventHandler(UserDisabled, veto)])), pytest.raises(ValueError):
        await publish(UserDisabled("u1"))


async def test_publishing_outside_a_unit_of_work_is_a_programming_error():
    with pytest.raises(RuntimeError):
        await publish(UserDisabled("u1"))


def test_subscribing_to_something_that_is_not_an_event_is_rejected():
    async def handler(_event) -> None:
        return None

    with pytest.raises(RuntimeError):
        EventBus([EventHandler(str, handler)])  # type: ignore[arg-type]
