"""CLI entry point: qrfile camera | convert | encode | decode"""

import sys
import argparse
from pathlib import Path
from qrfile.domain.models import DEFAULT_MAX_FILES
from qrfile.errors import QrCodeError

DEFAULT_RESOLUTION = "1920x1080"
DEFAULT_OUTPUT_BASE = str(Path(__file__).resolve().parent.parent.parent.parent / "OutputQR")


def _parse_resolution(s: str) -> tuple[int, int]:
    """Parse WxH string into (width, height) tuple"""
    try:
        w, h = s.split("x", 1)
        return (int(w), int(h))
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(
            f"Invalid resolution format: '{s}', expected WxH (e.g. 1920x1080)"
        )


def cmd_encode(args):
    """Encode a single file to QR code image(s)"""
    from qrfile.io.file_io import read_file_bytes
    from qrfile.io.image_io import text_to_qr_image, save_qr_image
    from qrfile.domain.encoder import (
        compress_and_encode, make_file_id, split_into_chunks, format_qr_data,
    )

    filepath = Path(args.file)
    output_dir = Path(args.output) if args.output else Path.cwd()

    print(f"[INFO] Reading file: {filepath}")
    raw_data = read_file_bytes(filepath)
    encoded = compress_and_encode(raw_data)
    file_id = make_file_id(filepath.stem)
    chunks = split_into_chunks(encoded)
    total = len(chunks)

    print(f"[INFO] Original: {len(raw_data):,} bytes -> encoded: {len(encoded):,} chars")
    print(f"[INFO] Generating {total} QR image(s)")

    generated = []
    for i, chunk in enumerate(chunks, start=1):
        qr_data = format_qr_data(chunk, file_id, i, total)
        add_label = not args.no_labels

        if total == 1:
            label = f"{filepath.name}" if add_label else None
            out_name = f"{filepath.stem}_qrcode.png"
        else:
            label = f"{filepath.name} ({i}/{total})" if add_label else None
            out_name = f"{filepath.stem}_qrcode_{i:03d}_of_{total:03d}.png"

        img = text_to_qr_image(qr_data, label)
        out_path = output_dir / out_name
        save_qr_image(img, out_path)
        print(f"  [{i}/{total}] {out_path}")
        generated.append(out_path)

    print(f"\n[DONE] Generated {len(generated)} QR image(s)")
    if total > 1:
        print("[HINT] File was split into multiple QR codes. Scan all images in order to restore.")


def _collect_images(source: Path) -> list[Path]:
    """Collect PNG images from a directory, or return the single file path"""
    if source.is_dir():
        pngs = sorted(p for p in source.iterdir() if p.suffix.lower() == ".png")
        if not pngs:
            print(f"[WARN] No PNG images found in directory: {source}")
        return pngs
    return [source]


def cmd_decode(args):
    """Decode QR code image(s) back to original file(s)"""
    from qrfile.io.image_io import read_image
    from qrfile.domain.decoder import decode_qr_image, reconstruct_all
    from qrfile.domain.encoder import parse_qr_data
    from qrfile.io.file_io import write_file_bytes

    image_paths: list[Path] = []
    for item in args.images:
        p = Path(item)
        if not p.exists():
            print(f"[WARN] Path not found, skipping: {p}")
            continue
        image_paths.extend(_collect_images(p))

    if not image_paths:
        print("[ERROR] No images to decode")
        sys.exit(1)

    print(f"[INFO] {len(image_paths)} image(s) to decode")

    decoded_parts = []
    for p in image_paths:
        img = read_image(p)
        texts = decode_qr_image(img)
        if not texts:
            print(f"[WARN] No QR code detected: {p.name}")
            continue
        for text in texts:
            dp = parse_qr_data(text)
            decoded_parts.append(dp)
            if dp.file_id:
                print(f"  {p.name}: PART {dp.part_num}/{dp.total_parts} (file_id={dp.file_id})")
            else:
                print(f"  {p.name}: single-part file")

    if not decoded_parts:
        print("[ERROR] No QR data decoded from any image")
        sys.exit(1)

    try:
        files = reconstruct_all(decoded_parts)
    except ValueError as e:
        print(f"[ERROR] Reconstruction failed: {e}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else Path(".")
    is_single = len(files) == 1

    if is_single:
        file_id, data = next(iter(files.items()))
        if output_dir.suffix:
            out_path = output_dir
        else:
            ext = _guess_ext(data)
            out_path = output_dir / f"{file_id}{ext}"
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[INFO] Detected {len(files)} files, output to: {output_dir}")
        for file_id, data in files.items():
            ext = _guess_ext(data)
            out_path = output_dir / f"{file_id}{ext}"
            write_file_bytes(out_path, data)
            print(f"  {out_path.name} ({len(data):,} bytes)")
        return

    write_file_bytes(out_path, data)
    print(f"\n[DONE] Restored: {out_path} ({len(data):,} bytes)")


def _guess_ext(data: bytes) -> str:
    """Guess file extension from magic bytes"""
    if data.startswith(b'\x89PNG'):
        return '.png'
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if data.startswith(b'GIF8'):
        return '.gif'
    if data.startswith(b'%PDF'):
        return '.pdf'
    if data.startswith(b'PK\x03\x04'):
        return '.zip'
    try:
        text = data.decode('utf-8')
        if text.startswith('<!DOCTYPE') or text.startswith('<html'):
            return '.html'
        if text.startswith('{') or text.startswith('['):
            return '.json'
        if text.startswith('#!'):
            return '.py'
        return '.txt'
    except UnicodeDecodeError:
        return '.bin'


def cmd_convert(args):
    """Batch convert text/code files in a directory to QR code images"""
    from qrfile.services.batch_service import batch_convert

    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"[ERROR] Directory not found: {source_dir}")
        sys.exit(1)

    output_base = Path(args.output_base) if args.output_base else Path(DEFAULT_OUTPUT_BASE)
    batch_convert(
        source_dir=source_dir,
        output_base=output_base,
        max_files=args.max_files,
        add_labels=not args.no_labels,
    )


def cmd_camera(args):
    """Live camera QR code capture and file reconstruction"""
    from qrfile.services.camera_service import CameraSession

    resolution = _parse_resolution(args.resolution)
    output_dir = Path(args.output) if args.output else Path.cwd()

    session = CameraSession(
        camera_id=args.camera_id,
        resolution=resolution,
        output_dir=output_dir,
        frame_skip=args.frame_skip,
        show_preview=not args.no_preview,
    )

    print(f"[INFO] Camera {args.camera_id} started")
    print(f"[INFO] Resolution: {resolution[0]}x{resolution[1]}")
    print(f"[INFO] Output dir: {output_dir}")
    print("[KEYS] 'r' = switch resolution | 'q' = quit")

    try:
        session.run()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        session.stop()


def main():
    parser = argparse.ArgumentParser(
        prog="qrfile",
        description="QR Code file transfer tool — encode files to QR / decode from camera (fully local)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  qrfile encode myfile.txt\n"
               "  qrfile encode myfile.txt --output ./out\n"
               "  qrfile decode ./out                     # read all PNGs in directory\n"
               "  qrfile decode ./out --output result.txt\n"
               "  qrfile decode a.png b.png               # specify individual images\n"
               "  qrfile convert --source ./docs\n"
               "  qrfile camera --resolution 1280x720",
    )
    sub = parser.add_subparsers(dest="command", title="subcommands")

    # ---- encode ----
    enc = sub.add_parser("encode", help="Encode a file to QR code image(s)",
                         description="Compress and encode a file into one or more QR code images")
    enc.add_argument("file", help="Path to the file to encode")
    enc.add_argument("--output", "-o", default=None, help="Output directory (default: current dir)")
    enc.add_argument("--no-labels", action="store_true", help="Omit text labels on QR images")
    enc.set_defaults(func=cmd_encode)

    # ---- decode ----
    dec = sub.add_parser("decode", help="Decode QR code image(s) back to file(s)",
                         description="Read PNG images from a directory or specified files, "
                                     "auto-group by file_id, reassemble parts, and restore all files")
    dec.add_argument("images", nargs="+", help="QR image directory or file paths (can mix)")
    dec.add_argument("--output", "-o", default=None,
                     help="Output path (filename for single, directory for multiple; default: .)")
    dec.set_defaults(func=cmd_decode)

    # ---- convert ----
    conv = sub.add_parser("convert", help="Batch convert text/code files to QR images",
                          description="Recursively scan a directory for text/code files "
                                      "(.py .c .js .html etc.) and convert each to QR images. "
                                      "Binary files and .git/node_modules dirs are skipped.")
    conv.add_argument("--source", "-s", required=True, help="Source directory to scan")
    conv.add_argument("--output-base", default=None,
                      help=f"Base output directory (default: {DEFAULT_OUTPUT_BASE})")
    conv.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES,
                      help=f"Max files to process (default: {DEFAULT_MAX_FILES}, 0=unlimited)")
    conv.add_argument("--no-labels", action="store_true", help="Omit text labels on QR images")
    conv.set_defaults(func=cmd_convert)

    # ---- camera ----
    cam = sub.add_parser("camera", help="Live camera QR code capture",
                         description="Open camera for continuous QR code capture. "
                                     "Auto-detects supported resolutions on startup. "
                                     "Press 'r' to cycle resolutions, 'q' to quit.")
    cam.add_argument("--camera-id", type=int, default=0, help="Camera device index (default: 0)")
    cam.add_argument("--resolution", "-r", default=DEFAULT_RESOLUTION,
                     help=f"Initial resolution WxH (default: {DEFAULT_RESOLUTION}). Press 'r' to cycle")
    cam.add_argument("--output", "-o", default=None, help="Output directory for restored files (default: .)")
    cam.add_argument("--frame-skip", type=int, default=3,
                     help="Process every Nth frame for QR detection (default: 3)")
    cam.add_argument("--no-preview", action="store_true", help="Disable camera preview window")
    cam.set_defaults(func=cmd_camera)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except QrCodeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
