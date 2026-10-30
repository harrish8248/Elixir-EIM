"""Universal Type Detector from Magic Bytes.

Inspects raw binary content signatures (magic bytes) to identify true MIME type and format,
independent of untrusted client MIME strings or file extensions.
Detects extension/content mismatches (e.g. an executable named .pdf or HTML named .jpg).
"""

import io
import os
import re
import zipfile
from dataclasses import dataclass


@dataclass(frozen=True)
class TypeDetectionResult:
    mime_type: str
    extension: str
    family: str  # pdf, image, office, archive, script, executable, text, data, email, media, binary
    is_macro_enabled: bool
    is_executable: bool
    is_archive: bool
    extension_mismatch: bool
    detection_method: str  # magic_bytes, zip_inspection, text_sniff
    description: str


# Common extension to MIME mapping for mismatch comparison
EXT_MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".docm": "application/vnd.ms-word.document.macroEnabled.12",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".pptm": "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".xml": "application/xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".rtf": "application/rtf",
    ".eml": "message/rfc822",
    ".msg": "application/vnd.ms-outlook",
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".7z": "application/x-7z-compressed",
    ".exe": "application/x-dosexec",
    ".dll": "application/x-msdownload",
    ".msi": "application/x-msi",
    ".sh": "application/x-sh",
    ".bat": "application/x-bat",
    ".cmd": "application/x-bat",
    ".ps1": "application/x-powershell",
    ".js": "text/javascript",
    ".vbs": "text/vbscript",
    ".jar": "application/java-archive",
    ".apk": "application/vnd.android.package-archive",
}


def _inspect_zip_internals(data: bytes) -> tuple[str, str, str, bool, bool, str]:
    """Inspect internal contents of a ZIP container to distinguish DOCX, XLSX, PPTX, macro files, JAR, APK, ODT, or standard ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            namelist = set(zf.namelist())

            # Check macro projects
            has_vba = any("vbaProject.bin" in name.lower() for name in namelist)

            # Word Document
            if "word/document.xml" in namelist:
                if has_vba:
                    return (
                        "application/vnd.ms-word.document.macroEnabled.12",
                        ".docm",
                        "office",
                        True,
                        False,
                        "Macro-enabled Microsoft Word Document",
                    )
                return (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".docx",
                    "office",
                    False,
                    False,
                    "Microsoft Word Document (DOCX)",
                )

            # Excel Spreadsheet
            if "xl/workbook.xml" in namelist:
                if has_vba:
                    return (
                        "application/vnd.ms-excel.sheet.macroEnabled.12",
                        ".xlsm",
                        "office",
                        True,
                        False,
                        "Macro-enabled Microsoft Excel Workbook",
                    )
                return (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".xlsx",
                    "office",
                    False,
                    False,
                    "Microsoft Excel Workbook (XLSX)",
                )

            # PowerPoint Presentation
            if "ppt/presentation.xml" in namelist:
                if has_vba:
                    return (
                        "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
                        ".pptm",
                        "office",
                        True,
                        False,
                        "Macro-enabled Microsoft PowerPoint Presentation",
                    )
                return (
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    ".pptx",
                    "office",
                    False,
                    False,
                    "Microsoft PowerPoint Presentation (PPTX)",
                )

            # OpenDocument Text
            if "mimetype" in namelist:
                try:
                    mime_content = zf.read("mimetype").decode("utf-8", errors="ignore").strip()
                    if "opendocument.text" in mime_content:
                        return (
                            "application/vnd.oasis.opendocument.text",
                            ".odt",
                            "office",
                            False,
                            False,
                            "OpenDocument Text (ODT)",
                        )
                    if "opendocument.spreadsheet" in mime_content:
                        return (
                            "application/vnd.oasis.opendocument.spreadsheet",
                            ".ods",
                            "office",
                            False,
                            False,
                            "OpenDocument Spreadsheet (ODS)",
                        )
                except Exception:
                    pass

            # Java Archive (JAR)
            if "META-INF/MANIFEST.MF" in namelist:
                return (
                    "application/java-archive",
                    ".jar",
                    "executable",
                    False,
                    True,
                    "Java Executable Archive (JAR)",
                )

            # Android Package (APK)
            if "AndroidManifest.xml" in namelist:
                return (
                    "application/vnd.android.package-archive",
                    ".apk",
                    "executable",
                    False,
                    True,
                    "Android Application Package (APK)",
                )

            # Generic ZIP Archive
            return (
                "application/zip",
                ".zip",
                "archive",
                False,
                False,
                f"Standard ZIP Archive ({len(namelist)} entries)",
            )
    except Exception:
        return (
            "application/zip",
            ".zip",
            "archive",
            False,
            False,
            "ZIP Archive (Damaged or Encrypted Header)",
        )


def detect_file_type(data: bytes, filename: str = "document") -> TypeDetectionResult:
    """Analyze raw bytes to determine true MIME type, family, executable/macro flags, and extension mismatch."""
    header = data[:4096] if data else b""
    ext = os.path.splitext(filename)[1].lower() if filename else ""

    # 1. Executables & PE/MZ binaries
    if header.startswith(b"MZ"):
        is_mismatch = ext not in (".exe", ".dll", ".scr", ".com", ".sys")
        return TypeDetectionResult(
            mime_type="application/x-dosexec",
            extension=".exe",
            family="executable",
            is_macro_enabled=False,
            is_executable=True,
            is_archive=False,
            extension_mismatch=is_mismatch,
            detection_method="magic_bytes",
            description="Windows Executable / Dynamic Link Library (PE/MZ)",
        )

    if header.startswith(b"\x7fELF"):
        is_mismatch = ext not in (".bin", ".elf", ".so", "")
        return TypeDetectionResult(
            mime_type="application/x-elf",
            extension=".elf",
            family="executable",
            is_macro_enabled=False,
            is_executable=True,
            is_archive=False,
            extension_mismatch=is_mismatch,
            detection_method="magic_bytes",
            description="Unix Executable and Linkable Format (ELF)",
        )

    if header.startswith((b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe")):
        # Note: \xca\xfe\xba\xbe can also be Java class bytecode, both are executable
        is_mismatch = ext not in (".dylib", ".macho", ".class", "")
        return TypeDetectionResult(
            mime_type="application/x-mach-binary",
            extension=".bin",
            family="executable",
            is_macro_enabled=False,
            is_executable=True,
            is_archive=False,
            extension_mismatch=is_mismatch,
            detection_method="magic_bytes",
            description="Mach-O Binary / Java Bytecode",
        )

    # 2. Microsoft OLE Compound Document (MSI / Legacy Office DOC, XLS, PPT)
    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        # Check if MSI installer
        if b"MsiDigitalSignatureEx" in header or ext == ".msi":
            return TypeDetectionResult(
                mime_type="application/x-msi",
                extension=".msi",
                family="executable",
                is_macro_enabled=False,
                is_executable=True,
                is_archive=False,
                extension_mismatch=ext != ".msi",
                detection_method="magic_bytes",
                description="Microsoft Installer Package (MSI)",
            )
        # Legacy Office file (potentially macro bearing)
        has_vba_ole = b"_VBA_PROJECT" in data[:65536] or b"VBA" in data[:65536]
        return TypeDetectionResult(
            mime_type="application/x-ole-storage",
            extension=ext if ext in (".doc", ".xls", ".ppt") else ".doc",
            family="office",
            is_macro_enabled=has_vba_ole,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext not in (".doc", ".xls", ".ppt"),
            detection_method="magic_bytes",
            description=f"Legacy Microsoft OLE Compound Document ({'Macro-enabled' if has_vba_ole else 'Clean'})",
        )

    # 3. PDF Document
    if header.startswith(b"%PDF-"):
        is_mismatch = ext != ".pdf"
        return TypeDetectionResult(
            mime_type="application/pdf",
            extension=".pdf",
            family="pdf",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=is_mismatch,
            detection_method="magic_bytes",
            description="Portable Document Format (PDF)",
        )

    # 4. Standard Images
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return TypeDetectionResult(
            mime_type="image/png",
            extension=".png",
            family="image",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext != ".png",
            detection_method="magic_bytes",
            description="Portable Network Graphics (PNG)",
        )

    if header.startswith(b"\xff\xd8\xff"):
        return TypeDetectionResult(
            mime_type="image/jpeg",
            extension=".jpg",
            family="image",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext not in (".jpg", ".jpeg"),
            detection_method="magic_bytes",
            description="JPEG Image",
        )

    if header.startswith((b"GIF87a", b"GIF89a")):
        return TypeDetectionResult(
            mime_type="image/gif",
            extension=".gif",
            family="image",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext != ".gif",
            detection_method="magic_bytes",
            description="Graphics Interchange Format (GIF)",
        )

    if header.startswith((b"II*\x00", b"MM\x00*")):
        return TypeDetectionResult(
            mime_type="image/tiff",
            extension=".tiff",
            family="image",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext not in (".tif", ".tiff"),
            detection_method="magic_bytes",
            description="Tagged Image File Format (TIFF)",
        )

    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return TypeDetectionResult(
            mime_type="image/webp",
            extension=".webp",
            family="image",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext != ".webp",
            detection_method="magic_bytes",
            description="WebP Image",
        )

    if header.startswith(b"BM"):
        return TypeDetectionResult(
            mime_type="image/bmp",
            extension=".bmp",
            family="image",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext != ".bmp",
            detection_method="magic_bytes",
            description="Bitmap Image (BMP)",
        )

    # 5. ZIP and OpenXML Office Archives
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        mime, expected_ext, family, is_macro, is_exec, desc = _inspect_zip_internals(data)
        is_mismatch = ext != expected_ext and not (ext in (".zip", ".docx", ".xlsx", ".pptx", ".odt") and family == "office")
        return TypeDetectionResult(
            mime_type=mime,
            extension=expected_ext,
            family=family,
            is_macro_enabled=is_macro,
            is_executable=is_exec,
            is_archive=family == "archive",
            extension_mismatch=is_mismatch,
            detection_method="zip_inspection",
            description=desc,
        )

    # 6. Compressed Archives (7z, tar, gzip, bzip2)
    if header.startswith(b"7z\xbc\xaf\x27\x1c"):
        return TypeDetectionResult(
            mime_type="application/x-7z-compressed",
            extension=".7z",
            family="archive",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=True,
            extension_mismatch=ext != ".7z",
            detection_method="magic_bytes",
            description="7-Zip Compressed Archive",
        )

    if header.startswith(b"\x1f\x8b"):
        return TypeDetectionResult(
            mime_type="application/gzip",
            extension=".gz",
            family="archive",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=True,
            extension_mismatch=ext not in (".gz", ".tgz"),
            detection_method="magic_bytes",
            description="Gzip Compressed Archive",
        )

    if header.startswith(b"BZh"):
        return TypeDetectionResult(
            mime_type="application/x-bzip2",
            extension=".bz2",
            family="archive",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=True,
            extension_mismatch=ext not in (".bz2", ".tbz2"),
            detection_method="magic_bytes",
            description="Bzip2 Compressed Archive",
        )

    if len(header) >= 262 and header[257:262] == b"ustar":
        return TypeDetectionResult(
            mime_type="application/x-tar",
            extension=".tar",
            family="archive",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=True,
            extension_mismatch=ext != ".tar",
            detection_method="magic_bytes",
            description="Tape Archive (TAR)",
        )

    # 7. Rich Text Format (RTF)
    if header.startswith(b"{\\rtf"):
        return TypeDetectionResult(
            mime_type="application/rtf",
            extension=".rtf",
            family="text",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext != ".rtf",
            detection_method="magic_bytes",
            description="Rich Text Format Document (RTF)",
        )

    # 8. Script detection by shebang or script tags
    first_clean = header.lstrip()
    if first_clean.startswith(b"#!"):
        shebang = first_clean[:128].decode("utf-8", errors="ignore").lower()
        script_ext = ".sh"
        if "python" in shebang:
            script_ext = ".py"
        elif "node" in shebang or "js" in shebang:
            script_ext = ".js"
        elif "bash" in shebang or "sh" in shebang:
            script_ext = ".sh"
        return TypeDetectionResult(
            mime_type="application/x-sh",
            extension=script_ext,
            family="script",
            is_macro_enabled=False,
            is_executable=True,
            is_archive=False,
            extension_mismatch=ext not in (".sh", ".py", ".js", ".bash"),
            detection_method="magic_bytes",
            description=f"Script executable via shebang ({shebang.splitlines()[0]})",
        )

    if (
        first_clean.startswith((b"REM ", b"@echo"))
        or (ext in (".bat", ".cmd") and b"echo " in first_clean.lower())
    ):
        return TypeDetectionResult(
            mime_type="application/x-bat",
            extension=".bat",
            family="script",
            is_macro_enabled=False,
            is_executable=True,
            is_archive=False,
            extension_mismatch=ext not in (".bat", ".cmd"),
            detection_method="text_sniff",
            description="Windows Batch Script (.bat/.cmd)",
        )

    # 9. Structured text (HTML, XML, JSON, CSV, EML)
    text_sample = header[:1024].decode("utf-8", errors="ignore").strip()

    if text_sample.startswith(("<!DOCTYPE html", "<html")) or "<body" in text_sample.lower():
        return TypeDetectionResult(
            mime_type="text/html",
            extension=".html",
            family="text",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext not in (".html", ".htm"),
            detection_method="text_sniff",
            description="HyperText Markup Language (HTML)",
        )

    if text_sample.startswith("<?xml") or (text_sample.startswith("<") and ">" in text_sample and not text_sample.startswith("<!")):
        return TypeDetectionResult(
            mime_type="application/xml",
            extension=".xml",
            family="data",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext != ".xml",
            detection_method="text_sniff",
            description="Extensible Markup Language (XML)",
        )

    if (text_sample.startswith("{") and text_sample.endswith("}")) or (text_sample.startswith("[") and text_sample.endswith("]")) or ext == ".json":
        # Verify basic JSON structure
        if re.search(r'["\']\s*:\s*', text_sample) or ext == ".json":
            return TypeDetectionResult(
                mime_type="application/json",
                extension=".json",
                family="data",
                is_macro_enabled=False,
                is_executable=False,
                is_archive=False,
                extension_mismatch=ext != ".json",
                detection_method="text_sniff",
                description="JavaScript Object Notation (JSON)",
            )

    # Email message format
    if "From:" in text_sample and ("To:" in text_sample or "Subject:" in text_sample or "MIME-Version:" in text_sample):
        return TypeDetectionResult(
            mime_type="message/rfc822",
            extension=".eml",
            family="email",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext not in (".eml", ".msg"),
            detection_method="text_sniff",
            description="RFC 822 Email Message (EML)",
        )

    # CSV / TSV check
    if ext in (".csv", ".tsv"):
        sep = "\t" if ext == ".tsv" else ","
        lines = [line for line in text_sample.splitlines() if line.strip()]
        if len(lines) >= 1 and sep in lines[0]:
            return TypeDetectionResult(
                mime_type="text/tab-separated-values" if ext == ".tsv" else "text/csv",
                extension=ext,
                family="data",
                is_macro_enabled=False,
                is_executable=False,
                is_archive=False,
                extension_mismatch=False,
                detection_method="text_sniff",
                description=f"Delimited Data ({'TSV' if ext == '.tsv' else 'CSV'})",
            )

    # Markdown / Plain text
    try:
        data[:8192].decode("utf-8")
        is_plain = True
    except UnicodeDecodeError:
        is_plain = False

    if is_plain:
        mime = "text/markdown" if ext == ".md" else "text/plain"
        plain_exts = (".txt", ".md", ".log", ".ini", ".cfg", ".yaml", ".yml", ".env", ".conf", ".properties", "")
        return TypeDetectionResult(
            mime_type=mime,
            extension=ext if ext in plain_exts and ext else ".txt",
            family="text",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext not in plain_exts,
            detection_method="text_sniff",
            description=f"Plain Text Document ({'Markdown' if ext == '.md' else 'TXT'})",
        )

    # Audio/Video check
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
        return TypeDetectionResult(
            mime_type="audio/mpeg",
            extension=".mp3",
            family="media",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext != ".mp3",
            detection_method="magic_bytes",
            description="MPEG Audio Layer 3 (MP3)",
        )

    if len(header) >= 8 and header[4:8] == b"ftyp":
        return TypeDetectionResult(
            mime_type="video/mp4",
            extension=".mp4",
            family="media",
            is_macro_enabled=False,
            is_executable=False,
            is_archive=False,
            extension_mismatch=ext not in (".mp4", ".mov", ".m4a"),
            detection_method="magic_bytes",
            description="MP4 / QuickTime Video Container",
        )

    # Fallback: Unknown Binary Octet Stream
    return TypeDetectionResult(
        mime_type="application/octet-stream",
        extension=ext if ext else ".bin",
        family="binary",
        is_macro_enabled=False,
        is_executable=False,
        is_archive=False,
        extension_mismatch=False,
        detection_method="fallback",
        description="Arbitrary Binary Stream",
    )
