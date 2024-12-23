import os
import shutil
import subprocess
from typing import Optional

# Final path where the chromedriver will be saved
DRIVERS_DIR = os.path.join(os.path.dirname(__file__), "../drivers/")
CHROMEDRIVER_PATH = os.path.join(DRIVERS_DIR, "chromedriver")

def get_chrome_version() -> Optional[str]:
    """
    Retrieves the installed version of Google Chrome.

    Returns:
        str: The version of Google Chrome (e.g., '96.0.4664.110') if successful.
        None: If the version could not be determined.
    """
    try:
        chrome_version = subprocess.check_output("google-chrome --version", shell=True)
        chrome_version = chrome_version.decode("utf-8").strip().split(" ")[2]
        return chrome_version
    except Exception as e:
        print(f"Error getting Chrome version: {e}")
        return None

def is_chromedriver_compatible(driver_path: str, chrome_version: str) -> bool:
    """
    Checks if the given chromedriver matches the specified Chrome version.

    Args:
        driver_path (str): Path to the chromedriver executable.
        chrome_version (str): The version of Google Chrome installed on the system.

    Returns:
        bool: True if the chromedriver exists and is compatible, False otherwise.
    """
    if not os.path.exists(driver_path):
        return False

    try:
        result = subprocess.run([driver_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        chromedriver_version = result.stdout.decode("utf-8").strip().split(" ")[1]
        return chrome_version.startswith(chromedriver_version.split('.')[0])
    except Exception as e:
        print(f"Error checking chromedriver version at {driver_path}: {e}")
        return False

def find_chromedriver_in_path(chrome_version: str) -> Optional[str]:
    """
    Checks if a compatible chromedriver exists in the system PATH.

    Args:
        chrome_version (str): The version of Google Chrome installed on the system.

    Returns:
        str: Path to the compatible chromedriver if found, None otherwise.
    """
    try:
        result = subprocess.run(["which", "chromedriver"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        chromedriver_path = result.stdout.decode("utf-8").strip()
        if chromedriver_path and is_chromedriver_compatible(chromedriver_path, chrome_version):
            return chromedriver_path
    except Exception as e:
        print(f"Error finding chromedriver in PATH: {e}")
    return None

def download_chromedriver(chrome_version: str) -> Optional[str]:
    """
    Downloads and sets up the chromedriver executable for the specified Chrome version.

    Args:
        chrome_version (str): The version of Google Chrome installed on the system.

    Returns:
        str: The absolute path to the chromedriver executable if successful.
        None: If the setup process failed.
    """
    try:
        # Create target directory if it does not exist
        if not os.path.exists(DRIVERS_DIR):
            os.makedirs(DRIVERS_DIR)

        # URL of the chromedriver zip file
        chromedriver_url = f"https://storage.googleapis.com/chrome-for-testing-public/{chrome_version}/linux64/chromedriver-linux64.zip"

        # Download the chromedriver zip file
        zip_path = os.path.join(os.path.dirname(__file__), "chromedriver-linux64.zip")
        subprocess.run(f"wget -O {zip_path} {chromedriver_url}", shell=True, check=True)

        # Unzip the file
        subprocess.run(f"unzip -o {zip_path} -d {os.path.dirname(__file__)}", shell=True, check=True)

        # Move the executable to the target directory
        extracted_driver = os.path.join(os.path.dirname(__file__), "chromedriver-linux64/chromedriver")
        if os.path.exists(extracted_driver):
            shutil.move(extracted_driver, CHROMEDRIVER_PATH)

        # Clean up temporary files
        os.remove(zip_path)
        shutil.rmtree(os.path.join(os.path.dirname(__file__), "chromedriver-linux64"), ignore_errors=True)

        return os.path.abspath(CHROMEDRIVER_PATH)

    except Exception as e:
        print(f"Error downloading chromedriver: {e}")
        return None

def setup_chromedriver() -> Optional[str]:
    """
    Sets up the chromedriver for the installed version of Google Chrome.

    Returns:
        str: The absolute path to the chromedriver executable if successful.
        None: If the setup process failed.
    """
    chrome_version = get_chrome_version()
    if not chrome_version:
        print("Failed to retrieve Chrome version.")
        return None

    # Check for chromedriver in system PATH
    chromedriver_path = find_chromedriver_in_path(chrome_version)
    if chromedriver_path:
        print(f"Using chromedriver from PATH: {chromedriver_path}")
        return chromedriver_path

    # Check for chromedriver in the drivers directory
    if is_chromedriver_compatible(CHROMEDRIVER_PATH, chrome_version):
        print(f"Using chromedriver from drivers directory: {CHROMEDRIVER_PATH}")
        return os.path.abspath(CHROMEDRIVER_PATH)

    # Download and set up a new chromedriver
    print("Downloading a new chromedriver...")
    return download_chromedriver(chrome_version)

if __name__ == "__main__":
    chromedriver_path = setup_chromedriver()
    if chromedriver_path:
        print(f"Chromedriver ready at: {chromedriver_path}")
    else:
        print("Failed to set up Chromedriver.")
