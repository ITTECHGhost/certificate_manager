# =============================================================================
# nicegui_ui/upload_utils.py — Read files from ui.upload events
#
# NiceGUI 3 changed the upload event: the file is now e.file (with an async
# read()), and e.name / e.content no longer exist. Handlers written for the old
# API silently got no content. read_upload() works with both.
# =============================================================================


async def read_upload(e) -> tuple[str, bytes]:
    """Return (file name, file bytes) from a ui.upload on_upload event."""
    upload = getattr(e, "file", None)
    if upload is not None:  # NiceGUI 3.x
        return str(getattr(upload, "name", "") or ""), await upload.read()
    # NiceGUI 2.x
    content = e.content.read() if hasattr(e, "content") else b""
    return str(getattr(e, "name", "") or ""), content or b""
