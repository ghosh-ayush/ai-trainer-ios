"""Shared test harness: the golden fixture, a JSON round trip through the contract, and a
tiny host that applies state commands the way ``TrainerService`` does."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from ai_trainer import content
from ai_trainer.api import dispatch_json

# Rule tests run against the fixture, not whatever research content currently ships.
os.environ[content.PINNED_BUNDLE_ENV] = content.FIXTURE_BUNDLE_ID
content._active_bundle.cache_clear()

JSON = dict[str, Any]

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "shared/fixtures/v1"
DAY = 86400.0


def uid(number: int) -> str:
    """A deterministic UUID string for test records."""
    return f"00000000-0000-0000-0000-{number:012d}"


def golden_request() -> JSON:
    """The qualifying ``decide`` request: two completed 3x10 @ 100 lb exposures, 5 and 2 days ago."""
    request: JSON = json.loads((FIXTURES / "qualifying-request.json").read_text())
    return request


NOW: float = golden_request()["payload"]["now"]


def call(operation: str, payload: JSON) -> JSON:
    """One request through the real JSON entry point; returns the whole response envelope."""
    envelope = {"schemaVersion": "1.0", "operation": operation, "payload": payload}
    response: JSON = json.loads(dispatch_json(json.dumps(envelope)))
    return response


def result(operation: str, payload: JSON) -> Any:
    """The ``result`` of a successful call; fails loudly with the error otherwise."""
    response = call(operation, payload)
    if "error" in response:
        raise AssertionError(f"{operation} failed: {response['error']}")
    return response["result"]


class Athlete:
    """A host in miniature: holds state, sends commands, commits results and bumps ``revision``."""

    def __init__(self, state: JSON, permits_fixtures: bool = True) -> None:
        self.state = state
        self.permits_fixtures = permits_fixtures
        self._next_id = 1000

    @classmethod
    def qualified(cls) -> Athlete:
        """The golden athlete with two qualifying bench exposures."""
        return cls(golden_request()["payload"]["state"])

    @classmethod
    def fresh(cls) -> Athlete:
        """The golden athlete's program and profile with no training history."""
        athlete = cls.qualified()
        athlete.state["sessions"] = []
        return athlete

    @property
    def plan(self) -> JSON:
        override: JSON | None = self.state.get("nextPlanOverride")
        plan: JSON = override or self.state["program"]["plans"][self.state["program"]["sequenceIndex"]]
        return plan

    @property
    def slot(self) -> JSON:
        slot: JSON = self.plan["slots"][0]
        return slot

    @property
    def active_session(self) -> JSON | None:
        return next((s for s in reversed(self.state["sessions"]) if s["status"] in ("inProgress", "paused")), None)

    def ids(self, count: int = 10) -> list[str]:
        start = self._next_id
        self._next_id += count
        return [uid(start + offset) for offset in range(count)]

    def payload(self, command: str, arguments: JSON, now: float) -> JSON:
        return {
            "command": command,
            "arguments": arguments,
            "state": self.state,
            "permitsFixtures": self.permits_fixtures,
            "now": now,
            "ids": self.ids(),
        }

    def attempt(self, command: str, now: float = NOW, **arguments: Any) -> JSON:
        """Send a command; commit on success. Returns the raw response envelope."""
        response = call("stateCommand", self.payload(command, arguments, now))
        if "result" in response:
            self.state = response["result"]["state"]
            self.state["revision"] += 1
        return response

    def run(self, command: str, now: float = NOW, **arguments: Any) -> JSON:
        """Send a command that must succeed; returns its ``result``."""
        response = self.attempt(command, now, **arguments)
        if "error" in response:
            raise AssertionError(f"{command} failed: {response['error']}")
        outcome: JSON = response["result"]
        return outcome

    def error_code(self, command: str, now: float = NOW, **arguments: Any) -> str:
        """Send a command that must fail; returns its error code and leaves state unchanged."""
        before = copy.deepcopy(self.state)
        response = self.attempt(command, now, **arguments)
        if "error" not in response:
            raise AssertionError(f"{command} unexpectedly succeeded")
        assert self.state == before
        code: str = response["error"]["code"]
        return code

    def decide(self, request: JSON | None = None, permits_fixtures: bool | None = None) -> JSON:
        """A read-only Training Brain answer for ``request`` (default: progress the first slot)."""
        payload = {
            "state": self.state,
            "request": request or progression(self.slot["id"]),
            "permitsFixtures": self.permits_fixtures if permits_fixtures is None else permits_fixtures,
            "now": NOW,
        }
        decision: JSON = result("decide", payload)
        return decision

    def reason(self, request: JSON | None = None) -> str:
        reason: str = self.decide(request)["reason"]
        return reason

    def start(self, now: float = NOW) -> JSON:
        self.run("start", now, checkIn=check_in(now))
        session = self.active_session
        assert session is not None
        return session

    def save_set(self, session: JSON, index: int, reps: int, now: float = NOW, **extra: Any) -> JSON:
        """Log a working set on the first slot. ``load``/``rir`` are omitted unless given."""
        arguments: JSON = {
            "sessionID": session["id"],
            "slotID": session["plan"]["slots"][0]["id"],
            "index": index,
            "kind": "working",
            "reps": reps,
            "logID": uid(5000 + len(self.state["operations"])),
            "operationID": uid(6000 + len(self.state["operations"])),
            **extra,
        }
        return self.attempt("saveSet", now, **arguments)

    def propose(self, request: JSON | None = None) -> JSON:
        """Request a change and return the stored proposal."""
        outcome = self.run("requestChange", request=request or progression(self.slot["id"]))
        assert outcome["decision"]["outcome"] == "proposeChange", outcome["decision"]
        recommendation: JSON = self.state["recommendations"][-1]
        return recommendation


def progression(slot_id: str) -> JSON:
    return {"kind": "progression", "slotID": slot_id}


def check_in(now: float = NOW, **overrides: Any) -> JSON:
    return {"painReported": False, "unavailableEquipment": [], "occurredAt": now, **overrides}


def exposure(template: JSON, number: int, days_ago: float, reps: list[int], rir: int | None = 2) -> JSON:
    """A completed session copied from ``template`` with the given working sets at 100 lb."""
    session = copy.deepcopy(template)
    started = NOW - days_ago * DAY
    session.update(id=uid(number), startedAt=started, endedAt=started + 1800, status="completed")
    logs = []
    for index, count in enumerate(reps):
        log = copy.deepcopy(template["logs"][0])
        log.update(id=uid(number * 10 + index), operationID=uid(number * 10 + index + 5), index=index, reps=count)
        log["occurredAt"] = started
        log.pop("rir", None)
        if rir is not None:
            log["rir"] = rir
        logs.append(log)
    session["logs"] = logs
    return session
