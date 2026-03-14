#!/usr/bin/env python3
"""Extract XML parts, embedded media, and drawing metadata from a DOCX file.

Usage:
    python scripts/dump-docx-contents.py path/to/file.docx
    python scripts/dump-docx-contents.py path/to/file.docx --output-dir path/to/output-root
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile


XML_EXTENSIONS = {".xml", ".rels"}

DOCX_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}

PACKAGE_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
OFFICE_REL_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "docx-dump"


def is_xml_part(zip_path: PurePosixPath) -> bool:
    return zip_path.suffix.lower() in XML_EXTENSIONS


def is_media_part(zip_path: PurePosixPath) -> bool:
    return len(zip_path.parts) >= 2 and zip_path.parts[:2] == ("word", "media")


def paragraph_text(paragraph: ET.Element) -> str:
    text = "".join(node.text or "" for node in paragraph.findall(".//w:t", DOCX_NS))
    return re.sub(r"\s+", " ", text).strip()


def resolve_relationship_target(target: str, base_dir: PurePosixPath) -> PurePosixPath:
    if target.startswith("/"):
        normalized = posixpath.normpath(target.lstrip("/"))
    else:
        normalized = posixpath.normpath(posixpath.join(str(base_dir), target))
    return PurePosixPath(normalized)


def parse_relationships(rels_data: bytes, base_dir: PurePosixPath) -> dict[str, PurePosixPath]:
    rels_root = ET.fromstring(rels_data)
    relmap: dict[str, PurePosixPath] = {}

    for rel in rels_root.findall(f"{PACKAGE_REL_NS}Relationship"):
        if rel.attrib.get("TargetMode") == "External":
            continue

        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if not rel_id or not target:
            continue

        relmap[rel_id] = resolve_relationship_target(target, base_dir)

    return relmap


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def build_drawing_report(document_data: bytes, rels_data: bytes) -> list[dict[str, object]]:
    relmap = parse_relationships(rels_data, PurePosixPath("word"))
    root = ET.fromstring(document_data)
    paragraphs = root.findall(".//w:body/w:p", DOCX_NS)
    report: list[dict[str, object]] = []

    for index, paragraph in enumerate(paragraphs):
        text = paragraph_text(paragraph)
        choice_uris: list[str] = []
        choice_media_targets: list[str] = []
        fallback_media_targets: list[str] = []
        fallback_names: list[str] = []

        for choice in paragraph.findall(".//mc:Choice", DOCX_NS):
            for graphic_data in choice.findall(".//a:graphicData", DOCX_NS):
                uri = graphic_data.attrib.get("uri")
                if uri:
                    choice_uris.append(uri)

            for blip in choice.findall(".//a:blip", DOCX_NS):
                rel_id = blip.attrib.get(OFFICE_REL_EMBED)
                if not rel_id or rel_id not in relmap:
                    continue
                choice_media_targets.append(str(relmap[rel_id]))

        for fallback in paragraph.findall(".//mc:Fallback", DOCX_NS):
            for c_nv_pr in fallback.findall(".//pic:cNvPr", DOCX_NS):
                name = c_nv_pr.attrib.get("name")
                if name:
                    fallback_names.append(name)

            for blip in fallback.findall(".//a:blip", DOCX_NS):
                rel_id = blip.attrib.get(OFFICE_REL_EMBED)
                if not rel_id or rel_id not in relmap:
                    continue
                fallback_media_targets.append(str(relmap[rel_id]))

        if not choice_uris and not fallback_names and not fallback_media_targets:
            continue

        previous_text = next(
            (paragraph_text(paragraphs[i]) for i in range(index - 1, -1, -1) if paragraph_text(paragraphs[i])),
            "",
        )
        next_text = next(
            (paragraph_text(paragraphs[i]) for i in range(index + 1, len(paragraphs)) if paragraph_text(paragraphs[i])),
            "",
        )

        report.append(
            {
                "paragraph_index": index,
                "text": text,
                "previous_text": previous_text,
                "next_text": next_text,
                "choice_uris": unique_strings(choice_uris),
                "choice_media_targets": unique_strings(choice_media_targets),
                "fallback_names": unique_strings(fallback_names),
                "fallback_media_targets": unique_strings(fallback_media_targets),
            }
        )

    return report


def write_drawing_report(report: list[dict[str, object]], output_dir: Path) -> None:
    json_path = output_dir / "drawing-report.json"
    markdown_path = output_dir / "drawing-report.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# DOCX Drawing Report",
        "",
        "This report lists Word or Google-style drawing blocks found in the main document body.",
        "",
    ]

    for entry in report:
        lines.extend(
            [
                f"## Paragraph {entry['paragraph_index']}",
                "",
                f"- Text: {entry['text'] or '[no paragraph text]'}",
                f"- Previous: {entry['previous_text'] or '[none]'}",
                f"- Next: {entry['next_text'] or '[none]'}",
                f"- Choice URIs: {', '.join(entry['choice_uris']) or '[none]'}",
                f"- Choice media: {', '.join(entry['choice_media_targets']) or '[none]'}",
                f"- Fallback names: {', '.join(entry['fallback_names']) or '[none]'}",
                f"- Fallback media: {', '.join(entry['fallback_media_targets']) or '[none]'}",
                "",
            ]
        )

    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def extract_docx_contents(docx_path: Path, output_dir: Path) -> tuple[int, int, int]:
    xml_dir = output_dir / "xml"
    images_dir = output_dir / "images"
    xml_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    xml_count = 0
    media_count = 0
    document_data: bytes | None = None
    document_rels_data: bytes | None = None

    with ZipFile(docx_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue

            zip_path = PurePosixPath(info.filename)
            data = archive.read(info.filename)

            if is_xml_part(zip_path):
                target = xml_dir / Path(*zip_path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                xml_count += 1

                if info.filename == "word/document.xml":
                    document_data = data
                elif info.filename == "word/_rels/document.xml.rels":
                    document_rels_data = data
                continue

            if is_media_part(zip_path):
                relative_media_path = Path(*zip_path.parts[2:])
                target = images_dir / relative_media_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                media_count += 1

    report_count = 0
    if document_data and document_rels_data:
        report = build_drawing_report(document_data, document_rels_data)
        write_drawing_report(report, output_dir)
        report_count = len(report)

    return xml_count, media_count, report_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dump XML parts, embedded media, and drawing metadata from a DOCX file."
    )
    parser.add_argument("docx_path", help="Path to the .docx file to extract")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory where the dump folder should be created (default: next to the DOCX)"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    docx_path = Path(args.docx_path).expanduser().resolve()
    if not docx_path.is_file():
        print(f"Error: DOCX file not found: {docx_path}", file=sys.stderr)
        return 1

    base_output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else docx_path.parent
    )
    output_dir = base_output_dir / slugify(docx_path.stem)

    try:
        xml_count, media_count, report_count = extract_docx_contents(docx_path, output_dir)
    except BadZipFile:
        print(f"Error: Not a valid DOCX/ZIP file: {docx_path}", file=sys.stderr)
        return 1

    print(f"DOCX: {docx_path}")
    print(f"Output: {output_dir}")
    print(f"XML files written: {xml_count}")
    print(f"Media files written: {media_count}")
    print(f"Drawing report entries: {report_count}")
    print(f"XML directory: {output_dir / 'xml'}")
    print(f"Media directory: {output_dir / 'images'}")
    print(f"Drawing report: {output_dir / 'drawing-report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())