import argparse

from case_closed import eval as evaluate
from case_closed.agent import default_provider, solve

parser = argparse.ArgumentParser(prog="python -m case_closed")
parser.add_argument("--provider", choices=["anthropic", "openai"], default=default_provider(),
                    help="which API to use (default: whichever API key is set, Anthropic first)")
commands = parser.add_subparsers(dest="command", required=True)
solve_parser = commands.add_parser("solve", help="investigate Blackwood Manor")
solve_parser.add_argument("question", nargs="*", help='default: "Who stole the painting?"')
commands.add_parser("eval", help="run the detective on every case and print a score")

args = parser.parse_args()
if args.command == "solve":
    print(solve(" ".join(args.question) or "Who stole the painting?", provider=args.provider))
else:
    evaluate.run(provider=args.provider)
