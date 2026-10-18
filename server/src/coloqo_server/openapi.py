"""Write the API description: ``python -m coloqo_server.openapi > ../protocol/openapi.json``."""

import json
import sys

from coloqo_server.app import create_app
from coloqo_server.settings import Settings


def main() -> None:
    """Print the OpenAPI description of the API to standard output (decision 0002)."""
    spec = create_app(Settings(web_dir=None)).openapi()
    json.dump(spec, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
