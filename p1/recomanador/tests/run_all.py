"""Executa les proves de totes les iteracions (regressió completa).

Execució:  python -m recomanador.tests.run_all
"""

from recomanador.tests import (test_bloc1, test_bloc2, test_bloc3, test_bloc3b, test_bloc4, test_bloc4b, test_bloc5,
                               test_integracio, test_iter3)

SUITES = [test_bloc1, test_bloc2, test_bloc3, test_bloc3b, test_bloc4, test_bloc4b, test_bloc5, test_integracio, test_iter3]

if __name__ == "__main__":
    raise SystemExit(sum(suite.main() for suite in SUITES))
