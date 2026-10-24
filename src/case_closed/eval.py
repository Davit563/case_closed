"""Score the detective: run it on every case in cases/ and compare with solution.json."""

import json
import re

from case_closed import agent

QUESTION = (
    "Investigate this case and work out who did it. "
    "End your answer with one line of the form 'Culprit: Full Name'."
)


def case_dirs():
    """Every case folder that has a solution.json."""
    return sorted(p.parent for p in agent.CASES_DIR.glob("*/solution.json"))


def accused(answer):
    """The name on the last 'Culprit: ...' line, or None if there isn't one."""
    names = re.findall(r"^\W*culprit\W*:\s*(.+?)\s*$", answer, re.IGNORECASE | re.MULTILINE)
    return names[-1].strip("*_. ") if names else None


def run(client=None, provider="anthropic"):
    cases = case_dirs()
    if not cases:
        print(f"No cases with a solution.json in {agent.CASES_DIR}.")
        return 0, 0

    investigate = agent.get_investigator(provider)
    print(f"Provider: {provider}")
    solved = 0
    tool_calls = []
    for case_dir in cases:
        culprit = json.loads((case_dir / "solution.json").read_text())["culprit"]
        print(f"\n=== {case_dir.name} ===")
        try:
            answer, calls = investigate(QUESTION, client, case_dir)
            name = accused(answer)
        except agent.InvestigationError as e:
            print(f"failed: {e}")
            name, calls = None, e.tool_calls

        correct = name is not None and culprit.lower() in name.lower()
        solved += correct
        tool_calls.append(calls)
        verdict = "SOLVED" if correct else "WRONG"
        print(f"{verdict}: accused {name or 'nobody'}, culprit was {culprit} ({calls} tool calls)")

    print(f"\n{solved}/{len(cases)} solved, avg {sum(tool_calls) / len(tool_calls):.1f} tool calls")
    return solved, len(cases)
