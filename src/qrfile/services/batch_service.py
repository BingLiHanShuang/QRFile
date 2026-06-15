"""Feature 2: Batch convert text/code files in a directory to QR code images"""

from pathlib import Path
from qrfile.io.file_io import read_file_bytes, list_source_files
from qrfile.io.image_io import text_to_qr_image, save_qr_image
from qrfile.domain.encoder import (
    compress_and_encode,
    make_file_id,
    split_into_chunks,
    format_qr_data,
)
from qrfile.domain.models import DEFAULT_MAX_FILES
from qrfile.errors import EncodeError


def batch_convert(
    source_dir: Path,
    output_base: Path,
    max_files: int = DEFAULT_MAX_FILES,
    add_labels: bool = True,
) -> list[Path]:
    """Batch convert all text/code files in a directory to QR code images

    Supports .py .c .js .ts .html .css .sh .go .rs .java .json .yaml etc.
    Skips binary files (.exe .dll .png .zip ...) and .git/node_modules dirs.

    Args:
        source_dir: Source directory to scan
        output_base: Base output directory (actual: output_base/<source_dir_name>/)
        max_files: Max files to process (0 = unlimited)
        add_labels: Whether to add text labels below QR images

    Returns:
        List of all generated image paths
    """
    source_dir = source_dir.resolve()
    files = list_source_files(source_dir, max_files)

    if not files:
        print(f"[INFO] No convertible files found in: {source_dir}")
        return []

    output_dir = output_base.resolve() / source_dir.name
    print(f"[INFO] Found {len(files)} file(s) to convert")
    print(f"[INFO] Output dir: {output_dir}")

    generated: list[Path] = []
    for filepath in files:
        try:
            paths = _convert_one_file(filepath, output_dir, add_labels)
            generated.extend(paths)
        except EncodeError as e:
            print(f"[WARN] Skipping {filepath.name}: {e}")

    print(f"\n[DONE] Generated {len(generated)} QR image(s)")
    return generated


def _convert_one_file(
    filepath: Path,
    output_dir: Path,
    add_labels: bool,
) -> list[Path]:
    """Convert a single file to QR code image(s)

    Returns:
        List of generated image paths
    """
    raw_data = read_file_bytes(filepath)
    encoded = compress_and_encode(raw_data)
    file_id = make_file_id(filepath.stem)
    chunks = split_into_chunks(encoded)
    total = len(chunks)

    generated: list[Path] = []
    for i, chunk in enumerate(chunks, start=1):
        qr_data = format_qr_data(chunk, file_id, i, total)

        if total == 1:
            label = f"{filepath.name}" if add_labels else None
            stem = filepath.stem
            out_name = f"{stem}_qrcode.png"
        else:
            label = f"{filepath.name} ({i}/{total})" if add_labels else None
            stem = filepath.stem
            out_name = f"{stem}_qrcode_{i:03d}_of_{total:03d}.png"

        img = text_to_qr_image(qr_data, label)
        out_path = output_dir / out_name
        save_qr_image(img, out_path)
        generated.append(out_path)

    print(f"  {filepath.name}: {total} QR image(s) "
          f"({len(raw_data):,} bytes -> {len(encoded):,} chars)")

    return generated
