from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Koryak EyeLink ASC pre/post-onset gaze analysis.")
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    args = parser.parse_args()

    from gaze import write_gaze_outputs
    from utils import load_config

    config = load_config(args.config)
    write_gaze_outputs(config)


if __name__ == "__main__":
    main()
