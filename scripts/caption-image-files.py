#!/usr/bin/env python3
"""Generate captions for images and rename files with normalized slugs."""

import argparse
import re
import sys
from pathlib import Path

try:
    from PIL import Image
    from transformers import BlipForConditionalGeneration, BlipProcessor
except ImportError:
    print("Error: Required packages not found.")
    print("Install with: pip install pillow transformers torch torchvision")
    sys.exit(1)


def to_kebab_case(text: str, max_length: int = 50) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s\-]", "", text)
    text = text.lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    if len(text) > max_length:
        text = text[:max_length].rstrip("-")
    return text


def caption_image(image_path: Path, processor, model) -> str | None:
    try:
        image = Image.open(image_path).convert("RGB")
        inputs = processor(image, return_tensors="pt")
        out = model.generate(**inputs, max_length=50)
        return processor.decode(out[0], skip_special_tokens=True)
    except Exception as exc:
        print(f"Warning: Could not caption {image_path}: {exc}")
        return None


def build_target_name(image_path: Path, caption: str, keep_numeric_prefix: bool, index: int) -> str:
    slug = to_kebab_case(caption) or f"captioned-image-{index}"
    prefix = ""
    if keep_numeric_prefix:
        number_match = re.search(r"(\d+)$", image_path.stem)
        if number_match:
            prefix = f"{number_match.group(1)}-"
    return f"{prefix}{slug}{image_path.suffix}"


def unique_path(directory: Path, candidate_name: str) -> Path:
    candidate = directory / candidate_name
    if not candidate.exists():
        return candidate

    stem = Path(candidate_name).stem
    suffix = Path(candidate_name).suffix
    counter = 2
    while True:
        attempt = directory / f"{stem}-{counter}{suffix}"
        if not attempt.exists():
            return attempt
        counter += 1


def rename_images(
    image_dir: Path,
    model_name: str,
    dry_run: bool,
    keep_numeric_prefix: bool,
) -> int:
    if not image_dir.is_dir():
        print(f"Error: {image_dir} is not a directory")
        return 1

    print(f"Loading model: {model_name}")
    processor = BlipProcessor.from_pretrained(model_name)
    model = BlipForConditionalGeneration.from_pretrained(model_name)

    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    images = sorted([p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in image_extensions])

    if not images:
        print(f"No images found in {image_dir}")
        return 0

    print(f"Found {len(images)} images")
    print(f"Dry run: {dry_run}\n")

    for idx, image_path in enumerate(images, 1):
        print(f"[{idx}/{len(images)}] Processing: {image_path.name}")
        caption = caption_image(image_path, processor, model)
        if not caption:
            print("  Skipped (no caption)\n")
            continue

        print(f"  Caption: {caption}")
        target_name = build_target_name(image_path, caption, keep_numeric_prefix, idx)
        target_path = unique_path(image_dir, target_name)

        if dry_run:
            print(f"  [DRY RUN] Would rename to: {target_path.name}\n")
            continue

        image_path.rename(target_path)
        print(f"  Renamed to: {target_path.name}\n")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename image files using generated captions",
    )
    parser.add_argument(
        "image_dir",
        nargs="?",
        default="images",
        help="Directory containing images (default: images)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned renames without modifying files",
    )
    parser.add_argument(
        "--model",
        default="Salesforce/blip-image-captioning-base",
        help="Hugging Face model ID for caption generation",
    )
    parser.add_argument(
        "--keep-numeric-prefix",
        action="store_true",
        help="Preserve trailing numeric token from original filename as prefix",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return rename_images(
        image_dir=Path(args.image_dir),
        model_name=args.model,
        dry_run=args.dry_run,
        keep_numeric_prefix=args.keep_numeric_prefix,
    )


if __name__ == "__main__":
    raise SystemExit(main())
