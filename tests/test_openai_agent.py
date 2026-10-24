from types import SimpleNamespace

import pytest

from case_closed import agent, openai_agent


def call(id, name, arguments):
    return SimpleNamespace(id=id, function=SimpleNamespace(name=name, arguments=arguments))


def completion(finish_reason, content=None, tool_calls=None, refusal=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason, message=message)])


class FakeOpenAI:
    """Stands in for openai.OpenAI(): returns scripted completions and records each request."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0)


def test_tools_are_wrapped_as_functions():
    names = [t["function"]["name"] for t in openai_agent.OPENAI_TOOLS]
    assert names == ["list_evidence", "read_evidence", "search_evidence"]
    assert all(t["type"] == "function" for t in openai_agent.OPENAI_TOOLS)


def test_investigate_runs_tools_and_sends_results_back():
    client = FakeOpenAI([
        completion("tool_calls", tool_calls=[
            call("c1", "read_evidence", '{"name": "door_log.csv"}'),
            call("c2", "read_evidence", '{"name": "solution.json"}'),
        ]),
        completion("stop", content="Culprit: Victor Crane"),
    ])

    assert openai_agent.investigate("Who did it?", client) == ("Culprit: Victor Crane", 2)

    messages = client.requests[1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool", "tool"]
    assert messages[2]["tool_calls"][0]["function"]["name"] == "read_evidence"
    assert messages[3]["tool_call_id"] == "c1"
    assert "20:36,Gallery,Victor Crane" in messages[3]["content"]
    assert messages[4]["content"].startswith("Error:")  # solution.json is hidden


def test_investigate_handles_bad_json_arguments():
    client = FakeOpenAI([
        completion("tool_calls", tool_calls=[call("c1", "read_evidence", "{not json")]),
        completion("stop", content="Done."),
    ])
    openai_agent.investigate("Who did it?", client)
    assert client.requests[1]["messages"][3]["content"] == "Error: Arguments were not valid JSON."


def test_investigate_raises_on_refusal():
    client = FakeOpenAI([completion("stop", refusal="I can't help with that.")])
    with pytest.raises(agent.InvestigationError):
        openai_agent.investigate("Who did it?", client)


def test_get_investigator_picks_openai():
    assert agent.get_investigator("openai") is openai_agent.investigate
