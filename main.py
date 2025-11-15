import argparse
import sys
import requests
import toml
from typing import Set, Dict, Optional


def positive_int(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue


def get_direct_dependencies(url):
    if 'github.com' in url and '/blob/' in url:
        url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')

    print(f"[*] Fetching direct dependencies from: {url}")
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


def load_test_graph(filepath: str) -> Dict[str, Set[str]]:
    graph = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue

                parts = line.split(':', 1)
                package_name = parts[0].strip()
                dependencies = parts[1].strip().split()

                graph[package_name] = set(dependencies)
    except FileNotFoundError:
        print(f"Error: Test graph file not found at {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to parse test graph file: {e}", file=sys.stderr)
        sys.exit(1)
    return graph


def _print_tree_recursive(
        graph: Dict[str, Set[str]],
        node: str,
        max_depth: int,
        filter_str: str,
        current_depth: int,
        prefix: str,
        path: Set[str],
        parent_prefix: str
):


    if filter_str and filter_str in node:
        return

    print(f"{prefix}{node}", end="")

    if node in path:
        print(" (cyclic)")
        return

    if current_depth >= max_depth:
        print()
        return


    print()

    dependencies = sorted(list(graph.get(node, set())))
    if not dependencies:
        return

    path.add(node)

    for i, dep in enumerate(dependencies):
        is_last = (i == len(dependencies) - 1)

        connector = "└── " if is_last else "├── "
        new_parent_prefix = "    " if is_last else "│   "

        _print_tree_recursive(
            graph=graph,
            node=dep,
            max_depth=max_depth,
            filter_str=filter_str,
            current_depth=current_depth + 1,
            prefix=parent_prefix + connector,
            path=path.copy(),
            parent_prefix=parent_prefix + new_parent_prefix
        )


def run_test_mode(args: argparse.Namespace):

    print(f"[*] Running in Test Mode")
    print(f"[*] Loading graph from: {args.repo}")
    print(f"[*] Analyzing package: {args.package}")
    print(f"[*] Max depth: {args.max_depth}")
    if args.filter:
        print(f"[*] Filtering out packages containing: {args.filter}")
    print("-" * 30)

    graph = load_test_graph(args.repo)

    if args.package not in graph:
        print(f"Error: Package '{args.package}' not found as a root in {args.repo}", file=sys.stderr)
        return

    print(args.package)

    direct_deps = sorted(list(graph.get(args.package, set())))

    path = {args.package}

    for i, dep_name in enumerate(direct_deps):
        is_last = (i == len(direct_deps) - 1)

        connector = "└── " if is_last else "├── "
        parent_prefix = "    " if is_last else "│   "

        _print_tree_recursive(
            graph=graph,
            node=dep_name,
            max_depth=args.max_depth,
            filter_str=args.filter,
            current_depth=1,
            prefix=connector,
            path=path.copy(),
            parent_prefix=parent_prefix
        )


def main():
    parser = argparse.ArgumentParser(description="Dependency Graph Analyzer")

    parser.add_argument(
        "--package",
        "-p",
        type=str,
        required=True,
        help="The root package to analyze (e.g., 'tokio' or 'A' in test mode)"
    )

    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        help="URL to the Cargo.toml file (real mode) or path to the graph file (test mode)"
    )

    parser.add_argument(
        "--test-mode",
        "-t",
        action="store_true",
        help="Enable test mode: --repo becomes a path to a local graph file"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="graph.png",
        help="(Not used in this text-based version)"
    )

    parser.add_argument(
        "--max-depth",
        "-d",
        type=positive_int,
        default=5,
        help="Maximum depth for dependency analysis"
    )

    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        default="",
        help="Substring to filter out packages (case-sensitive)"
    )

    args = parser.parse_args()

    if args.test_mode:
        if not args.repo:
            parser.error("--repo is required for test mode (path to graph file)")
        run_test_mode(args)
    else:
        if not args.repo:
            parser.error("--repo is required when not using test mode (URL to Cargo.toml)")
        print(get_direct_dependencies(args.repo))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)