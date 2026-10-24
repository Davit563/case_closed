"""The same detective loop as agent.py, written for OpenAI's Chat Completions API.

The tools, system prompt, step limit and errors are shared with agent.py; only the
message format differs:
- tools are wrapped as {"type": "function", "function": {...}}
- Claude's stop_reason == "tool_use" becomes finish_reason == "tool_calls"
- tool arguments arrive as a JSON string, not a dict
- each result goes back as its own {"role": "tool"} message, not one user message
"""

import json
import os

import openai

from case_closed.agent import CASE_DIR, MAX_STEPS, SYSTEM, TOOLS, InvestigationError, run_tool

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }
    for tool in TOOLS
]


def investigate(question, client=None, case_dir=CASE_DIR):
    """Run the tool-use loop on one case. Returns (answer, number of tool calls)."""
    client = client or openai.OpenAI()
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    tool_calls = 0

    for step in range(1, MAX_STEPS + 1):
        response = client.chat.completions.create(model=MODEL, tools=OPENAI_TOOLS, messages=messages)
        choice = response.choices[0]
        message = choice.message

        # Keep the model's reply (including its tool calls) in the history.
        reply = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            reply["tool_calls"] = [
                {"id": call.id, "type": "function",
                 "function": {"name": call.function.name, "arguments": call.function.arguments}}
                for call in message.tool_calls
            ]
        messages.append(reply)

        if choice.finish_reason != "tool_calls":
            break

        # Run every tool the model asked for; each result is its own "tool" message.
        for call in message.tool_calls:
            tool_calls += 1
            print(f"[step {step}] {call.function.name}({call.function.arguments})")
            try:
                tool_input = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                content, is_error = "Arguments were not valid JSON.", True
            else:
                content, is_error = run_tool(call.function.name, tool_input, case_dir)
            if is_error:
                print(f"    error: {content}")
                content = f"Error: {content}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
    else:
        raise InvestigationError(f"The model was still calling tools after {MAX_STEPS} steps.", tool_calls)

    if message.refusal or choice.finish_reason == "content_filter":
        raise InvestigationError("The model declined the request.", tool_calls)
    if choice.finish_reason == "length":
        raise InvestigationError("The answer was cut off by the length limit.", tool_calls)
    return message.content or "", tool_calls
