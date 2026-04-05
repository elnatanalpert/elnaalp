Generate an image using the Higgsfield AI API with the Nano Banana Pro model.

## Instructions

1. Read the `.env` file to get `HF_API_KEY` and `HF_API_SECRET`
2. Run `higgsfield_images.py` with the user's prompt
3. Display the resulting image using the Read tool

## Usage

The user will provide an image prompt as the argument: $ARGUMENTS

## Steps

Run this command for text-to-image:

```bash
cd /home/user/elnaalp && python3 higgsfield_images.py generate "$ARGUMENTS"
```

For image-to-image (with a reference photo), add `--image <path>`:

```bash
cd /home/user/elnaalp && python3 higgsfield_images.py generate "$ARGUMENTS" --image <path_to_image>
```

After the image is generated, read and display the image file from `generated_images/` using the Read tool.

If the generation fails, suggest the user run `python3 higgsfield_images.py test-models` to find the correct model slug, then retry with `--model <slug>`.

## Available options

- Resolution: `--resolution 1K|2K|4K` (default: 2K)
- Aspect ratio: `--aspect-ratio 1:1|16:9|9:16|4:3|3:4` (default: 1:1)
- Model override: `--model <slug>`
- Reference image: `--image <path>` (for image-to-image generation)
