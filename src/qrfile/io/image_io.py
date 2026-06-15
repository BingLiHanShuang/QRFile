"""二维码图片生成与读写

使用 zxingcpp 生成 QR 码，通过 numpy 桥接转换为 PIL Image，
可选在底部添加文字标签。
"""

import zxingcpp
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def _get_font(size: int = 18) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """获取可用字体，按优先级回退"""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",   # 微软雅黑
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(fp, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def text_to_qr_image(data: str, label: str | None = None) -> Image.Image:
    """将文本数据编码为 QR 码 PIL Image，可选添加文字标签

    QR 模块尺寸与 file2qrcode.py 保持一致：box_size=8、border=4。

    Args:
        data: 要编码的文本数据
        label: 二维码底部显示的文字标签（None 则不添加）

    Returns:
        PIL Image（灰度模式，白色背景黑色 QR）

    Raises:
        ValueError: 数据过大，无法生成 QR 码
    """
    barcode = zxingcpp.create_barcode(data, zxingcpp.BarcodeFormat.QRCode)
    zxing_img = zxingcpp.write_barcode_to_image(barcode)
    arr = np.array(zxing_img, copy=False)

    # zxingcpp 输出 1px/模块，放大 8 倍以匹配 file2qrcode.py 的 box_size=8
    if arr.ndim == 2:
        pil_img = Image.fromarray(arr, mode="L")
    else:
        pil_img = Image.fromarray(arr)
    new_size = (pil_img.width * 8, pil_img.height * 8)
    pil_img = pil_img.resize(new_size, Image.NEAREST)

    if label is None:
        return pil_img

    # 在底部添加文字标签
    label_height = 40
    font = _get_font(18)
    new_img = Image.new("L", (pil_img.width, pil_img.height + label_height), 255)
    new_img.paste(pil_img, (0, 0))

    draw = ImageDraw.Draw(new_img)
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (pil_img.width - text_w) // 2
    y = pil_img.height + (label_height - text_h) // 2
    draw.text((x, y), label, fill=0, font=font)

    return new_img


def save_qr_image(image: Image.Image, filepath: Path) -> None:
    """保存 PIL Image 为 PNG 文件，自动创建父目录"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(filepath), format="PNG")


def read_image(filepath: Path) -> Image.Image:
    """读取图片文件为 RGB 模式的 PIL Image"""
    return Image.open(filepath).convert("RGB")
