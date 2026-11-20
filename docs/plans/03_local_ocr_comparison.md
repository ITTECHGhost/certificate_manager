# 03 — Compare local OCR engines, then import wizard (TODO A3 + OCR bullet)
- Goal: run PaddleOCR → Qwen2.5-VL 7B (Ollama, if 8GB GPU) → Qari-OCR on the same samples as plan 01; pick one behind one `ocr_provider` interface (cloud off by default, key server-side only).
- Files: new `services/ocr_provider.py` (interface + local impls), `scripts/ocr_compare.py`, results in `docs/ocr_accuracy.md`.
- DB / migration: none.
- Tests first: `tests/test_ocr_provider.py` (fake provider, cloud disabled unless config flag, no key in client).
- Risks: new heavy dependencies (needs your OK each); GPU absent; exe size grows — keep OCR on server, not in client exe.
- Model: Opus for comparison/judgement, Sonnet for the wrapper.
- Question: Which machine has the GPU (server laptop or DEV), and may I add paddleocr/ollama as dependencies?
