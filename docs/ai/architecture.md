# Architecture Overview

> 本文档为 AI agent 提供项目架构上下文。仅包含无法从代码中直接看出的信息。

## Tech Stack
- Language: Python 3.12+
- Runtime: CPython
- Package Manager: pip (可编辑安装)
- CLI Framework: argparse (标准库)
- Key Libraries: zxing-cpp (QR 编解码), opencv-python (摄像头), pillow (图像处理)

## Project Structure
```
src/qrcode_app/
├── __init__.py
├── cli/
│   └── main.py              # argparse CLI 入口（不包含业务逻辑）
├── domain/                  # 纯领域逻辑，无 I/O 无副作用
│   ├── encoder.py           # 文件 → QR 文本块（gzip+base64+分片）
│   ├── decoder.py           # QR 文本块 → 原始文件字节
│   └── models.py            # 数据类、常量、PART_PATTERN
├── services/                # 编排层（有副作用）
│   ├── camera_service.py    # 功能1：摄像头实时捕捉
│   └── batch_service.py     # 功能2：批量目录转换
├── io/                      # I/O 操作
│   ├── file_io.py           # 文件读写
│   └── image_io.py          # QR 图片生成与读写
└── errors.py                # 统一异常类型
```

## Key Design Decisions
- CLI 委托到 services 层，services 委托到 domain 层 — 不包含业务逻辑
- Domain 层是纯函数 — 便于单元测试
- 使用 zxingcpp 同时进行 QR 编解码 — 减少依赖，保证兼容性
- PART 头部包含 file_id 字段 — 摄像头场景下区分不同文件的分片

## QR Data Format
- 单分片：`<base64_gzip_data>`
- 多分片：`PART:<file_id>:<part>/<total>:<base64_data>`
- 管道：`文件字节 → gzip(level=9) → base64 → 分片 → PART头部 → QR 码`
- 每个 QR 块最大 2900 字符（Byte 模式，Version 40）

## External Dependencies
- Camera: cv2.VideoCapture(0)，支持分辨率切换
- Output: D:\MediaPipe\QRCode\OutputQR\

## Known Pitfalls
- QR 码 Byte 模式上限 ~2953 字节，含小写字母的 base64 数据会触发此限制
- Windows 下 opencv-python-headless 不支持 cv2.imshow()，需要 opencv-python
- zxingcpp 的 create_barcode() 参数顺序是 (content, format)，不是 (format, content)
- Windows 文本文件写盘时 `\n` 会被转换为 `\r\n`，编解码闭环不受影响
