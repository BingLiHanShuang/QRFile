"""domain/decoder.py 单元测试"""

import pytest
from qrfile.domain.encoder import compress_and_encode, split_into_chunks, format_qr_data, parse_qr_data, make_file_id
from qrfile.domain.decoder import reconstruct_file
from qrfile.domain.models import DecodedPart


class TestReconstructFile:
    def test_single_part(self):
        data = b"Hello World " * 100
        encoded = compress_and_encode(data)
        parts = [DecodedPart(raw_text=encoded)]
        result = reconstruct_file(parts)
        assert result == data

    def test_multi_part(self):
        data = b"X" * 10000
        encoded = compress_and_encode(data)
        chunks = split_into_chunks(encoded, 500)
        file_id = "testfile"
        parts = [
            DecodedPart(
                raw_text=chunk,
                file_id=file_id,
                part_num=i + 1,
                total_parts=len(chunks),
            )
            for i, chunk in enumerate(chunks)
        ]
        result = reconstruct_file(parts)
        assert result == data

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="没有提供"):
            reconstruct_file([])

    def test_incomplete_parts_raises(self):
        # 直接用构造的 DecodedPart 测试，不依赖压缩
        parts = [
            DecodedPart(
                raw_text="chunk1",
                file_id="f",
                part_num=1,
                total_parts=3,
            )
        ]
        with pytest.raises(ValueError, match="不完整"):
            reconstruct_file(parts)

    def test_binary_data_roundtrip(self):
        data = bytes(range(256)) * 20
        encoded = compress_and_encode(data)
        parts = [DecodedPart(raw_text=encoded)]
        result = reconstruct_file(parts)
        assert result == data
