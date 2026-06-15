"""统一的异常类型层次"""


class QrCodeError(Exception):
    """QR Code 操作的基础异常"""
    pass


class EncodeError(QrCodeError):
    """编码失败（文件无法读取、过大、压缩失败等）"""
    pass


class DecodeError(QrCodeError):
    """解码失败（base64/gzip 错误、分片缺失等）"""
    pass


class CameraError(QrCodeError):
    """摄像头不可用或操作失败"""
    pass


class FileLimitError(QrCodeError):
    """批量转换时文件数量超限"""
    pass
