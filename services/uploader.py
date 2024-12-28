import rclone_python as rclone
from config import RCLONE_REMOTE, RCLONE_CONFIG


def upload_file(path, group_name="TK"):
    """Upload the folder to a cloud with rclone"""
    rclone_options = [
        "--config",
        RCLONE_CONFIG,
        "--onedrive-chunk-size 10M",
        "--server-side-across-configs",
        "--transfers=4",
        "--checkers=8",
        "--max-transfer=750G",
        '--user-agent="ISV|rclone.org|rclone/v1.67.0"',
        "--tpslimit=8",
        "--onedrive-no-versions",
        "--onedrive-delta",
        "--onedrive-hard-delete",
        "--fast-list",
        "--check-first",
        "--order-by=size,desc",
        "--size-only",
        "--no-check-dest",
        "--ignore-checksum",
        "--log-file=/usr/src/app/rclone.log",
        "--log-level INFO",
        # Incluir solo archivos de video, .mkv .mp4 .avi
        '--include="*.{mkv,mp4,avi}"',
        "--use-mmap",
        "--buffer-size=0",
    ]
    output_path = f"{RCLONE_REMOTE}:[{group_name}]/{path}"

    rclone.move(
        path, output_path, ignore_existing=True, show_progress=True, args=rclone_options
    )
