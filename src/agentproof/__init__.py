"""AgentProof: regression testing for customer-facing AI agents."""

from importlib.metadata import version

# Read the version from the installed package metadata, so pyproject.toml
# is the only place where the version is written.
__version__ = version("agentproof")


def main() -> None:
    print(f"AgentProof {__version__}")
