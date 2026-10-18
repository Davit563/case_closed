from types import SimpleNamespace

import pytest

from case_closed import agent


def text(s):
    return SimpleNamespace(type="text", text=s)


def tool_use(id, name, input):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


def reply(stop_reason, *content):
    return SimpleNamespace(stop_reason=stop_reason, content=list(content))


class FakeClient:
    """Stands in for anthropic.Anthropic(): returns scripted replies and records each request."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        # Copy the list, because solve() keeps appending to the same one.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0)


def test_list_evidence_hides_solution():
    files = agent.list_evidence().splitlines()
    assert "door_log.csv" in files
    assert "statements/victor_crane.txt" in files
    assert "solution.json" not in files


def test_read_evidence_rejects_solution_and_escapes():
    for path in ["solution.json", "../../pyproject.toml", "missing.txt"]:
        with pytest.raises(ValueError):
            agent.read_evidence(path)


def test_search_evidence_finds_lines_and_hides_solution():
    out = agent.search_evidence("gallery")
    assert "door_log.csv:8: 20:36,Gallery,Victor Crane" in out
    assert "solution.json" not in out
    assert agent.search_evidence("zeppelin") == "No lines contain 'zeppelin'."


def test_run_tool_reports_errors():
    assert agent.run_tool("read_evidence", {"name": "door_log.csv"})[1] is False
    assert agent.run_tool("read_evidence", {"name": "solution.json"})[1] is True
    assert agent.run_tool("read_evidence", {})[1] is True
    assert agent.run_tool("search_evidence", {"keyword": "Terrace"})[1] is False
    assert agent.run_tool("search_evidence", {})[1] is True
    assert agent.run_tool("no_such_tool", {})[1] is True


def test_solve_runs_tools_and_sends_results_back():
    client = FakeClient([
        reply("tool_use",
              text("Let me check the log and Victor's statement."),
              tool_use("t1", "read_evidence", {"name": "door_log.csv"}),
              tool_use("t2", "read_evidence", {"name": "statements/victor_crane.txt"})),
        reply("end_turn", text("Victor Crane did it.")),
    ])

    assert agent.solve("Who did it?", client=client) == "Victor Crane did it."
    assert len(client.requests) == 2
    assert client.requests[0]["model"] == "claude-sonnet-5-5"

    # Second request: question, Claude's tool calls, then both results in one user message.
    messages = client.requests[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    results = messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert "20:36,Gallery,Victor Crane" in results[0]["content"]
    assert results[0]["is_error"] is False


def test_solve_raises_on_refusal():
    client = FakeClient([reply("refusal")])
    with pytest.raises(RuntimeError):
        agent.solve("Who did it?", client=client)


def test_solve_prints_each_tool_call(capsys):
    client = FakeClient([
        reply("tool_use", tool_use("t1", "read_evidence", {"name": "solution.json"})),
        reply("end_turn", text("Done.")),
    ])
    agent.solve("Who did it?", client=client)
    out = capsys.readouterr().out
    assert "[step 1] read_evidence({'name': 'solution.json'})" in out
    assert "error:" in out


def test_solve_stops_after_step_limit():
    looping = [reply("tool_use", tool_use(f"t{i}", "list_evidence", {})) for i in range(agent.MAX_STEPS)]
    client = FakeClient(looping)
    with pytest.raises(RuntimeError, match="15 steps"):
        agent.solve("Who did it?", client=client)
    assert len(client.requests) == 15


def test_main_requires_solve_command():
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", "case_closed"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "usage: python -m case_closed solve" in result.stderr
