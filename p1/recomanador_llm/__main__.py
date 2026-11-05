"""Xat a la terminal:  python -m recomanador_llm [--verbose]

Cal GPU (la T4 de Colab): el model es carrega en arrencar.
"""

import argparse

from .chat import chat
from .config import MODEL_NAME
from .model import QwenModel


def main():
    parser = argparse.ArgumentParser(prog="python -m recomanador_llm",
                                     description="House advice chatbot with an LLM and tools (system 2).")
    parser.add_argument("--verbose", action="store_true", help="show the tool calls and their results")
    parser.add_argument("--model", default=MODEL_NAME, help=f"Hugging Face model (default: {MODEL_NAME})")
    args = parser.parse_args()
    print(f"Loading {args.model}...")
    chat(QwenModel(name=args.model), verbose=args.verbose)


if __name__ == "__main__":
    main()
