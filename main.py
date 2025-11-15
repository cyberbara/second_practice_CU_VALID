import argparse
import sys
import requests
import toml
from typing import Set, Dict, Optional, List


def positive_int(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue


def get_direct_dependencies(url: str) -> str:
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
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or ':' not in line:
                    continue

                parts = line.split(':', 1)
                package_name = parts[0].strip()
                dependencies = parts[1].strip().split()

                if package_name not in graph:
                    graph[package_name] = set()

                graph[package_name].update(set(dependencies))

                for dep in dependencies:
                    if dep not in graph:
                        graph[dep] = set()

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

    dependencies = sorted([dep for dep in graph.get(node, set()) if not (filter_str and filter_str in dep)])

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


def get_loading_order_dfs(
        graph: Dict[str, Set[str]],
        start_node: str,
        filter_str: str,
        order: List[str],
        visited: Set[str],
        recursion_stack: Set[str],
        cycles: Set[str]
) -> None:
    if filter_str and filter_str in start_node:
        return

    if start_node in recursion_stack:
        cycles.add(start_node)
        return

    if start_node in visited:
        return

    recursion_stack.add(start_node)

    dependencies = sorted([dep for dep in graph.get(start_node, set()) if not (filter_str and filter_str in dep)])

    for dep in dependencies:
        get_loading_order_dfs(graph, dep, filter_str, order, visited, recursion_stack, cycles)

    recursion_stack.remove(start_node)
    visited.add(start_node)

    order.append(start_node)


def run_loading_order_mode(args: argparse.Namespace):


    graph = load_test_graph(args.repo)

    if args.package not in graph:
        print(f"Error: Package '{args.package}' not found in the graph.", file=sys.stderr)
        return

    loading_order = []
    visited = set()
    recursion_stack = set()
    cycles = set()

    get_loading_order_dfs(graph, args.package, args.filter, loading_order, visited, recursion_stack, cycles)

    print("\n--- Calculated Dependency Loading Order (Reverse Topological Sort) ---")

    print("Packages loaded (built) in this order (Deepest dependencies first):")
    print("-> ".join(loading_order))

    if cycles:
        print("\nNote: The graph contains cycles.")

        all_nodes_in_order = set(loading_order)
        cycle_nodes_in_graph = cycles.intersection(all_nodes_in_order)

        if cycle_nodes_in_graph:
            print(
                f"A cycle was detected involving one or more packages in the order: {', '.join(sorted(list(cycle_nodes_in_graph)))}")
        else:
            print("A cycle was detected in a filtered-out or already processed path.")

def run_test_mode(args: argparse.Namespace):
    print(f"[*] Running in DFS Tree Mode (Stage 3)")
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

    direct_deps = sorted([dep for dep in graph.get(args.package, set()) if not (args.filter and args.filter in dep)])

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
        help="Maximum depth for dependency analysis (Stage 3)"
    )

    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        default="",
        help="Substring to filter out packages (case-sensitive)"
    )

    parser.add_argument(
        "--loading-order",
        "-l",
        action="store_true",
        help="Run in loading order mode (Stage 4), performing reverse topological sort on dependencies."
    )

    args = parser.parse_args()

    if args.loading_order and not args.test_mode:
        print(
            "Error: Loading Order analysis (Stage 4) requires a full graph definition and is supported only in Test Mode (-t).",
            file=sys.stderr)
        sys.exit(1)

    if (args.test_mode or args.loading_order) and not args.repo:
        parser.error("--repo is required for test mode (path to graph file)")

    if not args.test_mode and not args.loading_order and not args.repo:
        parser.error("--repo is required when not using test mode (URL to Cargo.toml)")

    if args.loading_order:
        run_loading_order_mode(args)
    elif args.test_mode:
        run_test_mode(args)
    else:
        print(get_direct_dependencies(args.repo))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)