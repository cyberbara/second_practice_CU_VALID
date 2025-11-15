import argparse
import sys


def positive_int(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue


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

    # Вывод всех параметров
    print("Configured parameters:")
    print(f"  Package: {args.package}")
    print(f"  Repository: {args.repo}")
    print(f"  Test mode: {args.test_mode}")
    print(f"  Output file: {args.output}")
    print(f"  Max depth: {args.max_depth}")
    print(f"  Filter: {args.filter}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)