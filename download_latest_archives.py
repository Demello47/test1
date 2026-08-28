import os
import stat
from pathlib import Path
from datetime import datetime

import paramiko


# ==========================================================
# SETTINGS
# ==========================================================

SERIALS_FILE = Path("serials.txt")

SSH_HOST = "SERVER_IP_OR_HOSTNAME"
SSH_PORT = 22
SSH_USERNAME = "username"

# Luchshe ne hranit parol v kode.
# Esli ispolzuetsja SSH key - ukazhi put.
SSH_KEY_FILE = Path(
    r"C:\Users\YOUR_USER\.ssh\id_ed25519"
)

# Udalenaja papka na servere
REMOTE_ROOT = "/path/to/archive/root"

# Lokalnaja papka dlja skachannyh ZIP
DOWNLOAD_DIR = Path(
    r"C:\Logs\DOWNLOADED_ZIPS"
)

SCANNED_FILE = Path(
    "downloaded_serials.txt"
)

MISSING_FILE = Path(
    "missing_serials.txt"
)

REPORT_FILE = Path(
    "download_report.txt"
)


# ==========================================================
# LOAD SERIALS
# ==========================================================

def load_serials():

    if not SERIALS_FILE.is_file():
        raise FileNotFoundError(
            f"Serial list not found: {SERIALS_FILE}"
        )

    serials = []

    with SERIALS_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            serial = line.strip()

            if serial:
                serials.append(serial)

    return serials


# ==========================================================
# SSH / SFTP CONNECTION
# ==========================================================

def connect_sftp():

    client = paramiko.SSHClient()

    client.set_missing_host_key_policy(
        paramiko.AutoAddPolicy()
    )

    client.connect(
        hostname=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USERNAME,
        key_filename=str(SSH_KEY_FILE),
        look_for_keys=False,
        allow_agent=False,
        timeout=20
    )

    return client, client.open_sftp()


# ==========================================================
# RECURSIVE REMOTE WALK
# ==========================================================

def walk_remote(sftp, remote_dir):

    try:

        entries = sftp.listdir_attr(
            remote_dir
        )

    except OSError as error:

        print(
            f"Cannot read remote dir: "
            f"{remote_dir}: {error}"
        )

        return


    for entry in entries:

        remote_path = (
            remote_dir.rstrip("/")
            + "/"
            + entry.filename
        )


        if stat.S_ISDIR(
            entry.st_mode
        ):

            yield from walk_remote(
                sftp,
                remote_path
            )


        elif stat.S_ISREG(
            entry.st_mode
        ):

            yield remote_path, entry


# ==========================================================
# BUILD ZIP INDEX ONCE
# ==========================================================

def build_zip_index(sftp):

    print(
        f"Scanning remote root: "
        f"{REMOTE_ROOT}"
    )

    zip_files = []

    count = 0


    for remote_path, attrs in walk_remote(
        sftp,
        REMOTE_ROOT
    ):

        if not remote_path.lower().endswith(
            ".zip"
        ):
            continue

        zip_files.append({
            "path": remote_path,
            "name": os.path.basename(
                remote_path
            ),
            "mtime": attrs.st_mtime,
            "size": attrs.st_size
        })

        count += 1


        if count % 1000 == 0:

            print(
                f"ZIP indexed: {count:,}",
                flush=True
            )


    print(
        f"Total ZIP files: "
        f"{len(zip_files):,}"
    )

    return zip_files


# ==========================================================
# FIND NEWEST ZIP FOR SERIAL
# ==========================================================

def find_newest_zip(
    serial,
    zip_index
):

    matches = [

        item

        for item in zip_index

        if serial.lower()
        in item["name"].lower()

    ]


    if not matches:
        return None


    return max(
        matches,
        key=lambda x: x["mtime"]
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    serials = load_serials()


    print(
        f"Serials loaded: "
        f"{len(serials)}"
    )


    client = None
    sftp = None


    downloaded = []
    missing = []
    report = []


    try:

        client, sftp = connect_sftp()


        # Vazhno:
        # Server skaniruem tolko ODIN raz.
        zip_index = build_zip_index(
            sftp
        )


        for number, serial in enumerate(
            serials,
            start=1
        ):

            print()
            print(
                f"[{number}/{len(serials)}] "
                f"{serial}"
            )


            newest = find_newest_zip(
                serial,
                zip_index
            )


            if newest is None:

                print(
                    "NOT FOUND"
                )

                missing.append(
                    serial
                )

                report.append(
                    f"{serial}\tNOT_FOUND"
                )

                continue


            remote_path = newest[
                "path"
            ]


            mtime_text = (
                datetime.fromtimestamp(
                    newest["mtime"]
                )
                .strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )


            print(
                f"Newest: {remote_path}"
            )

            print(
                f"Modified: {mtime_text}"
            )


            # Dobavljaem serial v imja,
            # chtoby ne bylo konfliktov.
            local_name = (
                f"{serial}__"
                f"{newest['name']}"
            )

            local_path = (
                DOWNLOAD_DIR
                / local_name
            )


            print(
                f"Downloading -> "
                f"{local_path}"
            )


            sftp.get(
                remote_path,
                str(local_path)
            )


            downloaded.append(
                serial
            )


            report.append(
                f"{serial}\tOK\t"
                f"{mtime_text}\t"
                f"{newest['size']}\t"
                f"{remote_path}\t"
                f"{local_path}"
            )


    finally:

        if sftp is not None:
            sftp.close()

        if client is not None:
            client.close()


    # ======================================================
    # REPORTS
    # ======================================================

    with SCANNED_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        for serial in downloaded:
            f.write(
                serial + "\n"
            )


    with MISSING_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        for serial in missing:
            f.write(
                serial + "\n"
            )


    with REPORT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "SERIAL\tSTATUS\tMTIME\tSIZE\t"
            "REMOTE_FILE\tLOCAL_FILE\n"
        )

        for line in report:
            f.write(
                line + "\n"
            )


    print()
    print("=" * 70)
    print("DOWNLOAD COMPLETED")
    print("=" * 70)

    print(
        f"Original serials: "
        f"{len(serials)}"
    )

    print(
        f"Downloaded: "
        f"{len(downloaded)}"
    )

    print(
        f"Missing: "
        f"{len(missing)}"
    )


if __name__ == "__main__":
    main()