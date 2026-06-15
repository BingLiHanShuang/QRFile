"""数据模型、常量与正则模式"""

import re
from dataclasses import dataclass

# 每张 QR 码最大字符数（Byte 模式上限 ~2953，留 PART 头部余量）
QR_CHUNK_SIZE = 2900

# 匹配新格式：PART:<file_id>:<序号>/<总数>:<base64数据>
PART_PATTERN = re.compile(r'^PART:([^:]+):(\d+)/(\d+):(.+)$', re.DOTALL)

# 匹配旧格式（file2qrcode.py）：PART:<序号>/<总数>:<base64数据>（无 file_id）
PART_PATTERN_LEGACY = re.compile(r'^PART:(\d+)/(\d+):(.+)$', re.DOTALL)

# 分辨率探测候选列表：覆盖常见 16:9 和 4:3 分辨率（从高到低）
_RESOLUTION_CANDIDATES = [
    (3840, 2160),
    (2944, 1656),
    (2560, 1440),
    (1920, 1080),
    (1600, 900),
    (1280, 960),
    (1280, 720),
    (1024, 768),
    (800, 600),
    (640, 480),
    (640, 360),
    (320, 240),
]

# 批量转换默认最大文件数
DEFAULT_MAX_FILES = 100


@dataclass
class DecodedPart:
    """从单个 QR 码解码得到的数据"""
    raw_text: str
    file_id: str | None = None
    part_num: int | None = None
    total_parts: int | None = None

    @property
    def is_multi_part(self) -> bool:
        return self.file_id is not None
