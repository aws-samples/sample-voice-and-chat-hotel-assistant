#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Hotel Knowledge Base Metadata Generation Script

This script generates .metadata.json files for all hotel documents in the knowledge base.
It creates metadata files that will be used by Amazon Bedrock Knowledge Base for
hotel-specific filtering and document categorization.

Usage:
    python hotel_data/scripts/generate_metadata.py

The script will process all markdown files in hotel-knowledge-base/
and generate corresponding .metadata.json files.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict


def get_hotel_mapping() -> Dict[str, Dict[str, str]]:
    """
    Returns mapping of hotel directory names to hotel IDs and names.

    Returns:
        Dict mapping directory names to hotel info (id and name)
    """
    return {
        "paraiso-vallarta": {
            "id": "H-PVR-002",
            "name": "Paraíso Vallarta Resort & Spa",
        },
        "paraiso-tulum": {"id": "H-PTL-003", "name": "Paraíso Tulum Eco-Luxury Resort"},
        "paraiso-los-cabos": {
            "id": "H-PLC-004",
            "name": "Paraíso Los Cabos Desert & Ocean Resort",
        },
        "grand-paraiso-resort-spa": {
            "id": "H-GPR-001",
            "name": "Grand Paraíso Resort & Spa",
        },
    }


def categorize_document(filename: str) -> str:
    """
    Categorize document based on filename.

    Args:
        filename: The markdown filename (without extension)

    Returns:
        Category string for the document
    """
    category_mapping = {
        "informacion-general": "general-info",
        "ubicacion-contacto": "location-contact",
        "habitaciones-suites": "rooms-suites",
        "gastronomia": "dining-gastronomy",
        "instalaciones": "facilities-amenities",
        "politicas-servicios": "policies-services",
        "operaciones-rendimiento": "operations-performance",
    }

    return category_mapping.get(filename, "general-info")


def format_hotel_name(hotel_dir: str) -> str:
    """
    Format hotel directory name to human-readable hotel name.

    Args:
        hotel_dir: Hotel directory name

    Returns:
        Formatted hotel name
    """
    hotel_mapping = get_hotel_mapping()
    return hotel_mapping.get(hotel_dir, {}).get(
        "name", hotel_dir.replace("-", " ").title()
    )


def generate_metadata_for_file(
    hotel_dir: str, filename: str, hotel_mapping: Dict[str, Dict[str, str]]
) -> Dict:
    """
    Generate metadata for a single markdown file.

    Args:
        hotel_dir: Hotel directory name
        filename: Markdown filename (with .md extension)
        hotel_mapping: Hotel directory to ID/name mapping

    Returns:
        Metadata dictionary for the file
    """
    if hotel_dir not in hotel_mapping:
        raise ValueError(f"Unknown hotel directory: {hotel_dir}")

    hotel_info = hotel_mapping[hotel_dir]
    document_type = filename.replace(".md", "")

    metadata = {
        "metadataAttributes": {
            "hotel_id": hotel_info["id"],
            "hotel_name": hotel_info["name"],
            # "document_type": document_type,
            # "language": "es",
            # "category": categorize_document(document_type),
            # "last_updated": datetime.now().strftime("%Y-%m-%d"),
        }
    }

    return metadata


def generate_metadata_files(source_path: str) -> Dict[str, int]:
    """
    Generate metadata files for all hotel documents.

    Args:
        source_path: Path to hotel-knowledge-base directory

    Returns:
        Dictionary with statistics about generated files
    """
    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Source path does not exist: {source_path}")

    hotel_mapping = get_hotel_mapping()
    stats = {
        "hotels_processed": 0,
        "files_processed": 0,
        "metadata_files_created": 0,
        "errors": 0,
    }

    print(f"Processing hotel documents in: {source_path}")
    print(f"Hotel mapping: {len(hotel_mapping)} hotels configured")
    print()

    for hotel_dir in source_path.iterdir():
        if not hotel_dir.is_dir():
            continue

        hotel_name = hotel_dir.name

        # Skip directories that aren't hotels
        if hotel_name.startswith(".") or hotel_name not in hotel_mapping:
            print(f"Skipping directory: {hotel_name}")
            continue

        print(f"Processing hotel: {hotel_name}")
        stats["hotels_processed"] += 1

        hotel_files_processed = 0

        for file_path in hotel_dir.iterdir():
            if not file_path.is_file() or not file_path.name.endswith(".md"):
                continue

            # Skip README files
            if file_path.name.lower() == "readme.md":
                continue

            try:
                # Generate metadata
                metadata = generate_metadata_for_file(
                    hotel_name, file_path.name, hotel_mapping
                )

                # Write metadata file
                metadata_file_path = file_path.with_suffix(".md.metadata.json")

                with open(metadata_file_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                print(f"  ✓ Created metadata for: {file_path.name}")
                stats["files_processed"] += 1
                stats["metadata_files_created"] += 1
                hotel_files_processed += 1

            except Exception as e:
                print(f"  ✗ Error processing {file_path.name}: {e}")
                stats["errors"] += 1

        print(f"  Hotel {hotel_name}: {hotel_files_processed} files processed")
        print()

    return stats


def main():
    """Main function to run the metadata generation script."""

    # Default source path relative to script location
    script_dir = Path(__file__).parent
    default_source_path = script_dir.parent / "hotel-knowledge-base"

    print("Hotel Knowledge Base Metadata Generation")
    print("=" * 50)
    print()

    try:
        # Generate metadata files
        stats = generate_metadata_files(str(default_source_path))

        print("Generation Complete!")
        print("=" * 50)
        print(f"Hotels processed: {stats['hotels_processed']}")
        print(f"Files processed: {stats['files_processed']}")
        print(f"Metadata files created: {stats['metadata_files_created']}")
        print(f"Errors: {stats['errors']}")

        if stats["errors"] > 0:
            print("\n⚠️  Some files had errors. Check the output above for details.")
            return 1
        else:
            print("\n✅ All metadata files generated successfully!")
            return 0

    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
