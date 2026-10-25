# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Blender entry point: blender --background --factory-startup --python head_tool.py -- ..."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Targeted head reconstruction on an imported copy')
    parser.add_argument('--input', required=True, help='Triangulated, textured, rigged source GLB')
    parser.add_argument('--profile', required=True, help='Fitted JSON profile')
    parser.add_argument('--output', required=True, help='New output directory')
    parser.add_argument('--render', action='store_true', help='Also render Blender review images')
    parser.add_argument('--validate-only', action='store_true', help='Check profile and input hash without Blender')
    args = parser.parse_args(argv)
    from head_workflow.config import load, validate_input
    config = load(args.profile)
    actual = validate_input(args.input, config)
    if args.validate_only:
        print('Profile and input hash valid:', actual)
        return
    from head_workflow.pipeline import build
    build(args.input, args.profile, args.output, args.render)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
