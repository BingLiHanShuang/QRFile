"""domain/encoder.py 单元测试"""

import pytest
from qrfile.domain.encoder import (
    compress_and_encode,
    decompress_and_decode,
    make_file_id,
    content_hash,
    split_into_chunks,
    format_qr_data,
    parse_qr_data,
    combine_and_decompress,
)
from qrfile.domain.models import DecodedPart


class TestCompressAndEncode:
    def test_roundtrip(self):
        data = b"Hello World " * 100
        encoded = compress_and_encode(data)
        decoded = decompress_and_decode(encoded)
        assert decoded == data

    def test_empty_data(self):
        data = b""
        encoded = compress_and_encode(data)
        decoded = decompress_and_decode(encoded)
        assert decoded == data

    def test_binary_data(self):
        data = bytes(range(256)) * 10
        encoded = compress_and_encode(data)
        decoded = decompress_and_decode(encoded)
        assert decoded == data

    def test_returns_ascii_string(self):
        encoded = compress_and_encode(b"test")
        assert isinstance(encoded, str)
        encoded.encode("ascii")  # 不应抛异常


class TestMakeFileId:
    def test_simple_name(self):
        assert make_file_id("hello") == "hello"

    def test_special_chars(self):
        # 点号和括号都被替换为下划线，连续下划线合并
        assert make_file_id("my file (1).txt") == "my_file_1_txt"

    def test_chinese_chars(self):
        # 中文字符全部被替换为下划线，合并后 strip 掉，回退为 "file"
        result = make_file_id("测试文件")
        assert result == "file"

    def test_too_long(self):
        long_name = "a" * 100
        result = make_file_id(long_name)
        assert len(result) <= 64

    def test_all_special(self):
        assert make_file_id("!!!") == "file"


class TestContentHash:
    def test_same_content_same_hash(self):
        assert content_hash("hello") == content_hash("hello")

    def test_different_content_different_hash(self):
        assert content_hash("hello") != content_hash("world")

    def test_hash_length(self):
        assert len(content_hash("test")) == 8


class TestSplitIntoChunks:
    def test_exact_chunks(self):
        result = split_into_chunks("ABCDEF", 3)
        assert result == ["ABC", "DEF"]

    def test_partial_last_chunk(self):
        result = split_into_chunks("ABCDE", 3)
        assert result == ["ABC", "DE"]

    def test_smaller_than_chunk(self):
        result = split_into_chunks("AB", 10)
        assert result == ["AB"]


class TestFormatQrData:
    def test_single_part(self):
        result = format_qr_data("data", "test", 1, 1)
        assert result == "data"

    def test_multi_part(self):
        result = format_qr_data("chunk", "test", 2, 5)
        assert result == "PART:test:2/5:chunk"


class TestParseQrData:
    def test_single_part(self):
        result = parse_qr_data("just_data")
        assert result.raw_text == "just_data"
        assert result.file_id is None
        assert result.part_num is None
        assert result.total_parts is None

    def test_multi_part(self):
        result = parse_qr_data("PART:myfile:3/7:base64data")
        assert result.raw_text == "base64data"
        assert result.file_id == "myfile"
        assert result.part_num == 3
        assert result.total_parts == 7

    def test_multiline_data(self):
        result = parse_qr_data("PART:f:1/2:line1\nline2\nline3")
        assert result.file_id == "f"
        assert result.raw_text == "line1\nline2\nline3"


class TestCombineAndDecompress:
    def test_single_part(self):
        data = b"Hello World"
        encoded = compress_and_encode(data)
        result = combine_and_decompress({1: encoded})
        assert result == data

    def test_multi_part(self):
        data = b"A" * 5000  # 需要多张 QR 码的数据
        encoded = compress_and_encode(data)
        chunks = split_into_chunks(encoded, 200)
        parts = {i + 1: chunk for i, chunk in enumerate(chunks)}
        result = combine_and_decompress(parts)
        assert result == data

    def test_missing_part_raises(self):
        with pytest.raises(KeyError):
            combine_and_decompress({1: "a", 3: "c"})
