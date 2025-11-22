import argparse
import sys
import requests
from typing import Set, Dict, Optional, List
from functools import lru_cache
import json

CRATES_IO_API_BASE = "https://crates.io/api/v1"


def positive_int(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue


@lru_cache(maxsize=None)
def get_dependencies_from_api(crate_name: str) -> Optional[List[str]]:
    try:
        info_url = f"{CRATES_IO_API_BASE}/crates/{crate_name}"
        response = requests.get(info_url,
                                headers={'User-Agent': 'Dependency-Graph-Analyzer (contact: user@example.com)'},
                                timeout=10)
        response.raise_for_status()
        crate_info = response.json()

        latest_version = crate_info.get('crate', {}).get('max_stable_version')
        if not latest_version:
            latest_version = crate_info.get('crate', {}).get('newest_version')

        if not latest_version:
            return None

        deps_url = f"{CRATES_IO_API_BASE}/crates/{crate_name}/{latest_version}/dependencies"
        response = requests.get(deps_url,
                                headers={'User-Agent': 'Dependency-Graph-Analyzer (contact: user@example.com)'},
                                timeout=10)
        response.raise_for_status()
        deps_data = response.json()

        dependencies = []
        for dep in deps_data.get('dependencies', []):
            if dep['kind'] == 'normal':
                dependencies.append(dep['crate_id'])

        return sorted(dependencies)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"[-] Error: Crate '{crate_name}' not found on crates.io.", file=sys.stderr)
        else:
            print(f"[-] HTTP Error fetching dependencies for {crate_name}: {e}", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"[-] Network Error fetching dependencies for {crate_name}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[-] An unexpected error occurred for {crate_name}: {e}", file=sys.stderr)
        return None


def _print_tree_recursive_api(
        root_name: str,
        max_depth: int,
        current_depth: int,
        prefix: str,
        path: Set[str],
        parent_prefix: str
):
    print(f"{prefix}{root_name}", end="")

    if root_name in path:
        print(" (cyclic)")
        return

    if current_depth >= max_depth:
        print()
        return

    print()

    dependencies = get_dependencies_from_api(root_name)

    if not dependencies:
        return

    new_path = path.copy()
    new_path.add(root_name)

    for i, dep in enumerate(dependencies):
        is_last = (i == len(dependencies) - 1)

        connector = "└── " if is_last else "├── "
        new_parent_prefix = "    " if is_last else "│   "

        _print_tree_recursive_api(
            root_name=dep,
            max_depth=max_depth,
            current_depth=current_depth + 1,
            prefix=parent_prefix + connector,
            path=new_path,
            parent_prefix=parent_prefix + new_parent_prefix
        )


def run_real_mode(args: argparse.Namespace):
    print(f"[*] Running in Real Mode (Crates.io API)")
    print(f"[*] Analyzing package: {args.package}")
    print(f"[*] Max depth: {args.max_depth}")
    print("-" * 30)

    initial_deps = get_dependencies_from_api(args.package)

    print(args.package)

    if not initial_deps:
        return

    path = {args.package}

    for i, dep_name in enumerate(initial_deps):
        is_last = (i == len(initial_deps) - 1)

        connector = "└── " if is_last else "├── "
        parent_prefix = "    " if is_last else "│   "

        _print_tree_recursive_api(
            root_name=dep_name,
            max_depth=args.max_depth,
            current_depth=1,
            prefix=connector,
            path=path.copy(),
            parent_prefix=parent_prefix
        )


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
        current_depth: int,
        prefix: str,
        path: Set[str],
        parent_prefix: str
):
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

    new_path = path.copy()
    new_path.add(node)

    for i, dep in enumerate(dependencies):
        is_last = (i == len(dependencies) - 1)

        connector = "└── " if is_last else "├── "
        new_parent_prefix = "    " if is_last else "│   "

        _print_tree_recursive(
            graph=graph,
            node=dep,
            max_depth=max_depth,
            current_depth=current_depth + 1,
            prefix=parent_prefix + connector,
            path=new_path,
            parent_prefix=parent_prefix + new_parent_prefix
        )


def run_test_mode(args: argparse.Namespace):
    print(f"[*] Running in Test Mode")
    print(f"[*] Loading graph from: {args.repo}")
    print(f"[*] Analyzing package: {args.package}")
    print(f"[*] Max depth: {args.max_depth}")
    print("-" * 30)

    graph = load_test_graph(args.repo)

    if args.package not in graph:
        print(f"Error: Root package '{args.package}' not found in the graph file.", file=sys.stderr)
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
            current_depth=1,
            prefix=connector,
            path=path.copy(),
            parent_prefix=parent_prefix
        )


def main():
    parser = argparse.ArgumentParser(description="Dependency Graph Analyzer (Crates.io & Test Mode)")

    parser.add_argument(
        "--package",
        "-p",
        type=str,
        required=True,
        help="The root package (crate) to analyze (e.g., 'tokio' or 'A' in test mode)"
    )

    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        help="Path to the graph file (test mode) or (Ignored in real mode)"
    )

    parser.add_argument(
        "--test-mode",
        "-t",
        action="store_true",
        help="Enable test mode: --repo must be a path to a local graph file"
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
        run_real_mode(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if "SystemExit" not in str(type(e)):
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)