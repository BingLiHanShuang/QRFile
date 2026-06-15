"""集成测试：批量转换 + 解码闭环"""

import pytest
import tempfile
from pathlib import Path
from qrfile.services.batch_service import batch_convert
from qrfile.domain.decoder import decode_qr_image, reconstruct_file
from qrfile.domain.encoder import parse_qr_data
from qrfile.io.image_io import read_image


class TestBatchConvertRoundtrip:
    def test_single_file_roundtrip(self):
        """批量转换一个文件后，能解码还原"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "input"
            source_dir.mkdir()
            test_file = source_dir / "hello.txt"
            test_file.write_text("Hello QR Code World!", encoding="utf-8")

            output_base = Path(tmpdir) / "output"
            generated = batch_convert(source_dir, output_base)

            assert len(generated) == 1
            assert generated[0].exists()

            # 解码还原
            img = read_image(generated[0])
            texts = decode_qr_image(img)
            assert len(texts) == 1
            dp = parse_qr_data(texts[0])
            result = reconstruct_file([dp])
            assert result == test_file.read_bytes()

    def test_multi_file_roundtrip(self):
        """批量转换多个文件，每个都能解码还原"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "input"
            source_dir.mkdir()

            files = {}
            for name in ["a.txt", "b.txt", "c.txt"]:
                content = f"Content of {name}\n" * 50
                filepath = source_dir / name
                filepath.write_text(content, encoding="utf-8")
                files[name] = filepath.read_bytes()  # 读取实际写入的字节

            output_base = Path(tmpdir) / "output"
            generated = batch_convert(source_dir, output_base)

            assert len(generated) >= 3

            qr_by_stem: dict[str, list[Path]] = {}
            for p in generated:
                stem = p.stem.rsplit("_qrcode", 1)[0]
                qr_by_stem.setdefault(stem, []).append(p)

            for stem, paths in qr_by_stem.items():
                dps = []
                for p in sorted(paths):
                    img = read_image(p)
                    for text in decode_qr_image(img):
                        dps.append(parse_qr_data(text))
                try:
                    result = reconstruct_file(dps)
                except ValueError as e:
                    pytest.fail(f"还原 {stem} 失败: {e}")

                expected_name = stem + ".txt"
                assert result == files[expected_name], f"{stem} 内容不匹配"

    def test_empty_directory(self):
        """空目录返回空列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "empty"
            source_dir.mkdir()
            generated = batch_convert(source_dir, Path(tmpdir) / "out")
            assert generated == []

    def test_non_txt_files(self):
        """非 .txt 代码文件也能转换（.py .c .js 等）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "input"
            source_dir.mkdir()
            test_file = source_dir / "hello.py"
            test_file.write_text("print('hello')", encoding="utf-8")

            output_base = Path(tmpdir) / "output"
            generated = batch_convert(source_dir, output_base)
            assert len(generated) == 1

            img = read_image(generated[0])
            texts = decode_qr_image(img)
            dp = parse_qr_data(texts[0])
            result = reconstruct_file([dp])
            assert result == test_file.read_bytes()

    def test_binary_files_skipped(self):
        """二进制文件不会被转换"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "input"
            source_dir.mkdir()
            # .png 在黑名单
            (source_dir / "image.png").write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 20)
            # .txt 在白名单
            (source_dir / "good.txt").write_text("valid", encoding="utf-8")

            output_base = Path(tmpdir) / "output"
            generated = batch_convert(source_dir, output_base)
            # 只转换了 .txt
            assert len(generated) == 1
            assert "good" in generated[0].stem

    def test_skip_git_dir(self):
        """.git 等目录被递归跳过"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "input"
            source_dir.mkdir()
            git_dir = source_dir / ".git"
            git_dir.mkdir()
            (git_dir / "config.txt").write_text("secret", encoding="utf-8")
            (source_dir / "readme.md").write_text("# Hello", encoding="utf-8")

            output_base = Path(tmpdir) / "output"
            generated = batch_convert(source_dir, output_base)
            assert len(generated) == 1
            assert "readme" in generated[0].stem

    def test_large_file_multi_qr(self):
        """大文件产生多张 QR 码，能正确还原"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "input"
            source_dir.mkdir()
            # 使用无明显规律的内容（高熵数据压缩率低，确保需要多张 QR）
            import os
            content = "".join(
                chr(0x4e00 + (i % 0x5000)) for i in range(30000)
            )
            test_file = source_dir / "large.txt"
            test_file.write_text(content, encoding="utf-8")

            output_base = Path(tmpdir) / "output"
            generated = batch_convert(source_dir, output_base)
            assert len(generated) > 1

            dps = []
            for p in sorted(generated):
                img = read_image(p)
                for text in decode_qr_image(img):
                    dps.append(parse_qr_data(text))

            result = reconstruct_file(dps)
            assert result == test_file.read_bytes()
