from typing import Optional
from config import DB_TYPE
from utils.database import client
import patoolib


def get_password_from_database(hash_md5: str) -> Optional[str]:
    """
    Retrieves a password from the database for a given MD5 hash.

    Args:
        hash_md5 (str): The MD5 hash of the file.

    Returns:
        Optional[str]: The password if found, otherwise None.
    """
    if DB_TYPE == "Supabase" and client:
        data = (
            client.table("rar_files").select("password").eq("hash", hash_md5).execute()
        )
        if data and data.data:
            return data.data[0]["password"]
    return None


def save_password_to_database(filename: str, hash_md5: str, password: str) -> None:
    """
    Saves a password to the database for a given file and its MD5 hash.

    Args:
        filename (str): The name of the file.
        hash_md5 (str): The MD5 hash of the file.
        password (str): The password to save.
    """
    if DB_TYPE == "Supabase" and client:
        client.table("rar_files").insert(
            {"filename": filename, "hash": hash_md5, "password": password}
        ).execute()


def obtain_password(file_path: str) -> Optional[str]:
    """
    Attempts to determine the password for a file by testing known passwords.

    Args:
        file_path (str): The path to the file.

    Returns:
        Optional[str]: The correct password if found, otherwise None.
    """
    passwords = [
        "(duerumonstasu!)",
        "(H4mtar0!)",
        "(TeamKurosaki)",
        "by DarthMaster",
        "by_GfS",
        "ExcAlib444h!!",
        "https://www.teamkurosaki.net/",
        "M1rum0!!",
        "TeamKurosaki",
        "teamkurosaki.net",
        "TeamKurosaki-real89mx2",
        "TeamKurosaki-Rolando96",
        "TeamKurosaki-Shingeki",
        "www.mexanime.info",
        "www.teamkurosaki.net",
        "www.lascaricaturas.com",
        "Math",
        "80stvseries",
    ]

    for password in passwords:
        try:
            patoolib.test_archive(
                file_path,
                verbosity=-1,
                program="unrar",
                interactive=False,
                password=password,
            )
            return password
        except patoolib.util.PatoolError:
            # Catching specific exception for archive testing failure
            continue
        except Exception as e:
            # Log unexpected exceptions
            print(f"Unexpected error while testing password '{password}': {e}")
            continue
    return None
