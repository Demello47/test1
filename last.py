import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime


# ==========================================================
# SETTINGS
# ==========================================================

# Fail so spiskom serial numbers.
# Odin serial na odnoj stroke.
SERIALS_FILE = Path("serials.txt")


# Papka gde ishchem ZIP.
# Poisk budet rekursivnyj vo vseh podpapkah.
SOURCE_ROOT = Path(r"C:\Logs\ZIP_SOURCE")


# Kuda kopirovat najdennye ZIP.
ZIP_OUTPUT_DIR = Path(r"C:\Logs\FOUND_ZIPS")


# Kuda raspakovyvat ZIP.
EXTRACT_ROOT = Path(r"C:\Logs\EXTRACTED")


# Kuda kopirovat finalnye LOG.
LOG_OUTPUT_DIR = Path(r"C:\Logs\FOUND_LOGS")


# Otchety.
SCANNED_FILE = Path("scanned_serials.txt")
MISSING_FILE = Path("missing_serials.txt")
REPORT_FILE = Path("scan_report.txt")


# ==========================================================
# READ SERIAL NUMBERS
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
# FIND ALL ZIP FILES ONE TIME
#
# Eto vazhno dlja skorosti.
# My ne delaem polnyj os.walk zanovo dlja kazhdogo serial.
# ==========================================================

def build_zip_index():

    print()
    print("Indexing ZIP files...")

    zip_files = []

    for path in SOURCE_ROOT.rglob("*"):

        if (
            path.is_file()
            and path.suffix.lower() == ".zip"
        ):
            zip_files.append(path)

    print(
        f"ZIP files found: {len(zip_files)}"
    )

    return zip_files


# ==========================================================
# FIND NEWEST ZIP FOR SERIAL
# ==========================================================

def find_newest_zip(
    serial,
    zip_files
):

    matches = []

    serial_lower = serial.lower()

    for zip_path in zip_files:

        if serial_lower in zip_path.name.lower():
            matches.append(zip_path)

    if not matches:
        return None

    # Samyj novyj fail po modification time.
    newest = max(
        matches,
        key=lambda p: p.stat().st_mtime
    )

    return newest


# ==========================================================
# SAFE ZIP EXTRACTION
#
# Zashchita ot ZIP s putjami tipa ../../file
# ==========================================================

def safe_extract_zip(
    zip_path,
    destination
):

    destination.mkdir(
        parents=True,
        exist_ok=True
    )

    destination_resolved = (
        destination.resolve()
    )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as archive:

        for member in archive.infolist():

            target = (
                destination
                / member.filename
            ).resolve()

            try:

                target.relative_to(
                    destination_resolved
                )

            except ValueError:

                raise RuntimeError(
                    "Unsafe ZIP path detected: "
                    f"{member.filename}"
                )

        archive.extractall(
            destination
        )


# ==========================================================
# FIND LOG FILES INSIDE EXTRACTED DIRECTORY
#
# Serial mozhet byt v ljubom meste imeni.
#
# Primer:
#
# 000047910556_692608000023_test.log
#
# serial:
#
# 692608000023
# ==========================================================

def find_logs(
    extract_dir,
    serial
):

    matches = []

    serial_lower = serial.lower()

    for path in extract_dir.rglob("*"):

        if not path.is_file():
            continue

        if path.suffix.lower() != ".log":
            continue

        if serial_lower in path.name.lower():
            matches.append(path)

    return matches


# ==========================================================
# COPY LOG
#
# Esli najdeno neskolko LOG,
# berem samyj novyj.
# ==========================================================

def select_newest_log(log_files):

    if not log_files:
        return None

    return max(
        log_files,
        key=lambda p: p.stat().st_mtime
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    if not SOURCE_ROOT.is_dir():

        print(
            f"Source folder not found: "
            f"{SOURCE_ROOT}"
        )

        return


    ZIP_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    EXTRACT_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    LOG_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    serials = load_serials()

    print(
        f"Serial numbers loaded: "
        f"{len(serials)}"
    )


    # Indeksiruem ZIP odin raz.
    zip_files = build_zip_index()


    scanned = []
    missing = []
    report = []


    # ======================================================
    # PROCESS SERIALS
    # ======================================================

    for number, serial in enumerate(
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


        # ==================================================
        # FIND ZIP
        # ==================================================

        newest_zip = find_newest_zip(
            serial,
            zip_files
        )


        if newest_zip is None:

            print(
                "ZIP NOT FOUND"
            )

            missing.append(
                f"{serial}\tZIP_NOT_FOUND"
            )

            report.append(
                f"{serial}\tZIP_NOT_FOUND"
            )

            continue


        print(
            f"Newest ZIP: {newest_zip}"
        )


        # ==================================================
        # COPY ZIP
        # ==================================================

        copied_zip = (
            ZIP_OUTPUT_DIR
            / newest_zip.name
        )


        shutil.copy2(
            newest_zip,
            copied_zip
        )


        print(
            f"ZIP copied: {copied_zip}"
        )


        # ==================================================
        # EXTRACT
        #
        # Dlja kazhdogo serial otdelnaja papka.
        # ==================================================

        extract_dir = (
            EXTRACT_ROOT
            / serial
        )


        # Esli papka ostalas ot starogo zapuska,
        # ochishchaem ee.
        if extract_dir.exists():

            shutil.rmtree(
                extract_dir
            )


        extract_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        try:

            safe_extract_zip(
                copied_zip,
                extract_dir
            )

        except Exception as error:

            print(
                f"ZIP extraction failed: "