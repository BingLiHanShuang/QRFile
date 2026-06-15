"""纯编码函数：文件 → QR 文本块（压缩 + base64 + 分片）
替代 file2qrcode.py 的核心逻辑，使用 zxingcpp 代替 qrcode 库。
"""

import gzip
import base64
import re
import hashlib
from .models import QR_CHUNK_SIZE, DecodedPart, PART_PATTERN, PART_PATTERN_LEGACY


def compress_and_encode(data: bytes) -> str:
    """gzip(level=9) 压缩 → base64 编码，返回 ASCII 字符串"""
    compressed = gzip.compress(data, compresslevel=9)
    return base64.b64encode(compressed).decode("ascii")


def decompress_and_decode(encoded: str) -> bytes:
    """base64 解码 → gzip 解压，返回原始字节"""
    return gzip.decompress(base64.b64decode(encoded))


def make_file_id(filename_stem: str) -> str:
    """从文件名 stem 生成合法的 file_id（只保留字母数字下划线连字符，最长 64 字符）"""
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '_', filename_stem)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned[:64] or "file"


def content_hash(raw_text: str) -> str:
    """计算 QR 文本内容的 SHA-256 前 8 位十六进制（用于去重）"""
    return hashlib.sha256(raw_text.encode()).hexdigest()[:8]


def split_into_chunks(data: str, chunk_size: int = QR_CHUNK_SIZE) -> list[str]:
    """将编码后的字符串按块大小分割"""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def format_qr_data(chunk: str, file_id: str, part_num: int, total: int) -> str:
    """格式化 QR 数据：多分片加 PART 头部，单分片直接返回"""
    if total == 1:
        return chunk
    return f"PART:{file_id}:{part_num}/{total}:{chunk}"


def parse_qr_data(raw_text: str) -> DecodedPart:
    """解析 QR 原始文本，兼容新旧两种 PART 头部格式。

    新格式（本工具生成）：PART:<file_id>:<序号>/<总数>:<base64数据>
    旧格式（file2qrcode.py 生成）：PART:<序号>/<总数>:<base64数据>
    无 PART 头部：单分片文件
    """
    # 先匹配新格式
    m = PART_PATTERN.match(raw_text)
    if m:
        return DecodedPart(
            raw_text=m.group(4),
            file_id=m.group(1),
            part_num=int(m.group(2)),
            total_parts=int(m.group(3)),
        )

    # 再匹配旧格式（无 file_id），用总分片数构造分组 ID
    m = PART_PATTERN_LEGACY.match(raw_text)
    if m:
        part_num = int(m.group(1))
        total = int(m.group(2))
        return DecodedPart(
            raw_text=m.group(3),
            file_id=f"_file_{total}p",
            part_num=part_num,
            total_parts=total,
        )

    return DecodedPart(raw_text=raw_text)


def combine_and_decompress(parts: dict[int, str]) -> bytes:
    """按分片序号拼接 → base64 解码 → gzip 解压，返回原始字节

    Args:
        parts: {part_num: base64_chunk_data} 字典

    Raises:
        ValueError: 分片缺失或不连续
    """
    total = len(parts)
    combined = "".join(parts[i] for i in range(1, total + 1))
    return decompress_and_decode(combined)
