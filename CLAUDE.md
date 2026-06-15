# QRCode Project Contract

## Build And Test
- Install: `pip install -e .`
- Test: `pytest tests/ -v`
- Lint: `ruff check src/`
- Typecheck: `mypy src/qrcode_app/`

## Architecture Boundaries
- CLI handlers live in `src/qrcode_app/cli/`
- Domain logic lives in `src/qrcode_app/domain/` (pure functions, no I/O)
- I/O operations live in `src/qrcode_app/io/`
- Service orchestration lives in `src/qrcode_app/services/`
- Shared errors live in `src/qrcode_app/errors.py`

## Coding Conventions
- Prefer pure functions in domain layer
- Do not introduce new global state without explicit justification
- Reuse existing error types from `src/qrcode_app/errors.py`
- All processing is local — never transmit data externally

## Data Format
- Single-part: `<base64_gzip_data>`
- Multi-part: `PART:<file_id>:<part>/<total>:<base64_data>`
- QR chunk size: 2900 chars (Byte mode, Version 40, EC Level L)

## Safety Rails

## NEVER
- Modify `.env`, lockfiles, or CI secrets without explicit approval
- Commit without running tests
- Change the QR data format without backward-compatibility review

## ALWAYS
- Show diff before committing
- Run `pytest tests/ -v` after any code change
- Verify encode-decode roundtrip for format changes

## Verification
- Domain changes: `pytest tests/test_encoder.py tests/test_decoder.py -v`
- I/O changes: `pytest tests/test_batch_service.py -v`
- Camera changes: manual test with phone-displayed QR codes
- Full verification: `pytest tests/ -v`
