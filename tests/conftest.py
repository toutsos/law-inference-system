"""Suite-wide pytest configuration: the ``--update-golden`` switch.

``conftest.py`` is pytest's hook file — loaded automatically for every test
under this directory, no import needed. Its nearest Java relative is a JUnit 5
extension registered for the whole suite.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite golden files from the current output instead of comparing.",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Whether this run accepts the current output as the new golden files.

    Off by default, and deliberately a command-line flag rather than an
    environment variable: accepting a change to what the pipeline produces
    should be something typed on purpose, once, and visible in the shell
    history — never a setting left on.
    """
    return bool(request.config.getoption("--update-golden"))
