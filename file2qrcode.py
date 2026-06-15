#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
file_to_qrcode.py
将本地文件内容转换为二维码图片（完全本地处理，不传输任何数据到外部）

用法:
    python file_to_qrcode.py <文件路径> [输出目录]

示例:
    python file_to_qrcode.py C:/path/to/file.py
    python file_to_qrcode.py C:/path/to/file.py ./output
"""

import sys
import os
import gzip
import base64
import math
import argparse
from pathlib import Path

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"[错误] 缺少依赖库: {e}")
    print("请运行: pip install qrcode[pil] pillow")
    sys.exit(1)

# QR码版本40（最大容量），纠错级别L时最大可存储2953字节二进制数据
# 使用base64编码后，实际可存储约 2953 * 3/4 ≈ 2214 字节原始数据（压缩后）
QR_MAX_BYTES = 2900  # 留一些余量


def read_file(filepath: str) -> bytes:
    """读取文件内容（二进制模式）"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    if not path.is_file():
        raise ValueError(f"路径不是文件: {filepath}")
    with open(path, "rb") as f:
        return f.read()


def compress_and_encode(data: bytes) -> str:
    """压缩数据并进行base64编码，返回字符串"""
    compressed = gzip.compress(data, compresslevel=9)
    encoded = base64.b64encode(compressed).decode("ascii")
    return encoded


def split_into_chunks(data: str, chunk_size: int) -> list:
    """将字符串分割为指定大小的块"""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def make_qr_image(data: str, error_correction=ERROR_CORRECT_L) -> Image.Image:
    """生成单张二维码图片"""
    qr = qrcode.QRCode(
        version=None,          # 自动选择最小版本
        error_correction=error_correction,
        box_size=8,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.get_image() if hasattr(img, "get_image") else img


def add_label(img: Image.Image, label: str) -> Image.Image:
    """在二维码图片底部添加文字标签"""
    label_height = 36
    new_img = Image.new("RGB", (img.width, img.height + label_height), "white")
    new_img.paste(img, (0, 0))
    draw = ImageDraw.Draw(new_img)
    # 尝试使用系统字体，失败则使用默认字体
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        try:
            font = ImageFont.truetype(
                "C:/Windows/Fonts/msyh.ttc", 18  # 微软雅黑
            )
        except Exception:
            font = ImageFont.load_default()
    # 居中绘制文字
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    x = (img.width - text_w) // 2
    y = img.height + (label_height - (bbox[3] - bbox[1])) // 2
    draw.text((x, y), label, fill="black", font=font)
    return new_img


def generate_qrcodes(filepath: str, output_dir: str = ".") -> list:
    """
    主函数：读取文件 -> 压缩编码 -> 分块 -> 生成二维码图片
    返回生成的图片路径列表
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = Path(filepath).name
    print(f"[信息] 读取文件: {filepath}")
    raw_data = read_file(filepath)
    raw_size = len(raw_data)
    print(f"[信息] 原始文件大小: {raw_size:,} 字节")

    encoded_data = compress_and_encode(raw_data)
    encoded_size = len(encoded_data)
    compression_ratio = (1 - encoded_size / raw_size) * 100 if raw_size > 0 else 0
    print(f"[信息] 压缩+Base64编码后大小: {encoded_size:,} 字节 "
          f"(压缩率: {compression_ratio:.1f}%)")

    # 计算需要多少张二维码
    # 每块数据需要预留头部信息: "PART:X/Y:" 最多约 "PART:999/999:" = 13字节
    header_overhead = 15
    chunk_size = QR_MAX_BYTES - header_overhead
    chunks = split_into_chunks(encoded_data, chunk_size)
    total_parts = len(chunks)

    print(f"[信息] 需要生成 {total_parts} 张二维码")

    generated_files = []
    for i, chunk in enumerate(chunks, start=1):
        # 构造带头部的数据块
        if total_parts == 1:
            # 单张二维码不需要分片头部
            qr_data = chunk
            label = f"{filename} (完整)"
        else:
            # 多张时加入分片信息，便于还原
            qr_data = f"PART:{i}/{total_parts}:{chunk}"
            label = f"{filename} ({i}/{total_parts})"

        print(f"[信息] 生成第 {i}/{total_parts} 张二维码 "
              f"(数据块大小: {len(qr_data):,} 字节)...")

        try:
            img = make_qr_image(qr_data)
        except Exception as e:
            print(f"[警告] 纠错级别L生成失败，尝试降低数据量: {e}")
            # 如果仍然失败，尝试更小的块
            raise RuntimeError(
                f"二维码生成失败，数据块过大: {len(qr_data)} 字节\n"
                f"错误: {e}"
            )

        img_with_label = add_label(img, label)

        # 输出文件名
        if total_parts == 1:
            out_filename = f"{Path(filepath).stem}_qrcode.png"
        else:
            out_filename = f"{Path(filepath).stem}_qrcode_{i:03d}_of_{total_parts:03d}.png"

        out_filepath = output_path / out_filename
        img_with_label.save(str(out_filepath))
        print(f"[成功] 已保存: {out_filepath}")
        generated_files.append(str(out_filepath))

    return generated_files


def print_summary(filepath: str, generated_files: list):
    """打印生成摘要"""
    print("\n" + "=" * 60)
    print("生成摘要")
    print("=" * 60)
    print(f"源文件  : {filepath}")
    print(f"二维码数: {len(generated_files)} 张")
    for f in generated_files:
        size = os.path.getsize(f)
        print(f"  -> {f}  ({size:,} 字节)")
    print("=" * 60)
    if len(generated_files) > 1:
        print("\n[提示] 文件被分割为多张二维码。")
        print("       还原时需按顺序扫描所有二维码，")
        print("       拼接数据后进行 Base64解码 + Gzip解压。")
    print("\n[安全] 所有处理均在本地完成，未向外部传输任何数据。")


def main():
    parser = argparse.ArgumentParser(
        description="将本地文件内容转换为二维码图片（完全本地处理）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python file_to_qrcode.py myfile.py
  python file_to_qrcode.py myfile.py ./output_dir
  python file_to_qrcode.py "C:/path/to/file.py" "C:/output"
        """
    )
    parser.add_argument(
        "filepath",
        help="要转换的文件路径"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=".",
        help="输出目录（默认为当前目录）"
    )

    args = parser.parse_args()

    try:
        generated = generate_qrcodes(args.filepath, args.output_dir)
        print_summary(args.filepath, generated)
    except FileNotFoundError as e:
        print(f"[错误] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[错误] {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"[错误] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()