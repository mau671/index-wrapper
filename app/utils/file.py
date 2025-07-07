import re
import hashlib
from urllib.parse import unquote, urlparse


def is_parted(nombre_archivo):
    # Define el patrón regex
    patron = r"\.part(?:\d{2}|\d)\.rar$|\.parte(?:\d{2}|\d)\.rar$"

    # Utiliza re.match para comprobar si el archivo coincide con el patrón
    if re.search(patron, nombre_archivo):
        return True
    else:
        return False


def format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0


def get_hash_md5(file_path, chunk_size=1048576):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def url_to_folder_path(url, site_type):
    parsed_url = urlparse(url)
    if site_type == "spencerwooo/onedrive":
        path = re.search(r"(?<=/).*", parsed_url.path).group(0)
    elif site_type == "achrou/goindex":
        path = re.search(r"(?<=0:/).*", parsed_url.path).group(0)

    # Apply URL decoding multiple times to handle double/triple encoding
    # Keep decoding until no more changes occur
    previous_path = ""
    path = unquote(path)
    while path != previous_path:
        previous_path = path
        path = unquote(path)

    # Remove invalid filesystem characters
    invalid_chars = r'<>:"\\|?*'
    path = re.sub(f"[{re.escape(invalid_chars)}]", "", path)

    # Remove the last segment (filename) to get the directory path
    path = "/".join(path.split("/")[:-1])

    return path
