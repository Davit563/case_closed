"""A hand-written tool-use loop: Claude investigates the case by reading evidence files."""

import sys
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5-5"
CASE_DIR = Path(__file__).resolve().parents[2] / "cases" / "blackwood_manor"
HIDDEN = {"solution.json"}  # the detective must not read the answer
MAX_STEPS = 15  # stop a runaway investigation

SYSTEM = (
    "You are a meticulous detective. Gather evidence before accusing anyone. "
    "Cite the files that prove your answer."
)

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


def list_evidence():
    names = [p.relative_to(CASE_DIR).as_posix() for p in CASE_DIR.rglob("*") if p.is_file()]
    return "\n".join(sorted(n for n in names if n not in HIDDEN))


def read_evidence(name):
    file = (CASE_DIR / name).resolve()
    if CASE_DIR not in file.parents or file.name in HIDDEN or not file.is_file():
        raise ValueError(f"No evidence file named {name!r}. Call list_evidence to see the files.")
    return file.read_text()


def search_evidence(keyword):
    matches = []
    for name in list_evidence().splitlines():
        for number, line in enumerate(read_evidence(name).splitlines(), start=1):
            if keyword.lower() in line.lower():
                matches.append(f"{name}:{number}: {line.strip()}")
    return "\n".join(matches) or f"No lines contain {keyword!r}."


def run_tool(tool_name, tool_input):
    """Run one tool call. Returns (content, is_error)."""
    try:
        if tool_name == "list_evidence":
            return list_evidence(), False
        if tool_name == "read_evidence":
            return read_evidence(tool_input["name"]), False
        if tool_name == "search_evidence":
            return search_evidence(tool_input["keyword"]), False
        return f"Unknown tool {tool_name!r}.", True
    except (KeyError, ValueError) as e:
        return str(e), True


def solve(question, client=None):
    client = client or anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]

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
                content, is_error = run_tool(block.name, block.input)
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
        raise RuntimeError(f"Claude was still calling tools after {MAX_STEPS} steps.")

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined the request.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The answer was cut off by max_tokens.")
    return "".join(b.text for b in response.content if b.type == "text")


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Who stole the painting?"
    print(solve(question))
