import sys

from case_closed.agent import solve

if len(sys.argv) < 2 or sys.argv[1] != "solve":
    sys.exit('usage: python -m case_closed solve ["question"]')

question = " ".join(sys.argv[2:]) or "Who stole the painting?"
print(solve(question))
