# latex-authoring-tools

Generic LaTeX authoring helper scripts reusable across document repositories.

## Tools

- scripts/caption-image-files.py
- scripts/extract-docx-contents.py

Backward-compatible aliases are kept during migration:

- scripts/rename-images-with-captions.py
- scripts/dump-docx-contents.py

## Usage

python3 scripts/caption-image-files.py --dry-run path/to/images
python3 scripts/extract-docx-contents.py path/to/file.docx

No project-specific defaults should be embedded here.
Caller repositories supply paths, policies, and naming conventions.
