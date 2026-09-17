import argparse
import json
from pathlib import Path

from .config import Settings
from .index import Index, build_index
from .pipeline import Pipeline
from .providers import Provider


def main():
    parser = argparse.ArgumentParser(prog="obbian-rag")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--dataset", type=Path, default=Path("evals/golden.jsonl"))
    evaluate.add_argument("--report", type=Path, default=Path("reports/evaluation.json"))
    evaluate.add_argument("--split", choices=["dev", "test", "all"], default="test")
    evaluate.add_argument("--min-pass-rate", type=float, default=0.9)
    args = parser.parse_args()
    settings = Settings()
    provider = Provider(settings)
    index = None
    try:
        if args.command == "ingest":
            print(json.dumps({"index_version": build_index(settings, provider)}))
            return
        index = Index(settings)
        pipeline = Pipeline(settings, provider, index)
        if args.command == "ask":
            print(pipeline.ask(args.question).model_dump_json(indent=2))
        else:
            from .evaluate import evaluate

            result = evaluate(pipeline, args.dataset, args.report, args.split)
            print(json.dumps(result, indent=2))
            if result["pass_rate"] < args.min_pass_rate:
                raise SystemExit(1)
    finally:
        if index:
            index.close()
        provider.close()


if __name__ == "__main__":
    main()
