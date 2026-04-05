#!/usr/bin/env python3
"""
Higgsfield AI — Nano Banana Pro Image Generator
Uses the official higgsfield-client SDK to generate images.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# --- Auth ---
HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_API_SECRET = os.getenv("HF_API_SECRET", "")

# Model slugs to try (exact slug may vary on Higgsfield platform)
MODEL_SLUGS = [
    "google/nano-banana-pro/text-to-image",
    "google/nano_banana_pro/text-to-image",
    "google/nano-banana-pro/v1/text-to-image",
]


def ensure_auth():
    """Set env vars for the higgsfield-client SDK."""
    if not HF_API_KEY or not HF_API_SECRET:
        print("HF_API_KEY and HF_API_SECRET must be set in .env")
        sys.exit(1)
    os.environ["HF_API_KEY"] = HF_API_KEY
    os.environ["HF_API_SECRET"] = HF_API_SECRET


def generate_image(
    prompt: str,
    output_dir: str = "generated_images",
    aspect_ratio: str = "1:1",
    resolution: str = "2K",
    model: str | None = None,
) -> str | None:
    """Generate an image with Nano Banana Pro via Higgsfield API."""
    import higgsfield_client

    ensure_auth()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"Generating image with Nano Banana Pro...")
    print(f"  Prompt: {prompt}")
    print(f"  Resolution: {resolution} | Aspect Ratio: {aspect_ratio}")

    slugs = [model] if model else MODEL_SLUGS

    result = None
    for slug in slugs:
        print(f"  Trying model: {slug}")
        try:
            result = higgsfield_client.subscribe(
                slug,
                arguments={
                    "prompt": prompt,
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                },
                on_enqueue=lambda rid: print(f"  Queued: {rid}"),
                on_queue_update=lambda s: print(f"  Status: {type(s).__name__}"),
            )
            break
        except Exception as e:
            print(f"  Failed with {slug}: {e}")
            if model:
                return None
            continue

    if result is None:
        print("All model slugs failed. Check cloud.higgsfield.ai for the correct model path.")
        return None

    # Extract image URL from result
    images = result.get("images", [])
    if not images:
        # Some models return results differently
        print(f"Full response: {result}")
        # Try alternative response formats
        for key in ("output", "result", "data"):
            if key in result and isinstance(result[key], dict):
                images = result[key].get("images", [])
                if images:
                    break
    if not images:
        print("No images in response.")
        return None

    image_url = images[0].get("url") or images[0].get("raw", {}).get("url", "")
    if not image_url:
        print("No image URL in response.")
        return None

    # Download image
    import urllib.request

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nano_banana_pro_{timestamp}.png"
    filepath = Path(output_dir) / filename

    print(f"Downloading image from: {image_url}")
    urllib.request.urlretrieve(image_url, str(filepath))
    print(f"Saved to: {filepath}")

    # Try to display the image
    try:
        from PIL import Image
        img = Image.open(filepath)
        img.show()
        print(f"Image opened! Size: {img.size}")
    except ImportError:
        print("Install Pillow to auto-open images: pip install Pillow")
    except Exception:
        pass

    return str(filepath)


def list_models():
    """Try to discover available models by testing known slugs."""
    import higgsfield_client
    ensure_auth()
    print("Testing known model slugs against the API...\n")
    for slug in MODEL_SLUGS + [
        "bytedance/seedream/v4/text-to-image",
        "flux-pro/kontext/max/text-to-image",
    ]:
        try:
            ctrl = higgsfield_client.submit(slug, {"prompt": "test"})
            print(f"  {slug}: OK (request_id: {ctrl.request_id})")
            ctrl.cancel()
        except Exception as e:
            print(f"  {slug}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Generate images with Nano Banana Pro via Higgsfield")
    subparsers = parser.add_subparsers(dest="command")

    # generate command (default)
    gen_parser = subparsers.add_parser("generate", help="Generate an image")
    gen_parser.add_argument("prompt", help="Text prompt for image generation")
    gen_parser.add_argument("--output-dir", "-o", default="generated_images", help="Output directory")
    gen_parser.add_argument("--aspect-ratio", "-a", default="1:1", choices=["1:1", "16:9", "9:16", "4:3", "3:4"])
    gen_parser.add_argument("--resolution", "-r", default="2K", choices=["1K", "2K", "4K"])
    gen_parser.add_argument("--model", "-m", default=None, help="Override model slug")

    # test-models command
    subparsers.add_parser("test-models", help="Test which model slugs work")

    args = parser.parse_args()

    if args.command == "test-models":
        list_models()
    elif args.command == "generate":
        generate_image(
            prompt=args.prompt,
            output_dir=args.output_dir,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            model=args.model,
        )
    else:
        # Default: treat all args as prompt for backwards compatibility
        parser.print_help()


if __name__ == "__main__":
    main()
