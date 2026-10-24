"""A hand-written tool-use loop: Claude investigates the case by reading evidence files."""

import os
import sys
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5-5"
CASES_DIR = Path(__file__).resolve().parents[2] / "cases"
CASE_DIR = CASES_DIR / "blackwood_manor"  # the default case
HIDDEN = {"solution.json"}  # the detective must not read the answer
MAX_STEPS = 15  # stop a runaway investigation

SYSTEM = (
    "You are a meticulous detective. Gather evidence before accusing anyone. "
    "Cite the files that prove your answer."
)

class InvestigationError(RuntimeError):
    """The detective gave up without an answer. Remembers how many tools it had called."""

    def __init__(self, message, tool_calls):
        super().__init__(message)
        self.tool_calls = tool_calls


TOOLS = [
    {
        "name": "list_evidence",
        "description": "List the name of every evidence file in the case folder.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_evidence",
        "description": "Read one evidence file by its name from list_evidence, e.g. statements/victor_crane.txt.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "File name from list_evidence."}},
            "required": ["name"],
        },
    },
    {
        "name": "search_evidence",
        "description": "Find every line in the evidence files that contains a keyword (case-insensitive).",
        "input_schema": {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "Word or phrase to look for, e.g. Gallery."}},
            "required": ["keyword"],
        },
    },
]


def list_evidence(case_dir=CASE_DIR):
    names = [p.relative_to(case_dir).as_posix() for p in case_dir.rglob("*") if p.is_file()]
    return "\n".join(sorted(n for n in names if n not in HIDDEN))


def read_evidence(name, case_dir=CASE_DIR):
    case_dir = case_dir.resolve()
    file = (case_dir / name).resolve()
    if case_dir not in file.parents or file.name in HIDDEN or not file.is_file():
        raise ValueError(f"No evidence file named {name!r}. Call list_evidence to see the files.")
    return file.read_text()


def search_evidence(keyword, case_dir=CASE_DIR):
    matches = []
    for name in list_evidence(case_dir).splitlines():
        for number, line in enumerate(read_evidence(name, case_dir).splitlines(), start=1):
            if keyword.lower() in line.lower():
                matches.append(f"{name}:{number}: {line.strip()}")
    return "\n".join(matches) or f"No lines contain {keyword!r}."


def run_tool(tool_name, tool_input, case_dir=CASE_DIR):
    """Run one tool call. Returns (content, is_error)."""
    try:
        if tool_name == "list_evidence":
            return list_evidence(case_dir), False
        if tool_name == "read_evidence":
            return read_evidence(tool_input["name"], case_dir), False
        if tool_name == "search_evidence":
            return search_evidence(tool_input["keyword"], case_dir), False
        return f"Unknown tool {tool_name!r}.", True
    except (KeyError, ValueError) as e:
        return str(e), True


def default_provider():
    """Use whichever API key is set: Anthropic first, then OpenAI."""
    if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "anthropic"


def get_investigator(provider):
    """The investigate() function for "anthropic" (this file) or "openai" (openai_agent.py)."""
    if provider == "anthropic":
        return investigate
    if provider == "openai":
        from case_closed import openai_agent  # imported here so agent.py doesn't depend on it
        return openai_agent.investigate
    raise ValueError(f"Unknown provider {provider!r}. Use 'anthropic' or 'openai'.")


def solve(question, client=None, case_dir=CASE_DIR, provider="anthropic"):
    answer, _ = get_investigator(provider)(question, client, case_dir)
    return answer


def investigate(question, client=None, case_dir=CASE_DIR):
    """Run the tool-use loop on one case. Returns (answer, number of tool calls)."""
    client = client or anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    tool_calls = 0

    for step in range(1, MAX_STEPS + 1):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if Sonnet declines, the API retries on a fallback model
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        # Keep Claude's whole reply (including tool_use blocks) in the history.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        # Run every tool Claude asked for and send all the results back in one user message.
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[step {step}] {block.name}({block.input})")
                tool_calls += 1
                content, is_error = run_tool(block.name, block.input, case_dir)
                if is_error:
                    print(f"    error: {content}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                })
        messages.append({"role": "user", "content": results})
    else:
        raise InvestigationError(f"Claude was still calling tools after {MAX_STEPS} steps.", tool_calls)

    if response.stop_reason == "refusal":
        raise InvestigationError("Claude declined the request.", tool_calls)
    if response.stop_reason == "max_tokens":
        raise InvestigationError("The answer was cut off by max_tokens.", tool_calls)
    return "".join(b.text for b in response.content if b.type == "text"), tool_calls


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Who stole the painting?"
    print(solve(question))
