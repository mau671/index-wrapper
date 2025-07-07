import subprocess
from typing import Optional


def setup_chromedriver() -> Optional[str]:
    """
    Locates the chromedriver installed by the 'chromium-chromedriver' package.
    """
    try:
        # Search for 'chromedriver' in the PATH
        result = subprocess.run(
            ["which", "chromedriver"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        path = result.stdout.decode("utf-8").strip()
        if path:
            print(f"Using chromedriver at: {path}")
            return path
        else:
            print("Chromedriver not found in PATH.")
            return None
    except Exception as e:
        print(f"Error finding chromedriver: {e}")
        return None


if __name__ == "__main__":
    chromedriver_path = setup_chromedriver()
    if chromedriver_path:
        print(f"Chromedriver ready at: {chromedriver_path}")
    else:
        print("Failed to set up Chromedriver.")
