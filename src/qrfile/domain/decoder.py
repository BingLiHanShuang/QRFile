"""纯解码函数：QR 文本块 → 原始文件字节
替代 qrcode2file.py 的核心逻辑。
"""

from collections import defaultdict
from PIL import Image
import zxingcpp
from .models import DecodedPart
from .encoder import combine_and_decompress


def decode_qr_image(pil_image: Image.Image) -> list[str]:
    """解码 PIL 图片中所有的二维码，返回文本列表

    只返回 QR Code 格式且有效的结果，过滤非 QR 格式的误检测（如标签文字）。
    """
    rgb_image = pil_image.convert("RGB")
    results = zxingcpp.read_barcodes(rgb_image)
    return [
        r.text for r in results
        if r.valid and r.format == zxingcpp.BarcodeFormat.QRCode
    ]


def group_parts_by_file(decoded_parts: list[DecodedPart]) -> dict[str, list[DecodedPart]]:
    """将解码的分片按 file_id 分组，单分片（无 file_id）各自成组

    Returns:
        {file_id: [DecodedPart, ...]} 字典，单分片的 file_id 由内容哈希生成
    """
    from .encoder import content_hash

    groups: dict[str, list[DecodedPart]] = defaultdict(list)
    for dp in decoded_parts:
        fid = dp.file_id if dp.file_id else content_hash(dp.raw_text)
        groups[fid].append(dp)
    return dict(groups)


def reconstruct_file(decoded_parts: list[DecodedPart]) -> bytes:
    """从同一文件的 DecodedPart 列表重建原始文件字节。

    校验所有分片齐全且序号连续，然后拼接解码。

    Args:
        decoded_parts: 同一 file_id 的 DecodedPart 列表

    Returns:
        原始文件字节

    Raises:
        ValueError: 分片不完整或不连续
    """
    if not decoded_parts:
        raise ValueError("没有提供任何 QR 数据")

    if len(decoded_parts) == 1 and not decoded_parts[0].file_id:
        # 单分片文件
        return combine_and_decompress({1: decoded_parts[0].raw_text})

    # 多分片文件：按序号收集
    parts: dict[int, str] = {}
    for dp in decoded_parts:
        if dp.part_num is None or dp.total_parts is None:
            raise ValueError("多分片模式下缺少 PART 头部信息")
        parts[dp.part_num] = dp.raw_text

    expected_count = decoded_parts[0].total_parts
    if len(parts) != expected_count:
        raise ValueError(
            f"分片不完整：已收集 {len(parts)}/{expected_count}"
        )

    return combine_and_decompress(parts)


def reconstruct_all(decoded_parts: list[DecodedPart]) -> dict[str, bytes]:
    """从混合的 DecodedPart 列表自动分组并还原所有文件

    自动按 file_id 分组，每组独立还原。适合摄像头捕捉或多文件目录解码场景。

    Args:
        decoded_parts: 可能包含多个文件的 DecodedPart 列表

    Returns:
        {file_id: raw_bytes} 字典，每个 file_id 对应一个还原后的文件内容

    Raises:
        ValueError: 某个文件的分片不完整
    """
    groups = group_parts_by_file(decoded_parts)
    results: dict[str, bytes] = {}
    for file_id, parts in groups.items():
        results[file_id] = reconstruct_file(parts)
    return results
