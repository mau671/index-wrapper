from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService

from urllib.parse import urlparse, unquote
import requests
import os
import time
import patoolib
from threading import Semaphore
from rich.progress import Progress, Task
from typing import List, Dict
from threading import Event

from config import HTTP_USER, HTTP_PASSWORD
from utils.file import is_parted, get_hash_md5
from services.extractor import get_password_from_database, save_password_to_database, obtain_password
from utils.driver import setup_chromedriver

def configure_webdriver() -> webdriver.Chrome:
    """
    Configures the Selenium WebDriver with appropriate options.

    Returns:
        webdriver.Chrome: Configured Chrome WebDriver instance.
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-gpu')
    options.add_argument("start-maximized")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    service = ChromeService(executable_path=setup_chromedriver())
    return webdriver.Chrome(service=service, options=options)

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
    driver = configure_webdriver()
    try:
        if use_auth:
            url = url.replace("https://", f"https://{HTTP_USER}:{HTTP_PASSWORD}@")
        driver.get(url)

        if site_type in ["donwa/goindex", "achrou/goindex"]:
            return _extract_goindex_links(driver, url)
        elif site_type == "maple3142/GDIndex":
            return _extract_gdindex_links(driver)
        elif site_type == "spencerwooo/onedrive":
            return _extract_onedrive_links(driver, url)
        else:
            return []
    except Exception as e:
        print(f"Error analyzing link: {e}")
        return []
    finally:
        driver.quit()

def _extract_goindex_links(driver: webdriver.Chrome, base_url: str) -> List[str]:
    """
    Extracts links from GoIndex pages.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
        base_url (str): Base URL of the GoIndex page.

    Returns:
        List[str]: Extracted links.
    """
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    rows = driver.find_elements(By.XPATH, '//tbody/tr')
    base_download_url = base_url.replace("0:", "0:down")
    return [f"{base_download_url}{row.find_element(By.TAG_NAME, 'td').get_attribute('title')}" for row in rows]


def _extract_gdindex_links(driver: webdriver.Chrome) -> List[str]:
    """
    Extracts links from GDIndex pages.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.

    Returns:
        List[str]: Extracted links.
    """
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    links = driver.find_elements(By.XPATH, '//a')
    return [link.get_attribute('href') for link in links if link.get_attribute('href').endswith(('rar', 'zip'))]


def _extract_onedrive_links(driver: webdriver.Chrome, base_url: str) -> List[str]:
    """
    Extracts links from OneDrive pages.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
        base_url (str): Base URL of the OneDrive page.

    Returns:
        List[str]: Extracted links.
    """
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'col-span-12')))
    elements = driver.find_elements(By.XPATH, "//a[@class='col-span-12 md:col-span-10']")
    return [
        element.get_attribute('href').replace(
            urlparse(element.get_attribute('href')).netloc,
            urlparse(element.get_attribute('href')).netloc + '/api/raw/?path='
        )
        for element in elements if not element.get_attribute('href').endswith('/')
    ]


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
    stop_event: Event
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

        local_filename = unquote(url.split('/')[-1])
        download_path = os.path.join(base_folder, local_filename)

        os.makedirs(base_folder, exist_ok=True)
        _download_file(url, download_path, progress, task, series_task, stop_event)

        if is_parted(local_filename):
            part_files[local_filename] = download_path
            print(f"Part file added: {local_filename}")
        elif local_filename.endswith('.rar'):
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
    stop_event: Event
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
        total_size = int(r.headers.get('content-length', 0))
        downloaded_size = 0
        start_time = time.time()

        with open(download_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1048576):
                if stop_event.is_set():
                    return
                f.write(chunk)
                downloaded_size += len(chunk)
                elapsed_time = time.time() - start_time
                speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
                progress.update(task, completed=downloaded_size, total=total_size, speed=speed)
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

    if not password:
        password = obtain_password(file_path)
        if password:
            save_password_to_database(os.path.basename(file_path), hash_md5, password)

    if password:
        os.makedirs(output_path, exist_ok=True)
        patoolib.extract_archive(file_path, verbosity=-1, program="unrar", interactive=False, outdir=output_path, password=password)
    if delete_after:
        os.remove(file_path)
