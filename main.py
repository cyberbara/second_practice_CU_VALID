import argparse
import sys
import requests
import toml


def positive_int(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue


def get_direct_dependencies(url):
    if 'github.com' in url and '/blob/' in url:
        url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')

    response = requests.get(url)
    response.raise_for_status()

    data = toml.loads(response.text)
    direct_deps = set()
    direct_deps.update(data.get('dependencies', {}).keys())
    direct_deps.update(data.get('dev-dependencies', {}).keys())
    direct_deps.update(data.get('build-dependencies', {}).keys())
    workspace = data.get('workspace', {})
    direct_deps.update(workspace.get('dependencies', {}).keys())
    direct_deps.update(workspace.get('dev-dependencies', {}).keys())
    result = ["dependencies:"]
    for name in sorted(direct_deps):
        result.append(f"  {name}")

    return "\n".join(result)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--package",
        "-p",
        type=str,
        required=True,
    )

    parser.add_argument(
        "--repo",
        "-r",
        type=str,
    )

    parser.add_argument(
        "--test-mode",
        "-t",
        action="store_true",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="graph.png",
    )

    parser.add_argument(
        "--max-depth",
        "-d",
        type=positive_int,
        default=3,
    )

    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        default="",
    )

    args = parser.parse_args()
    if not args.test_mode and not args.repo:
        parser.error("--repo is required when not using test mode")

    print(get_direct_dependencies(args.repo))




if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)