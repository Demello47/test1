import os
import stat
import getpass
from pathlib import Path
from datetime import datetime

import paramiko


# ==========================================================
# SETTINGS
# ==========================================================

# Файл со списком серийных номеров.
# Один serial number на одной строке.
SERIALS_FILE = Path("serials.txt")


# SSH / SFTP server
SSH_HOST = "SERVER_IP_OR_HOSTNAME"
SSH_PORT = 22
SSH_USERNAME = "username"


# Удалённая папка на сервере,
# где нужно рекурсивно искать ZIP.
REMOTE_ROOT = "/path/to/archive/root"


# Локальная папка для скачанных ZIP.
DOWNLOAD_DIR = Path(
    r"C:\Logs\DOWNLOADED_ZIPS"
)


# Отчёты
DOWNLOADED_FILE = Path(
    "downloaded_serials.txt"
)

MISSING_FILE = Path(
    "missing_serials.txt"
)

REPORT_FILE = Path(
    "download_report.txt"
)


# ==========================================================
# LOAD SERIAL NUMBERS
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
    ) as file:

        for line in file:

            serial = line.strip()

            if not serial:
                continue

            serials.append(
                serial
            )

    return serials


# ==========================================================
# SSH / SFTP CONNECTION
# ==========================================================

def connect_sftp():

    # Пароль не сохраняется в коде.
    # При вводе на экране ничего не отображается.
    password = getpass.getpass(
        "SSH password: "
    )

    client = paramiko.SSHClient()

    # Для первого теста автоматически принимаем
    # неизвестный host key.
    client.set_missing_host_key_policy(
        paramiko.AutoAddPolicy()
    )

    print(
        f"Connecting to "
        f"{SSH_HOST}:{SSH_PORT}..."
    )

    client.connect(
        hostname=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USERNAME,
        password=password,

        look_for_keys=False,
        allow_agent=False,

        timeout=30,
        banner_timeout=30,
        auth_timeout=30
    )

    print(
        "SSH connected."
    )

    sftp = client.open_sftp()

    print(
        "SFTP connected."
    )

    return client, sftp


# ==========================================================
# RECURSIVE REMOTE WALK
# ==========================================================

def walk_remote(
    sftp,
    remote_dir
):

    try:

        entries = sftp.listdir_attr(
            remote_dir
        )

    except OSError as error:

        print(
            f"Cannot read remote directory: "
            f"{remote_dir}"
        )

        print(
            f"Reason: {error}"
        )

        return

    for entry in entries:

        remote_path = (
            remote_dir.rstrip("/")
            + "/"
            + entry.filename
        )

        # Directory
        if stat.S_ISDIR(
            entry.st_mode
        ):

            yield from walk_remote(
                sftp,
                remote_path
            )

        # Regular file
        elif stat.S_ISREG(
            entry.st_mode
        ):

            yield (
                remote_path,
                entry
            )


# ==========================================================
# BUILD ZIP INDEX
#
# Сервер сканируется только ОДИН раз.
# После этого поиск serial идёт по локальному списку ZIP.
# ==========================================================

def build_zip_index(
    sftp
):

    print()
    print(
        "=" * 70
    )

    print(
        "SCANNING REMOTE ZIP FILES"
    )

    print(
        "=" * 70
    )

    print(
        f"Remote root: "
        f"{REMOTE_ROOT}"
    )

    print()

    zip_files = []

    total_files = 0
    total_zips = 0

    for (
        remote_path,
        attrs
    ) in walk_remote(
        sftp,
        REMOTE_ROOT
    ):

        total_files += 1

        if not remote_path.lower().endswith(
            ".zip"
        ):
            continue

        total_zips += 1

        zip_files.append({

            "path":
                remote_path,

            "name":
                os.path.basename(
                    remote_path
                ),

            "mtime":
                attrs.st_mtime,

            "size":
                attrs.st_size,
        })

        if total_zips % 500 == 0:

            print(
                f"ZIP indexed: "
                f"{total_zips:,}",
                flush=True
            )

    print()

    print(
        f"Remote files scanned: "
        f"{total_files:,}"
    )

    print(
        f"ZIP files indexed:    "
        f"{total_zips:,}"
    )

    print()

    return zip_files


# ==========================================================
# FIND NEWEST ZIP FOR SERIAL
#
# Serial может быть в любом месте имени ZIP.
#
# Если найдено несколько ZIP для одного serial,
# выбирается самый новый по modification time.
# ==========================================================

def find_newest_zip(
    serial,
    zip_index
):

    serial_lower = (
        serial.lower()
    )

    matches = []

    for item in zip_index:

        if (
            serial_lower
            in item["name"].lower()
        ):

            matches.append(
                item
            )

    if not matches:

        return None, 0

    newest = max(
        matches,
        key=lambda item:
        item["mtime"]
    )

    return (
        newest,
        len(matches)
    )


# ==========================================================
# DOWNLOAD FILE
# ==========================================================

def download_file(
    sftp,
    remote_file,
    local_file
):

    print(
        "Downloading:"
    )

    print(
        f"  FROM: {remote_file}"
    )

    print(
        f"  TO:   {local_file}"
    )

    sftp.get(
        remote_file,
        str(local_file)
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    # ======================================================
    # CHECK SETTINGS
    # ======================================================

    if (
        SSH_HOST
        == "SERVER_IP_OR_HOSTNAME"
    ):

        print(
            "ERROR: Set SSH_HOST first."
        )

        return

    if (
        SSH_USERNAME
        == "username"
    ):

        print(
            "ERROR: Set SSH_USERNAME first."
        )

        return

    if (
        REMOTE_ROOT
        == "/path/to/archive/root"
    ):

        print(
            "ERROR: Set REMOTE_ROOT first."
        )

        return


    # ======================================================
    # CREATE LOCAL DOWNLOAD DIRECTORY
    # ======================================================

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # ======================================================
    # LOAD SERIAL NUMBERS
    # ======================================================

    try:

        serials = load_serials()

    except Exception as error:

        print(
            f"ERROR: {error}"
        )

        return


    print(
        f"Serial numbers loaded: "
        f"{len(serials)}"
    )


    if not serials:

        print(
            "No serial numbers found."
        )

        return


    client = None
    sftp = None

    downloaded = []
    missing = []
    report = []


    try:

        # ==================================================
        # CONNECT
        # ==================================================

        client, sftp = connect_sftp()


        # ==================================================
        # INDEX ZIP FILES ON SERVER
        # ==================================================

        zip_index = build_zip_index(
            sftp
        )


        if not zip_index:

            print(
                "No ZIP files found "
                "in remote directory."
            )

            return


        # ==================================================
        # PROCESS EACH SERIAL
        # ==================================================

        for (
            number,
            serial
        ) in enumerate(
            serials,
            start=1
        ):

            print()
            print(
                "=" * 70
            )

            print(
                f"[{number}/{len(serials)}] "
                f"Serial: {serial}"
            )

            print(
                "=" * 70
            )


            newest, match_count = (
                find_newest_zip(
                    serial,
                    zip_index
                )
            )


            # ==============================================
            # NOT FOUND
            # ==============================================

            if newest is None:

                print(
                    "ZIP NOT FOUND"
                )

                missing.append(
                    serial
                )

                report.append({

                    "serial":
                        serial,

                    "status":
                        "NOT_FOUND",

                    "matches":
                        0,

                    "mtime":
                        "",

                    "size":
                        "",

                    "remote":
                        "",

                    "local":
                        "",
                })

                continue


            # ==============================================
            # FOUND
            # ==============================================

            remote_path = newest[
                "path"
            ]

            modified_time = (
                datetime.fromtimestamp(
                    newest["mtime"]
                )
                .strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )


            print(
                f"Matching ZIP files: "
                f"{match_count}"
            )

            print(
                "Newest ZIP:"
            )

            print(
                f"  {remote_path}"
            )

            print(
                "Modified:"
            )

            print(
                f"  {modified_time}"
            )

            print(
                "Size:"
            )

            print(
                f"  "
                f"{newest['size']:,} bytes"
            )


            # ==============================================
            # LOCAL FILE NAME
            #
            # Добавляем serial в начало имени.
            # Это предотвращает конфликты имён.
            # ==============================================

            local_name = (
                f"{serial}__"
                f"{newest['name']}"
            )

            local_path = (
                DOWNLOAD_DIR
                / local_name
            )


            # ==============================================
            # DOWNLOAD
            # ==============================================

            try:

                download_file(
                    sftp,
                    remote_path,
                    local_path
                )

            except Exception as error:

                print(
                    f"DOWNLOAD FAILED: "
                    f"{error}"
                )

                missing.append(
                    serial
                )

                report.append({

                    "serial":
                        serial,

                    "status":
                        "DOWNLOAD_FAILED",

                    "matches":
                        match_count,

                    "mtime":
                        modified_time,

                    "size":
                        newest["size"],

                    "remote":
                        remote_path,

                    "local":
                        str(local_path),
                })

                continue


            # ==============================================
            # VERIFY DOWNLOAD
            # ==============================================

            if not local_path.is_file():

                print(
                    "ERROR: File was not created."
                )

                missing.append(
                    serial
                )

                continue


            local_size = (
                local_path.stat().st_size
            )


            if (
                local_size
                != newest["size"]
            ):

                print(
                    "WARNING: "
                    "Downloaded size does not match "
                    "remote file size."
                )

                status = (
                    "SIZE_MISMATCH"
                )

            else:

                status = "OK"


            print(
                "Downloaded successfully."
            )


            downloaded.append(
                serial
            )


            report.append({

                "serial":
                    serial,

                "status":
                    status,

                "matches":
                    match_count,

                "mtime":
                    modified_time,

                "size":
                    newest["size"],

                "remote":
                    remote_path,

                "local":
                    str(local_path),
            })


    # ======================================================
    # SSH AUTH ERROR
    # ======================================================

    except paramiko.AuthenticationException:

        print()
        print(
            "SSH AUTHENTICATION FAILED."
        )

        print(
            "Check username/password."
        )

        return


    # ======================================================
    # SSH GENERAL ERROR
    # ======================================================

    except paramiko.SSHException as error:

        print()
        print(
            f"SSH ERROR: {error}"
        )

        return


    except Exception as error:

        print()
        print(
            f"ERROR: {error}"
        )

        return


    finally:

        if sftp is not None:

            try:
                sftp.close()
            except Exception:
                pass

        if client is not None:

            try:
                client.close()
            except Exception:
                pass


    # ======================================================
    # WRITE DOWNLOADED SERIAL LIST
    # ======================================================

    with DOWNLOADED_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        for serial in downloaded:

            file.write(
                serial
                + "\n"
            )


    # ======================================================
    # WRITE MISSING SERIAL LIST
    # ======================================================

    with MISSING_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        for serial in missing:

            file.write(
                serial
                + "\n"
            )


    # ======================================================
    # WRITE FULL REPORT
    # ======================================================

    with REPORT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "SERIAL\t"
            "STATUS\t"
            "MATCHES\t"
            "MODIFIED\t"
            "SIZE\t"
            "REMOTE_FILE\t"
            "LOCAL_FILE\n"
        )


        for item in report:

            file.write(

                f"{item['serial']}\t"
                f"{item['status']}\t"
                f"{item['matches']}\t"
                f"{item['mtime']}\t"
                f"{item['size']}\t"
                f"{item['remote']}\t"
                f"{item['local']}\n"
            )


    # ======================================================
    # FINAL SUMMARY
    # ======================================================

    print()
    print(
        "=" * 70
    )

    print(
        "DOWNLOAD COMPLETED"
    )

    print(
        "=" * 70
    )

    print(
        f"Original serials: "
        f"{len(serials)}"
    )

    print(
        f"Downloaded:       "
        f"{len(downloaded)}"
    )

    print(
        f"Missing/errors:   "
        f"{len(missing)}"
    )

    print()

    print(
        "Downloaded list:"
    )

    print(
        f"  {DOWNLOADED_FILE}"
    )

    print(
        "Missing list:"
    )

    print(
        f"  {MISSING_FILE}"
    )

    print(
        "Full report:"
    )

    print(
        f"  {REPORT_FILE}"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()