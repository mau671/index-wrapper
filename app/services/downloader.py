from playwright.sync_api import sync_playwright, Page
from urllib.parse import urlparse, unquote
import requests
import os
import time
import patoolib
from threading import Semaphore
from rich.progress import Progress, Task
from typing import List, Dict
from threading import Event

from app.config import HTTP_USER, HTTP_PASSWORD
from app.utils.file import is_parted, get_hash_md5
from app.services.extractor import (
    get_password_from_database,
    save_password_to_database,
    obtain_password,
)


def _launch_browser():
    """Launch a headless Playwright Chromium browser with sensible defaults."""
    playwright_context = sync_playwright().start()
    browser = playwright_context.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--ignore-certificate-errors",
            "--disable-gpu",
        ],
    )
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    return playwright_context, browser, page


def analyze_link(url: str, site_type: str, use_auth: bool) -> List[str]:
    """
    Analyzes a given URL to extract download links based on the site type.

    Args:
        url (str): The URL to analyze.
        site_type (str): The type of the site (e.g., 'donwa/goindex', 'spencerwooo/onedrive').
        use_auth (bool): Whether to use HTTP authentication.

    Returns:
        List[str]: A list of extracted download links.
    """
    playwright_context, browser, page = _launch_browser()

    try:
        if use_auth:
            url = url.replace("https://", f"https://{HTTP_USER}:{HTTP_PASSWORD}@")

        # Navigate and wait for the initial DOM content.
        page.goto(url, wait_until="domcontentloaded")

        if site_type in ["donwa/goindex", "achrou/goindex"]:
            links = _extract_goindex_links(page, url)
        elif site_type == "maple3142/GDIndex":
            links = _extract_gdindex_links(page)
        elif site_type == "spencerwooo/onedrive":
            links = _extract_onedrive_links(page, url)
        else:
            links = []

        return links
    except Exception as e:
        print(f"Error analyzing link: {e}")
        return []
    finally:
        # Ensure resources are cleaned up properly.
        browser.close()
        playwright_context.stop()


def _extract_goindex_links(page: Page, base_url: str) -> List[str]:
    """
    Extracts links from GoIndex pages.

    Args:
        page (Page): The Playwright Page instance.
        base_url (str): Base URL of the GoIndex page.

    Returns:
        List[str]: Extracted links.
    """
    page.wait_for_selector("body")

    # Scroll to the bottom to ensure all lazy-loaded items are present.
    last_height = page.evaluate("document.body.scrollHeight")
    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    rows = page.query_selector_all("xpath=//tbody/tr")
    base_download_url = base_url.replace("0:", "0:down")
    links: List[str] = []
    for row in rows:
        td = row.query_selector("td")
        if td:
            title = td.get_attribute("title")
            if title:
                links.append(f"{base_download_url}{title}")

    return links


def _extract_gdindex_links(page: Page) -> List[str]:
    """
    Extracts links from GDIndex pages.

    Args:
        page (Page): The Playwright Page instance.

    Returns:
        List[str]: Extracted links.
    """
    page.wait_for_selector("body")
    anchors = page.query_selector_all("xpath=//a")
    return [
        a.get_attribute("href")
        for a in anchors
        if a.get_attribute("href") and a.get_attribute("href").endswith(("rar", "zip"))
    ]


def _extract_onedrive_links(page: Page, base_url: str) -> List[str]:
    """
    Extracts links from OneDrive pages.

    Args:
        page (Page): The Playwright Page instance.
        base_url (str): Base URL of the OneDrive page.

    Returns:
        List[str]: Extracted links.
    """
    page.wait_for_selector(".col-span-12")
    elements = page.query_selector_all("xpath=//a[@class='col-span-12 md:col-span-10']")

    processed: List[str] = []
    for el in elements:
        href = el.get_attribute("href")
        if href and not href.endswith("/"):
            processed.append(
                href.replace(
                    urlparse(href).netloc,
                    urlparse(href).netloc + "/api/raw/?path=",
                )
            )

    return processed


def download_and_process_file(
    url: str,
    site_type: str,
    semaphore: Semaphore,
    progress: Progress,
    task: Task,
    series_task: Task,
    base_folder: str,
    delete_after: bool,
    part_files: Dict[str, str],
    stop_event: Event,
) -> None:
    """
    Downloads a file from a URL and processes it (e.g., extraction, password handling).

    Args:
        url (str): File URL.
        site_type (str): Site type for handling specifics.
        semaphore (Semaphore): Semaphore for limiting simultaneous downloads.
        progress (Progress): Rich progress tracker.
        task (Task): Current task progress.
        series_task (Task): Series-level progress.
        base_folder (str): Folder to save the downloaded file.
        delete_after (bool): Whether to delete the original file after processing.
        part_files (Dict[str, str]): Dictionary to track part files.
    """
    semaphore.acquire()
    try:
        if stop_event.is_set():
            return

        local_filename = unquote(url.split("/")[-1])
        download_path = os.path.join(base_folder, local_filename)

        os.makedirs(base_folder, exist_ok=True)
        _download_file(url, download_path, progress, task, series_task, stop_event)

        if is_parted(local_filename):
            part_files[local_filename] = download_path
            print(f"Part file added: {local_filename}")
        elif local_filename.endswith(".rar"):
            _process_rar_file(download_path, base_folder, delete_after)
    except Exception as e:
        print(f"Error downloading or processing {local_filename}: {e}")
    finally:
        progress.update(task, visible=False)
        semaphore.release()


def _download_file(
    url: str,
    download_path: str,
    progress: Progress,
    task: Task,
    series_task: Task,
    stop_event: Event,
) -> None:
    """
    Downloads a file from the given URL.

    Args:
        url (str): File URL.
        download_path (str): Path to save the downloaded file.
        progress (Progress): Progress tracker.
        task (Task): Task progress.
        series_task (Task): Series-level progress.
    """
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("content-length", 0))
        downloaded_size = 0
        start_time = time.time()

        with open(download_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1048576):
                if stop_event.is_set():
                    return
                f.write(chunk)
                downloaded_size += len(chunk)
                elapsed_time = time.time() - start_time
                speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
                progress.update(
                    task, completed=downloaded_size, total=total_size, speed=speed
                )
                progress.update(series_task, advance=len(chunk))


def _process_rar_file(file_path: str, output_path: str, delete_after: bool) -> None:
    """
    Processes a .rar file by extracting it, handling passwords, and optionally deleting the file.

    Args:
        file_path (str): Path to the .rar file.
        output_path (str): Directory to extract the file.
        delete_after (bool): Whether to delete the .rar file after extraction.
    """
    hash_md5 = get_hash_md5(file_path)
    password = get_password_from_database(hash_md5)
    successful_extraction = False

    # Try with password from database first (if exists)
    if password:
        print(f"Trying stored password for {os.path.basename(file_path)}: {password}")
        if _try_extract_with_password(file_path, output_path, password):
            print(f"✓ Successfully extracted {os.path.basename(file_path)} with stored password")
            successful_extraction = True
        else:
            print(f"✗ Stored password failed for {os.path.basename(file_path)}")

    # If no stored password or stored password failed, try all known passwords
    if not successful_extraction:
        password = obtain_password(file_path, output_path, verbose=True)
        if password:
            # Save the working password to database
            save_password_to_database(os.path.basename(file_path), hash_md5, password)
            successful_extraction = True

    if not successful_extraction:
        print(f"✗ No valid password found for {os.path.basename(file_path)}")
        return  # Don't delete if extraction failed
        
    if delete_after:
        try:
            os.remove(file_path)
            print(f"Deleted {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Warning: Could not delete {os.path.basename(file_path)}: {e}")


def _try_extract_with_password(file_path: str, output_path: str, password: str) -> bool:
    """
    Attempts to extract a RAR file with a specific password.
    
    Args:
        file_path (str): Path to the RAR file.
        output_path (str): Directory to extract to.
        password (str): Password to try.
        
    Returns:
        bool: True if extraction succeeded, False otherwise.
    """
    try:
        os.makedirs(output_path, exist_ok=True)
        patoolib.extract_archive(
            file_path,
            verbosity=-1,
            program="unrar",
            interactive=False,
            outdir=output_path,
            password=password,
        )
        return True
    except Exception:
        return False
