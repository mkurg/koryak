from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Koryak behavioral RT/count analyses.")
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    args = parser.parse_args()

    from behavior import write_behavior_outputs
    from utils import load_config

    config = load_config(args.config)
    write_behavior_outputs(config)


if __name__ == "__main__":
    main()
