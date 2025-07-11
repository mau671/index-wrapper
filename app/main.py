import os
import requests
import patoolib
import time
import re
import signal
from urllib.parse import unquote
import argparse
from threading import Semaphore, Thread, Event
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    SpinnerColumn,
    DownloadColumn,
    TransferSpeedColumn,
    Task,
)
from queue import Queue
from typing import List, Dict, Optional, Tuple

# Service and utility imports
from app.services.uploader import upload_file
from app.services.downloader import analyze_link, download_and_process_file
from app.utils.file import url_to_folder_path, get_hash_md5
from app.services.extractor import (
    get_password_from_database,
    save_password_to_database,
    obtain_password,
)

# Global variables to handle script interruption
stop_event = Event()
active_downloads = {}  # Track active downloads for cleanup
active_threads = []  # Track active threads for proper shutdown


def handle_exit(signal: int, frame: Optional[object]) -> None:
    """
    Handles SIGINT (Ctrl+C) to gracefully terminate the script.

    Args:
        signal (int): Signal number.
        frame (Optional[object]): Current stack frame (unused).
    """
    print("\n🛑 Interrupt received! Stopping downloads...")
    stop_event.set()

    # Wait for threads to finish (with timeout)
    print("⏳ Waiting for active downloads to stop...")
    for thread in active_threads:
        if thread.is_alive():
            thread.join(timeout=5)  # Wait max 5 seconds per thread

    # Clean up incomplete downloads
    cleanup_partial_files()

    print("✅ Cleanup completed. Exiting...")
    exit(0)


def cleanup_partial_files():
    """
    Removes partial download files that were interrupted.
    """
    cleaned_files = 0
    for file_path, expected_size in active_downloads.items():
        try:
            if os.path.exists(file_path):
                actual_size = os.path.getsize(file_path)
                if actual_size < expected_size:
                    os.remove(file_path)
                    print(f"🗑️  Removed incomplete file: {os.path.basename(file_path)}")
                    cleaned_files += 1
        except Exception as e:
            print(f"⚠️  Could not remove {file_path}: {e}")

    if cleaned_files > 0:
        print(f"🧹 Cleaned up {cleaned_files} incomplete download(s)")
    active_downloads.clear()


def parse_filter_range(filter_value: str) -> Tuple[int, int]:
    """
    Parses a range in the form '12-20' and returns (12, 20).
    If the format is not valid, raises ValueError.
    """
    pattern = r"^(\d+)-(\d+)$"
    match = re.match(pattern, filter_value.strip())
    if not match:
        raise ValueError(
            "The --filter argument must be a range in the format 'start-end'."
        )
    start, end = match.groups()
    start, end = int(start), int(end)
    if start > end:
        raise ValueError("The start of the range cannot be greater than the end.")
    return start, end


def analyze_and_download(
    url: str,
    site_type: str,
    use_auth: bool,
    simultaneous_downloads: int,
    delete_after: bool,
    upload: bool,
    group_name: Optional[str],
    files_limit: Optional[int],
    stats_one_line: bool,
    filter_range: Optional[str],
    base_folder: Optional[str],
) -> None:
    """
    Analyzes the URL for downloadable files and processes them.

    Args:
        url (str): The URL to analyze and download from.
        site_type (str): The type of the site (e.g., 'donwa/goindex', 'spencerwooo/onedrive').
        use_auth (bool): Whether to use HTTP authentication.
        simultaneous_downloads (int): Number of simultaneous downloads allowed.
        delete_after (bool): Whether to delete files after decompression.
        upload (bool): Whether to upload the files after download.
        group_name (Optional[str]): Group name for cloud upload.
        files_limit (Optional[int]): Limit of files to download in a batch.
        stats_one_line (bool): Whether to display progress in a single line.
        filter_range (Optional[str]): Rango de archivos a descargar en formato "inicio-fin".
        base_folder (Optional[str]): Base folder for downloading and processing files.
    """
    print("Analyzing link...", end="", flush=True)
    links = analyze_link(url, site_type, use_auth)

    while not links:
        print("\rNo links found, retrying...", end="", flush=True)
        time.sleep(5)
        links = analyze_link(url, site_type, use_auth)

    print(f"\rFound {len(links)} files, starting download.")

    # ----------------------------------------------------------------
    # Filter handling: filter files according to the requested range.
    # ----------------------------------------------------------------
    if filter_range:
        try:
            start, end = parse_filter_range(filter_range)
            # Adjustment if the indices are 1-based:
            # links[0] would correspond to the first file
            # Therefore, to download 12-20,
            # the slicing would be links[11:20].
            links = links[start - 1 : end]
            print(
                f"Filtering files from {start} to {end}. Total after filter: {len(links)}"
            )
        except ValueError as e:
            print(f"Error in filter range: {e}")
            return

    if base_folder:
        base_folder = os.path.join(base_folder, url_to_folder_path(url, site_type))
    else:
        base_folder = url_to_folder_path(url, site_type)

    os.makedirs(base_folder, exist_ok=True)

    semaphore = Semaphore(simultaneous_downloads)

    while links:
        current_batch = links[:files_limit] if files_limit else links
        links = links[files_limit:] if files_limit else []

        total_size = calculate_total_size(current_batch)

        download_queue = Queue()
        for link in current_batch:
            download_queue.put(link)

        part_files = {}

        if stats_one_line:
            handle_progress_single_line(
                download_queue,
                total_size,
                site_type,
                semaphore,
                base_folder,
                delete_after,
                part_files,
                simultaneous_downloads,
            )
        else:
            handle_progress_multi_line(
                download_queue,
                total_size,
                site_type,
                semaphore,
                base_folder,
                delete_after,
                part_files,
                simultaneous_downloads,
            )

        if part_files:
            process_part_files(part_files, base_folder, delete_after)

        if upload:
            upload_file(base_folder, group_name if group_name else "TK")

    print("All downloads and uploads completed.")


def calculate_total_size(links: List[str]) -> int:
    """
    Calculates the total size of files in a list of URLs.

    Args:
        links (List[str]): List of URLs.

    Returns:
        int: Total size of all files in bytes.
    """
    return sum(
        int(requests.get(link, stream=True).headers.get("content-length", 0))
        for link in links
    )


def handle_progress_single_line(
    download_queue: Queue,
    total_size: int,
    site_type: str,
    semaphore: Semaphore,
    base_folder: str,
    delete_after: bool,
    part_files: Dict[str, str],
    max_simultaneous: int,
) -> None:
    """
    Handles download progress using a single-line progress bar.

    Args:
        See `analyze_and_download`.
    """
    with Progress(
        TextColumn("[progress.description]{task.description}", justify="left"),
        TaskProgressColumn(),
        DownloadColumn(),
    ) as progress:
        title = base_folder.split("/")[-1]
        series_task = progress.add_task(
            f"[cyan]{title[:15] + '...' if len(title) > 15 else title}",
            total=total_size,
        )
        handle_tasks(
            download_queue,
            series_task,
            progress,
            site_type,
            semaphore,
            base_folder,
            delete_after,
            part_files,
            max_simultaneous,
        )


def handle_progress_multi_line(
    download_queue: Queue,
    total_size: int,
    site_type: str,
    semaphore: Semaphore,
    base_folder: str,
    delete_after: bool,
    part_files: Dict[str, str],
    max_simultaneous: int,
) -> None:
    """
    Handles download progress using a multi-line progress bar.

    Args:
        See `analyze_and_download`.
    """
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        SpinnerColumn(),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        series_task = progress.add_task(
            f"[cyan]{base_folder.split('/')[-1]}", total=total_size
        )
        handle_tasks(
            download_queue,
            series_task,
            progress,
            site_type,
            semaphore,
            base_folder,
            delete_after,
            part_files,
            max_simultaneous,
        )


def handle_tasks(
    download_queue: Queue,
    series_task: Task,
    progress: Progress,
    site_type: str,
    semaphore: Semaphore,
    base_folder: str,
    delete_after: bool,
    part_files: Dict[str, str],
    max_simultaneous: int,
) -> None:
    """
    Manages task execution for downloads.

    Args:
        See `analyze_and_download`.
    """
    tasks = []
    while not download_queue.empty() or any(task.is_alive() for task in tasks):
        # Check for stop event
        if stop_event.is_set():
            print("🛑 Stop signal received, waiting for active downloads to finish...")
            # Wait for current downloads to finish or timeout
            for task in tasks:
                if task.is_alive():
                    task.join(timeout=3)
            break

        while not download_queue.empty() and len(tasks) < max_simultaneous:
            if stop_event.is_set():
                break

            url = download_queue.get()
            local_filename = unquote(url.split("/")[-1])
            task_id = progress.add_task(
                f" └─{local_filename[:15] + '...' if len(local_filename) > 15 else local_filename}",
                start=True,
            )

            task_thread = Thread(
                target=download_and_process_file,
                args=(
                    url,
                    site_type,
                    semaphore,
                    progress,
                    task_id,
                    series_task,
                    base_folder,
                    delete_after,
                    part_files,
                    stop_event,
                ),
            )
            task_thread.daemon = True  # Allow main program to exit
            task_thread.start()
            tasks.append(task_thread)
            active_threads.append(task_thread)  # Track for cleanup

        tasks = [task for task in tasks if task.is_alive()]
        time.sleep(0.5)  # Reduced sleep for more responsive cancellation


def process_part_files(
    part_files: Dict[str, str], base_folder: str, delete_after: bool
) -> None:
    """
    Processes part files by extracting them.

    Args:
        part_files (Dict[str, str]): Dictionary of part files.
        base_folder (str): Base folder for file processing.
        delete_after (bool): Whether to delete files after processing.
    """
    print("\nProcessing multipart compressed files...")
    first_parts = [
        path
        for name, path in part_files.items()
        if re.search(r"\.part0*1\.rar$|\.parte0*1\.rar$", name)
    ]

    for first_part in first_parts:
        hash_md5 = get_hash_md5(first_part)
        password = get_password_from_database(hash_md5)

        if not password:
            password = obtain_password(first_part)
            if password:
                save_password_to_database(
                    os.path.basename(first_part), hash_md5, password
                )

        if password:
            try:
                os.makedirs(base_folder, exist_ok=True)
                patoolib.extract_archive(
                    first_part,
                    verbosity=-1,
                    program="unrar",
                    interactive=False,
                    outdir=base_folder,
                    password=password,
                )
            except Exception as e:
                print(f"Error extracting {first_part}: {e}")
        if delete_after:
            os.remove(first_part)


def main():
    """Main entry point for the application."""
    # Handle SIGINT (Ctrl+C) gracefully to terminate the script
    signal.signal(signal.SIGINT, handle_exit)

    # Create an argument parser for the command-line interface
    parser = argparse.ArgumentParser(description="Downloader and Decompressor")

    # Define command-line arguments
    parser.add_argument(
        "--url", type=str, required=True, help="The URL to download from"
    )
    parser.add_argument(
        "--site_type",
        type=str,
        required=True,
        choices=[
            "donwa/goindex",
            "maple3142/GDIndex",
            "achrou/goindex",
            "spencerwooo/onedrive",
        ],
        help="The type of the site to process",
    )
    parser.add_argument(
        "--simultaneous",
        type=int,
        default=3,
        help="The number of simultaneous downloads allowed",
    )
    parser.add_argument(
        "--delete-after",
        action="store_true",
        default=False,
        help="Delete the original file after decompression",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        default=False,
        help="Upload the downloaded and processed files to a cloud using rclone",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit the number of files to download in one batch"
    )
    parser.add_argument(
        "--stats-one-line",
        action="store_true",
        help="Print progress stats in a single line",
    )
    parser.add_argument(
        "--filter",
        type=str,
        help="Rango de archivos a descargar en el formato 'inicio-fin' (ejemplo: 12-20)",
    )
    parser.add_argument(
        "--use-auth",
        action="store_true",
        help="Use HTTP authentication for downloading",
    )
    parser.add_argument(
        "--group-name",
        type=str,
        help="Specify a group name for cloud upload organization",
    )
    parser.add_argument(
        "--base-folder",
        type=str,
        help="Specify a base folder for downloading and processing files",
    )

    # Parse command-line arguments
    args = parser.parse_args()

    # Call the main function to analyze the link and start the download process
    analyze_and_download(
        url=args.url,  # URL to process
        site_type=args.site_type,  # Type of site (e.g., GoIndex, OneDrive)
        use_auth=args.use_auth,  # Whether HTTP authentication is enabled
        simultaneous_downloads=args.simultaneous,  # Number of simultaneous downloads
        delete_after=args.delete_after,  # Whether to delete files after decompression
        upload=args.upload,  # Whether to upload files to a cloud
        group_name=args.group_name,  # Group name for cloud upload
        files_limit=args.limit,  # Limit of files to download per batch
        stats_one_line=args.stats_one_line,  # Whether to show progress in a single line
        filter_range=args.filter,  # File range to download
        base_folder=args.base_folder,  # Base folder for downloading and processing files
    )


if __name__ == "__main__":
    main()
