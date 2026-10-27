import json

from case_closed import agent
from case_closed import eval as evaluate
from test_agent import FakeClient, reply, text, tool_use


def make_case(cases_dir, name, culprit):
    case = cases_dir / name
    case.mkdir()
    (case / "brief.md").write_text(f"The {name} case.")
    (case / "solution.json").write_text(json.dumps({"culprit": culprit}))


def test_accused_reads_last_culprit_line():
    assert evaluate.accused("Long reasoning...\nCulprit: Victor Crane") == "Victor Crane"
    assert evaluate.accused("**Culprit:** Victor Crane.") == "Victor Crane"
    assert evaluate.accused("I suspect Sophie.\nCulprit: Sophie\nCulprit: Victor Crane") == "Victor Crane"
    assert evaluate.accused("I think it was Victor Crane.") is None


def test_case_dirs_only_includes_cases_with_a_solution(tmp_path, monkeypatch):
    make_case(tmp_path, "b_case", "Ann Lee")
    make_case(tmp_path, "a_case", "Bob Ray")
    (tmp_path / "draft").mkdir()
    monkeypatch.setattr(agent, "CASES_DIR", tmp_path)
    assert [d.name for d in evaluate.case_dirs()] == ["a_case", "b_case"]


def test_run_scores_cases_and_averages_tool_calls(tmp_path, monkeypatch, capsys):
    make_case(tmp_path, "a_case", "Ann Lee")
    make_case(tmp_path, "b_case", "Bob Ray")
    make_case(tmp_path, "c_case", "Cy Doe")
    monkeypatch.setattr(agent, "CASES_DIR", tmp_path)
    client = FakeClient([
        # a_case: 2 tool calls, right answer
        reply("tool_use", tool_use("t1", "list_evidence", {}), tool_use("t2", "read_evidence", {"name": "brief.md"})),
        reply("end_turn", text("Culprit: Ann Lee")),
        # b_case: 1 tool call, wrong answer
        reply("tool_use", tool_use("t3", "search_evidence", {"keyword": "case"})),
        reply("end_turn", text("Culprit: Someone Else")),
        # c_case: refuses after 0 tool calls
        reply("refusal"),
    ])

    assert evaluate.run(client) == (1, 3)
    out = capsys.readouterr().out
    assert "Culprit: Ann Lee\n" in out  # the full answer is printed
    assert "SOLVED: accused Ann Lee" in out
    assert "WRONG: accused Someone Else, culprit was Bob Ray" in out
    assert "WRONG: accused nobody, culprit was Cy Doe" in out
    assert "1/3 solved, avg 1.0 tool calls" in out


def test_tools_read_the_case_they_are_given(tmp_path):
    make_case(tmp_path, "a_case", "Ann Lee")
    case = tmp_path / "a_case"
    assert agent.list_evidence(case) == "brief.md"
    assert agent.run_tool("read_evidence", {"name": "brief.md"}, case) == ("The a_case case.", False)
    assert agent.run_tool("read_evidence", {"name": "solution.json"}, case)[1] is True
