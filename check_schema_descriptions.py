"""List API operations that have no summary, description or tag in the Swagger schema.

Usage:
    python manage.py spectacular --file schema.yml
    python check_schema_descriptions.py schema.yml
"""
import sys

import yaml

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def main(path):
    with open(path, encoding="utf-8") as handle:
        schema = yaml.safe_load(handle)

    problems = []
    total = 0
    for url, item in schema.get("paths", {}).items():
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            total += 1
            missing = [
                field for field in ("summary", "description", "tags")
                if not operation.get(field)
            ]
            if missing:
                problems.append(f"{method.upper():6} {url}  missing: {', '.join(missing)}")

    print(f"{total} operations checked.")
    if problems:
        print(f"{len(problems)} need documentation:")
        print("\n".join(problems))
        return 1
    print("Every operation has a summary, description and tag.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))