"""Small wrapper to run the transpiler non-interactively.
Usage:
  python run.py --input pl1code/simple.pli --outdir out
"""
import argparse
import os
import subprocess
import sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="PL/I input file")
    p.add_argument("--outdir", required=False, default=".", help="Output directory")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = p.parse_args()

    env = os.environ.copy()
    if args.debug:
        env["PLIJAVA_DEBUG"] = "1"
    # Set input file for non-interactive mode
    env["PLIJAVA_INPUT_FILE"] = args.input

    # Run plijava.py as a subprocess
    cmd = [sys.executable, "plijava.py"]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, env=env)
    return proc.returncode

if __name__ == '__main__':
    raise SystemExit(main())
