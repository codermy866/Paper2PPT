from __future__ import annotations

import argparse
from pathlib import Path

from agent import PaperToPPTAgent
from config import resolve_llm_provider
from llm import MockLLM, create_llm


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an editable PPTX from a research paper PDF.")
    parser.add_argument("--input", help="Path to the input PDF file.")
    parser.add_argument("--output", required=True, help="Path to the output PPTX file.")
    parser.add_argument("--template", help="Optional PPTX template used to overwrite slide slots.")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use bundled sample paper text instead of a real PDF.",
    )
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Enable the mock LLM interface for demo speaker notes generation.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.sample and not args.input:
        parser.error("Please provide --input PDF path, or use --sample.")

    if args.mock_llm:
        llm = MockLLM()
    else:
        provider = resolve_llm_provider()
        llm = create_llm(provider) if provider in {"openai", "mock"} else None
    agent = PaperToPPTAgent(llm=llm)

    sample_path = Path(__file__).parent / "sample_data" / "sample_paper.txt"
    result = agent.run(
        output_path=args.output,
        pdf_path=None if args.sample else args.input,
        text_path=str(sample_path) if args.sample else None,
        template_path=args.template,
    )

    print(f"Generated PPT: {result.output_path}")
    print(f"Paper title: {result.classified.title}")
    print(f"Slides: {len(result.plan.slides)}")


if __name__ == "__main__":
    main()
