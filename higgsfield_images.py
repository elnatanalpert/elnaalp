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
) -> str | None:
    """Generate an image with Nano Banana Pro via Higgsfield API."""
    import higgsfield_client

    ensure_auth()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"Generating image with Nano Banana Pro...")
    print(f"  Prompt: {prompt}")
    print(f"  Resolution: {resolution} | Aspect Ratio: {aspect_ratio}")

    try:
        result = higgsfield_client.subscribe(
            "google/nano-banana-pro/text-to-image",
            arguments={
                "prompt": prompt,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
            },
        )
    except Exception as e:
        print(f"Error generating image: {e}")
        return None

    # Extract image URL from result
    images = result.get("images", [])
    if not images:
        print("No images returned from API.")
        print(f"Full response: {result}")
        return None

    image_url = images[0].get("url", "")
    if not image_url:
        print("No image URL in response.")
        return None

    # Download image
    import urllib.request

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nano_banana_pro_{timestamp}.png"
    filepath = Path(output_dir) / filename

    print(f"Downloading image...")
    urllib.request.urlretrieve(image_url, str(filepath))
    print(f"Saved to: {filepath}")
    return str(filepath)


def main():
    parser = argparse.ArgumentParser(description="Generate images with Nano Banana Pro via Higgsfield")
    parser.add_argument("prompt", help="Text prompt for image generation")
    parser.add_argument("--output-dir", "-o", default="generated_images", help="Output directory")
    parser.add_argument("--aspect-ratio", "-a", default="1:1", choices=["1:1", "16:9", "9:16", "4:3", "3:4"])
    parser.add_argument("--resolution", "-r", default="2K", choices=["1K", "2K", "4K"])
    args = parser.parse_args()

    generate_image(
        prompt=args.prompt,
        output_dir=args.output_dir,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
    )


if __name__ == "__main__":
    main()
