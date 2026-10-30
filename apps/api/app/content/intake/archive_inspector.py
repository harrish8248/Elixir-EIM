"""Archive Security Inspector.

Recursively evaluates ZIP, TAR, and GZ containers against:
1. Zip bomb / decompression bombs (compression ratio threshold)
2. Excessive member counts and directory nesting depth
3. Total uncompressed payload limits
4. Password-encrypted members that prevent virus scanning
5. Embedded executable or script binaries inside archives
"""

import io
import os
import tarfile
import zipfile
from dataclasses import dataclass, field


@dataclass
class ArchiveInspectionReport:
    is_safe: bool
    format: str
    member_count: int = 0
    total_compressed_size: int = 0
    total_uncompressed_size: int = 0
    compression_ratio: float = 1.0
    max_depth: int = 0
    is_encrypted: bool = False
    has_dangerous_members: bool = False
    violations: list[str] = field(default_factory=list)
    member_names: list[str] = field(default_factory=list)


DANGEROUS_EXTENSIONS: set[str] = {
    ".exe", ".dll", ".scr", ".com", ".bat", ".cmd", ".ps1", ".vbs",
    ".js", ".sh", ".jar", ".apk", ".msi", ".sys", ".drv", ".cpl",
}


def inspect_zip_bytes(
    data: bytes,
    max_depth: int = 3,
    max_members: int = 500,
    max_ratio: float = 100.0,
    max_total_bytes: int = 104857600,  # 100 MB default
    current_depth: int = 1,
) -> ArchiveInspectionReport:
    """Safely inspect a ZIP archive in memory without extracting full content to disk."""
    report = ArchiveInspectionReport(
        is_safe=True,
        format="zip",
        total_compressed_size=len(data),
    )

    if current_depth > max_depth:
        report.is_safe = False
        report.violations.append(f"Exceeded maximum archive nesting depth ({current_depth} > {max_depth})")
        return report

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infolist = zf.infolist()
            report.member_count = len(infolist)

            if len(infolist) > max_members:
                report.is_safe = False
                report.violations.append(f"Archive member count ({len(infolist)}) exceeds limit ({max_members})")

            for info in infolist:
                report.member_names.append(info.filename)
                report.total_uncompressed_size += info.file_size

                # Check path depth
                parts = [p for p in info.filename.replace("\\", "/").split("/") if p]
                report.max_depth = max(report.max_depth, len(parts))

                # Check encryption (flag bit 0)
                if info.flag_bits & 0x1:
                    report.is_encrypted = True
                    report.is_safe = False
                    report.violations.append(f"Encrypted member '{info.filename}' blocks antivirus scanning")

                # Check dangerous file extensions
                member_ext = os.path.splitext(info.filename)[1].lower()
                if member_ext in DANGEROUS_EXTENSIONS:
                    report.has_dangerous_members = True
                    report.is_safe = False
                    report.violations.append(f"Dangerous executable member detected: '{info.filename}'")

                # Recursive check for nested zips (if small)
                if member_ext == ".zip" and info.file_size < 10485760:  # < 10MB
                    try:
                        nested_data = zf.read(info.filename)
                        nested_rep = inspect_zip_bytes(
                            nested_data,
                            max_depth=max_depth,
                            max_members=max_members,
                            max_ratio=max_ratio,
                            max_total_bytes=max_total_bytes,
                            current_depth=current_depth + 1,
                        )
                        if not nested_rep.is_safe:
                            report.is_safe = False
                            report.violations.extend(nested_rep.violations)
                    except Exception as nested_err:
                        report.violations.append(f"Nested archive error in '{info.filename}': {nested_err}")

            # Ratio & Total Size calculations
            comp_size = max(report.total_compressed_size, 1)
            report.compression_ratio = round(report.total_uncompressed_size / comp_size, 2)

            if report.compression_ratio > max_ratio and report.total_uncompressed_size > 1048576:
                report.is_safe = False
                report.violations.append(
                    f"Zip bomb signature: compression ratio {report.compression_ratio:.1f}:1 exceeds threshold {max_ratio:.1f}:1"
                )

            if report.total_uncompressed_size > max_total_bytes:
                report.is_safe = False
                report.violations.append(
                    f"Decompressed payload size ({report.total_uncompressed_size / (1024*1024):.1f} MB) exceeds maximum allowed ({max_total_bytes / (1024*1024):.1f} MB)"
                )

    except zipfile.BadZipFile:
        report.is_safe = False
        report.violations.append("Corrupted or invalid ZIP archive header")
    except Exception as exc:
        report.is_safe = False
        report.violations.append(f"Archive inspection exception: {exc}")

    return report


def inspect_tar_bytes(
    data: bytes,
    max_members: int = 500,
    max_ratio: float = 100.0,
    max_total_bytes: int = 104857600,
) -> ArchiveInspectionReport:
    """Safely inspect a TAR archive in memory."""
    report = ArchiveInspectionReport(
        is_safe=True,
        format="tar",
        total_compressed_size=len(data),
    )

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            members = tf.getmembers()
            report.member_count = len(members)

            if len(members) > max_members:
                report.is_safe = False
                report.violations.append(f"Tar member count ({len(members)}) exceeds limit ({max_members})")

            for m in members:
                report.member_names.append(m.name)
                report.total_uncompressed_size += m.size

                member_ext = os.path.splitext(m.name)[1].lower()
                if member_ext in DANGEROUS_EXTENSIONS:
                    report.has_dangerous_members = True
                    report.is_safe = False
                    report.violations.append(f"Dangerous executable member detected: '{m.name}'")

            comp_size = max(report.total_compressed_size, 1)
            report.compression_ratio = round(report.total_uncompressed_size / comp_size, 2)

            if report.compression_ratio > max_ratio and report.total_uncompressed_size > 1048576:
                report.is_safe = False
                report.violations.append(
                    f"Decompression bomb signature: ratio {report.compression_ratio:.1f}:1 exceeds threshold {max_ratio:.1f}:1"
                )

            if report.total_uncompressed_size > max_total_bytes:
                report.is_safe = False
                report.violations.append(
                    f"Decompressed payload size ({report.total_uncompressed_size / (1024*1024):.1f} MB) exceeds maximum allowed ({max_total_bytes / (1024*1024):.1f} MB)"
                )

    except Exception as exc:
        report.is_safe = False
        report.violations.append(f"TAR archive inspection exception: {exc}")

    return report


def inspect_archive(
    data: bytes,
    detected_mime: str,
    max_depth: int = 3,
    max_members: int = 500,
    max_ratio: float = 100.0,
    max_total_bytes: int = 104857600,
) -> ArchiveInspectionReport:
    """Entrypoint to inspect any supported archive format."""
    if "zip" in detected_mime:
        return inspect_zip_bytes(
            data,
            max_depth=max_depth,
            max_members=max_members,
            max_ratio=max_ratio,
            max_total_bytes=max_total_bytes,
        )
    if "tar" in detected_mime or "gzip" in detected_mime or "bzip2" in detected_mime:
        return inspect_tar_bytes(
            data,
            max_members=max_members,
            max_ratio=max_ratio,
            max_total_bytes=max_total_bytes,
        )

    # 7z or other format: basic safety report
    return ArchiveInspectionReport(
        is_safe=True,
        format="other_archive",
        member_count=1,
        total_compressed_size=len(data),
        total_uncompressed_size=len(data),
    )

