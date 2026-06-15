"""Feature 1: Live camera QR code capture, part accumulation, file reconstruction

Optimizations:
1. Content-hash deduplication: same QR won't be re-processed across consecutive frames
2. Frame skipping: only scan every Nth frame to reduce CPU usage
3. Early reconstruction: attempt decode as soon as all parts are collected
4. History display: completed files remain visible in the status overlay
"""

import time
import cv2
import numpy as np
import zxingcpp
from pathlib import Path
from collections import defaultdict

from qrfile.domain.models import _RESOLUTION_CANDIDATES
from qrfile.domain.encoder import (
    parse_qr_data, content_hash, combine_and_decompress,
)
from qrfile.io.file_io import write_file_bytes
from qrfile.errors import CameraError


class CameraSession:
    """Manages live camera capture, QR detection, part accumulation, and file reconstruction"""

    def __init__(
        self,
        camera_id: int = 0,
        resolution: tuple[int, int] = (1920, 1080),
        output_dir: Path = Path("."),
        frame_skip: int = 3,
        show_preview: bool = True,
    ):
        self.camera_id = camera_id
        self.resolution = resolution
        self.output_dir = output_dir.resolve()
        self.frame_skip = max(1, frame_skip)
        self.show_preview = show_preview

        self._pending: dict[str, dict[int, str]] = defaultdict(dict)
        self._totals: dict[str, int] = {}
        self._seen_hashes: set[str] = set()
        self._last_qr_time: dict[str, float] = {}

        self._completed: list[dict] = []
        self._file_count: int = 0
        self._resolutions: list[tuple[int, int]] = []
        self._cap: cv2.VideoCapture | None = None

    def _open_camera(self):
        """Open camera and set resolution"""
        if self._cap is not None:
            self._cap.release()

        self._cap = cv2.VideoCapture(self.camera_id)
        if not self._cap.isOpened():
            raise CameraError(f"Cannot open camera {self.camera_id}")

        # Detect supported resolutions on first open
        if not self._resolutions:
            self._resolutions = self._detect_resolutions()
            print(f"[INFO] Detected {len(self._resolutions)} supported resolution(s): {self._resolutions}")

        # Apply user-requested resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[INFO] Actual resolution: {actual_w}x{actual_h}")

    def _detect_resolutions(self) -> list[tuple[int, int]]:
        """Try each candidate resolution and collect what the camera actually accepts"""
        working: list[tuple[int, int]] = []
        for w, h in _RESOLUTION_CANDIDATES:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            res = (actual_w, actual_h)
            if res == (w, h) and res not in working:
                working.append(res)
        working.sort(key=lambda r: r[0] * r[1], reverse=True)
        return working or [self.resolution]

    def run(self):
        """Main loop: read frame -> detect QR -> dedupe -> accumulate parts -> try reconstruct"""
        self._open_camera()
        frame_idx = 0
        WINDOW_NAME = "QR Capture [r=res q=quit]"

        try:
            while True:
                ret, frame = self._cap.read()
                if not ret:
                    print("[WARN] Failed to read frame")
                    time.sleep(0.1)
                    continue

                frame_idx += 1

                if frame_idx % self.frame_skip == 0:
                    barcodes = self._scan_frame(frame)

                    for bc in barcodes:
                        if not bc.valid:
                            continue
                        h = content_hash(bc.text)
                        if h in self._seen_hashes:
                            continue
                        self._seen_hashes.add(h)
                        self._process_new_qr(bc.text)

                    if self.show_preview:
                        self._draw_detections(frame, barcodes)

                if self.show_preview:
                    self._draw_status(frame)
                    cv2.imshow(WINDOW_NAME, frame)

                if self._check_quit():
                    break

        finally:
            if self._cap is not None:
                self._cap.release()
            cv2.destroyAllWindows()

    def _scan_frame(self, frame: np.ndarray) -> list:
        """Scan all QR codes in a frame, return Barcode objects"""
        try:
            return list(zxingcpp.read_barcodes(
                frame,
                formats=zxingcpp.BarcodeFormat.QRCode,
                try_rotate=True,
                try_downscale=True,
                try_invert=True,
            ))
        except Exception as e:
            print(f"[WARN] QR scan error: {e}")
            return []

    def _process_new_qr(self, text: str):
        """Parse new QR -> group by file_id -> check completion -> try reconstruct"""
        dp = parse_qr_data(text)

        if dp.file_id is None:
            file_id = content_hash(dp.raw_text)
            print(f"\n[DETECT] Single-part QR, trying decode...")
            try:
                raw = combine_and_decompress({1: dp.raw_text})
                self._save_file(file_id, raw)
                return
            except Exception:
                print("[HINT] Single-part decode failed, waiting for more parts")
                self._pending[file_id][1] = dp.raw_text
                self._totals[file_id] = 1
                self._last_qr_time[file_id] = time.time()
                return

        file_id = dp.file_id
        self._pending[file_id][dp.part_num] = dp.raw_text
        self._totals[file_id] = dp.total_parts
        self._last_qr_time[file_id] = time.time()

        collected = len(self._pending[file_id])
        total = dp.total_parts
        print(f"\n[DETECT] {file_id}: part {dp.part_num}/{total} (collected {collected}/{total})")

        if collected >= total:
            print(f"[INFO] {file_id}: all parts collected, reconstructing...")
            if self._try_reconstruct(file_id):
                return

    def _try_reconstruct(self, file_id: str) -> bool:
        """Try to reconstruct file. Returns True on success and cleans up queue"""
        parts = self._pending[file_id]
        total = self._totals[file_id]

        if set(parts.keys()) != set(range(1, total + 1)):
            print(f"[HINT] {file_id}: parts not contiguous, waiting")
            return False

        try:
            raw = combine_and_decompress(parts)
        except Exception as e:
            print(f"[HINT] {file_id}: decode failed ({e}), waiting for more")
            return False

        self._save_file(file_id, raw)
        return True

    def _save_file(self, file_id: str, data: bytes):
        """Save reconstructed file, move to history, clean up queue"""
        self._file_count += 1
        total_parts = self._totals.get(file_id, 1)
        ext = self._guess_extension(data)
        out_path = self.output_dir / f"{file_id}_{self._file_count:03d}{ext}"

        counter = 1
        while out_path.exists():
            out_path = self.output_dir / f"{file_id}_{self._file_count:03d}_{counter}{ext}"
            counter += 1

        write_file_bytes(out_path, data)
        print(f"[SUCCESS] Saved: {out_path} ({len(data):,} bytes)")

        self._completed.append({
            "idx": self._file_count,
            "name": file_id,
            "parts": total_parts,
        })

        self._pending.pop(file_id, None)
        self._totals.pop(file_id, None)
        self._last_qr_time.pop(file_id, None)

    @staticmethod
    def _guess_extension(data: bytes) -> str:
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

    def switch_resolution(self, width: int, height: int):
        """Switch camera resolution at runtime"""
        self.resolution = (width, height)
        print(f"\n[INFO] Switching resolution: {width}x{height}")
        self._open_camera()

    def stop(self):
        """Release camera resources"""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        cv2.destroyAllWindows()

    def _draw_detections(self, frame: np.ndarray, barcodes: list):
        """Draw QR code detection bounding boxes on frame"""
        for r in barcodes:
            if not r.valid:
                continue
            pos = r.position
            if pos:
                pts = np.array([
                    [pos.top_left.x, pos.top_left.y],
                    [pos.top_right.x, pos.top_right.y],
                    [pos.bottom_right.x, pos.bottom_right.y],
                    [pos.bottom_left.x, pos.bottom_left.y],
                ], dtype=np.int32)
                cv2.polylines(frame, [pts], True, (0, 255, 0), 2)

    def _draw_status(self, frame: np.ndarray):
        """Draw status overlay: completed files + in-progress parts"""
        overlay = frame.copy()
        bar_h = self._status_bar_height()
        if bar_h > 0:
            cv2.rectangle(overlay, (0, 0), (350, bar_h + 10), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        y = 22
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1

        for entry in self._completed:
            text = f"[{entry['idx']}] {entry['name']}  {entry['parts']}/{entry['parts']}  DONE"
            cv2.putText(frame, text, (8, y), font, font_scale,
                        (0, 200, 0), thickness)
            y += 22

        for file_id in self._pending:
            parts = self._pending[file_id]
            total = self._totals.get(file_id, '?')
            idx = self._file_count + 1
            text = f"[{idx}] {file_id}  {len(parts)}/{total}"
            cv2.putText(frame, text, (8, y), font, font_scale,
                        (0, 255, 255), thickness)
            y += 22

    def _status_bar_height(self) -> int:
        """Return the required height for the status bar"""
        return (len(self._completed) + len(self._pending)) * 22

    def _check_quit(self) -> bool:
        """Check keyboard input for quit/resolution switch"""
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            return True
        if key == ord('r'):
            self._cycle_resolution()
        return False

    def _cycle_resolution(self):
        """Cycle to the next supported resolution"""
        if not self._resolutions:
            return
        current = self.resolution
        try:
            idx = self._resolutions.index(current)
            next_idx = (idx + 1) % len(self._resolutions)
        except ValueError:
            next_idx = 0
        new_res = self._resolutions[next_idx]
        self.switch_resolution(new_res[0], new_res[1])
