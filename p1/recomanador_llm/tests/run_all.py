"""Totes les proves del sistema 2 (sense GPU):  python -m recomanador_llm.tests.run_all"""

from recomanador_llm.tests import test_agent, test_evaluation


def main():
    failures = test_agent.main()
    print()
    failures += test_evaluation.main()
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
