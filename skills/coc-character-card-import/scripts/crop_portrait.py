#!/usr/bin/env python3
"""Crop a user-selected rectangle without overwriting any existing output."""
from __future__ import annotations

import argparse
import io
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--box', required=True, type=int, nargs=4, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        from PIL import Image, ImageOps
    except ImportError:
        print('ERROR: Pillow is required; install it in an isolated Python environment.', file=sys.stderr)
        return 2
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError(f'Output already exists: {args.output}')
        with Image.open(args.source) as original:
            image = ImageOps.exif_transpose(original)
            left, top, right, bottom = args.box
            if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                raise ValueError(f'Box must be within the oriented image ({image.width}x{image.height}).')
            portrait = image.crop((left, top, right, bottom))
            if portrait.mode not in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA', 'I', 'I;16'):
                portrait = portrait.convert('RGB')
            portrait.info.clear()
            payload = io.BytesIO()
            portrait.save(payload, format='PNG')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with args.output.open('xb') as stream:
                created = True
                stream.write(payload.getvalue())
        except BaseException:
            # Close the file before removing a partial write (also works on Windows).
            if created:
                args.output.unlink(missing_ok=True)
            raise
        print(f'Saved {right-left}x{bottom-top} PNG: {args.output}')
        return 0
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
