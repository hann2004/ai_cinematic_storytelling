import sys


def main() -> int:
    print(
        "The old Cloudflare text-to-image flow cannot use a reference photo. "
        "Use notebooks/character_reference.ipynb in Kaggle for reference-guided "
        "generation instead.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
