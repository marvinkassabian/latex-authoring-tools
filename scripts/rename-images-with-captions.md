# Image Rename Script

Automatically rename pandoc images from `imageXX` to semantic filenames using AI captioning.

## Features

- Uses Hugging Face **BLIP** (vision-language model) for image captioning
- Converts captions to clean **kebab-case** filenames
- Preserves original image number as prefix (e.g., `42-tourniquet-being-applied.jpg`)
- **Dry-run mode** by default (safe to test)
- Skips invalid/already-processed files gracefully

## Installation

```bash
pip install -r requirements.txt
```

For GPU acceleration (recommended for multiple images):
```bash
# CUDA-enabled GPU
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Apple Silicon (MPS)
# torch with MPS support is included in recent versions
```

## Usage

### Dry-run (test without modifying files)
```bash
python scripts/rename-images-with-captions.py --dry-run figures/media
```

### Actual rename (after verifying dry-run output)
```bash
python scripts/rename-images-with-captions.py figures/media
```

### Custom model
```bash
# Use larger/more accurate model
python scripts/rename-images-with-captions.py --model Salesforce/blip-image-captioning-large figures/media
```

### GPU acceleration
```bash
python scripts/rename-images-with-captions.py --device cuda figures/media
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | True (implied) | Show plan without modifying |
| `--model` | `Salesforce/blip-image-captioning-base` | Hugging Face model ID |
| `--device` | `cpu` | `cpu`, `cuda`, or `mps` |

## Output Example

```
[1/5] Processing: image42.png
  Caption: tourniquet being applied to arm
  Would rename to: 42-tourniquet-being-applied.png

[2/5] Processing: image50.jpg
  Caption: posterior tibial pulse location
  Would rename to: 50-posterior-tibial-pulse-location.jpg
```

## Models Available

| Model | Size | Quality | Speed |
|-------|------|---------|-------|
| `Salesforce/blip-image-captioning-base` | ~990MB | Good | Fast |
| `Salesforce/blip-image-captioning-large` | ~2.6GB | Better | Slower |

## Notes

- First run downloads model (~1GB) from Hugging Face
- Captions truncated to ~50 chars for readable filenames
- Kebab-case conversion removes special characters, lowercases
- Always test with `--dry-run` first
- Skips files that don't match `imageXX` pattern
- Creates backups of original names (prefix preserved as number)

## Troubleshooting

**Out of memory:** Use `--device cpu` (slower but works on any machine)

**Model download slow:** Set `HF_HOME=/path/to/cache` before running

**No CUDA/GPU detected:** Ensure PyTorch CUDA version matches your GPU driver
