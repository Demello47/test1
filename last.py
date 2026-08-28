import os
import shutil
import zipfile
import csv
from pathlib import Path


# ==========================================================
# CONFIG
# ==========================================================

# Gde iskat ZIP faily
SOURCE_ROOT = Path(r"C:\PATH\TO\SOURCE")

# Spisok serial numbers
SERIALS_FILE = Path(r"C:\PATH\TO\serials.txt")

# Kuda kopirovat najdennye ZIP
ZIP_OUTPUT = Path(r"C:\PATH\TO\OUTPUT\zips")

# Kuda raspakovyvat ZIP
EXTRACT_OUTPUT = Path(r"C:\PATH\TO\OUTPUT\extracted")

# Kuda sobirat finalnye LOG
LOG_OUTPUT = Path(r"C:\PATH\TO\OUTPUT\logs")

# Finalnyj CSV report
REPORT_FILE = Path(r"C:\PATH\TO\OUTPUT\scan_report.csv")

# Prostoj spisok serialov, dlja kotoryh LOG byl najden
SCANNED_SERIALS_FILE = Path(
    r"C:\PATH\TO\OUTPUT\scanned_serials.txt"
)

# Serialy, kotorye ne udalos obrabotat
MISSING_SERIALS_FILE = Path(
    r"C:\PATH\TO\OUTPUT\missing_serials.txt"
)


# ==========================================================
# READ SERIAL NUMBERS
# ==========================================================

def load_serials():

    with open(
        SERIALS_FILE,
        "r",
        encoding="utf-8-sig"
    ) as f:

        serials = [
            line.strip()
            for line in f
            if line.strip()
        ]

    # Udaljaem dublikaty,
    # no sohranjaem originalnyj porjadok
    return list(dict.fromkeys(serials))


# ==========================================================
# FIND ZIP FILES
# ==========================================================

def find_zip_files(serial):

    matches = []

    for root, dirs, files in os.walk(SOURCE_ROOT):

        for filename in files:

            if not filename.lower().endswith(".zip"):
                continue

            # Serial mozhet nahoditsja v ljubom meste
            # imeni ZIP faila
            if serial not in filename:
                continue

            full_path = Path(root) / filename

            try:
                modified_time = full_path.stat().st_mtime
            except OSError:
                continue

            matches.append(
                (
                    modified_time,
                    full_path
                )
            )

    return matches


# ==========================================================
# GET NEWEST ZIP
# ==========================================================

def get_newest_zip(serial):

    matches = find_zip_files(serial)

    if not matches:
        return None

    # Samyj novyj po Last Modified
    matches.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return matches[0][1]


# ==========================================================
# SAFE COPY
# ==========================================================

def copy_file_unique(source, destination_folder, serial):

    destination_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    destination = (
        destination_folder
        / source.name
    )

    # Esli takoe imja uzhe est,
    # dobavljaem serial.
    if destination.exists():

        destination = (
            destination_folder
            / f"{serial}_{source.name}"
        )

    shutil.copy2(
        source,
        destination
    )

    return destination


# ==========================================================
# EXTRACT ZIP
# ==========================================================

def extract_zip(zip_path, serial):

    # Otdelnaja papka dlja kazhdogo serial
    extract_folder = (
        EXTRACT_OUTPUT
        / serial
    )

    # Esli ostalis starye dannye
    if extract_folder.exists():
        shutil.rmtree(
            extract_folder
        )

    extract_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as archive:

        # Zashchita ot ZIP path traversal
        root_resolved = extract_folder.resolve()

        for member in archive.infolist():

            target = (
                extract_folder
                / member.filename
            ).resolve()

            if (
                target != root_resolved
                and root_resolved
                not in target.parents
            ):
                raise ValueError(
                    f"Unsafe ZIP path: "
                    f"{member.filename}"
                )

        archive.extractall(
            extract_folder
        )

    return extract_folder


# ==========================================================
# FIND LOG FILES
# ==========================================================

def find_matching_logs(
    extract_folder,
    serial
):

    matches = []

    for root, dirs, files in os.walk(
        extract_folder
    ):

        for filename in files:

            # Tolko .log
            if not filename.lower().endswith(
                ".log"
            ):
                continue

            # Nam ne vazhno chto stoit pered serial.
            #
            # Primer:
            #
            # 123456_692608000023_test.log
            #
            # najdetsja po:
            #
            # 692608000023
            if serial not in filename:
                continue

            full_path = (
                Path(root)
                / filename
            )

            try:
                modified_time = (
                    full_path
                    .stat()
                    .st_mtime
                )
            except OSError:
                modified_time = 0

            matches.append(
                (
                    modified_time,
                    full_path
                )
            )

    return matches


# ==========================================================
# CHOOSE LOG
# ==========================================================

def get_matching_log(
    extract_folder,
    serial
):

    matches = find_matching_logs(
        extract_folder,
        serial
    )

    if not matches:
        return None, 0

    # Esli v archive neskolko LOG
    # s etim serial,
    # berem samyj novyj.
    matches.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return (
        matches[0][1],
        len(matches)
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    serials = load_serials()

    if not serials:
        print(
            "No serial numbers found."
        )
        return

    ZIP_OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    EXTRACT_OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    LOG_OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    report = []

    scanned_serials = []

    missing_serials = []


    print(
        f"Serial numbers: {len(serials)}"
    )

    print(
        "=" * 70
    )


    for index, serial in enumerate(
        serials,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(serials)}] "
            f"Serial: {serial}"
        )


        # ==================================================
        # FIND NEWEST ZIP
        # ==================================================

        newest_zip = get_newest_zip(
            serial
        )


        if newest_zip is None:

            print(
                "  ZIP: NOT FOUND"
            )

            missing_serials.append(
                serial
            )

            report.append({
                "serial": serial,
                "status": "ZIP_NOT_FOUND",
                "source_zip": "",
                "copied_zip": "",
                "log_matches": 0,
                "source_log": "",
                "copied_log": ""
            })

            continue


        print(
            f"  ZIP found: "
            f"{newest_zip}"
        )


        # ==================================================
        # COPY ZIP
        # ==================================================

        copied_zip = copy_file_unique(
            newest_zip,
            ZIP_OUTPUT,
            serial
        )


        print(
            f"  ZIP copied: "
            f"{copied_zip}"
        )


        # ==================================================
        # EXTRACT
        # ==================================================

        try:

            extract_folder = extract_zip(
                copied_zip,
                serial
            )

        except (
            zipfile.BadZipFile,
            OSError,
            ValueError
        ) as error:

            print(
                f"  ZIP extraction ERROR: "
                f"{error}"
            )

            missing_serials.append(
                serial
            )

            report.append({
                "serial": serial,
                "status": "ZIP_ERROR",
                "source_zip": str(
                    newest_zip
                ),
                "copied_zip": str(
                    copied_zip
                ),
                "log_matches": 0,
                "source_log": "",
                "copied_log": ""
            })

            continue


        print(
            f"  Extracted: "
            f"{extract_folder}"
        )


        # ==================================================
        # FIND LOG
        # ==================================================

        log_file, match_count = (
            get_matching_log(
                extract_folder,
                serial
            )
        )


        if log_file is None:

            print(
                "  LOG: NOT FOUND"
            )

            missing_serials.append(
                serial
            )

            report.append({
                "serial": serial,
                "status": "LOG_NOT_FOUND",
                "source_zip": str(
                    newest_zip
                ),
                "copied_zip": str(
                    copied_zip
                ),
                "log_matches": 0,
                "source_log": "",
                "copied_log": ""
            })

            continue


        print(
            f"  LOG matches: "
            f"{match_count}"
        )

        print(
            f"  LOG selected: "
            f"{log_file}"
        )


        # ==================================================
        # COPY LOG
        # ==================================================

        copied_log = copy_file_unique(
            log_file,
            LOG_OUTPUT,
            serial
        )


        print(
            f"  LOG copied: "
            f"{copied_log}"
        )


        scanned_serials.append(
            serial
        )


        report.append({
            "serial": serial,
            "status": "OK",
            "source_zip": str(
                newest_zip
            ),
            "copied_zip": str(
                copied_zip
            ),
            "log_matches": match_count,
            "source_log": str(
                log_file
            ),
            "copied_log": str(
                copied_log
            )
        })


    # ======================================================
    # WRITE CSV REPORT
    # ======================================================

    with open(
        REPORT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        fieldnames = [
            "serial",
            "status",
            "source_zip",
            "copied_zip",
            "log_matches",
            "source_log",
            "copied_log"
        ]

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            report
        )


    # ======================================================
    # WRITE SCANNED LIST
    # ======================================================

    with open(
        SCANNED_SERIALS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for serial in scanned_serials:
            f.write(
                serial + "\n"
            )


    # ======================================================
    # WRITE MISSING LIST
    # ======================================================

    with open(
        MISSING_SERIALS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for serial in missing_serials:
            f.write(
                serial + "\n"
            )


    # ======================================================
    # SUMMARY
    # ======================================================

    print()
    print()
    print(
        "=" * 70
    )

    print(
        "COMPLETED"
    )

    print(
        "=" * 70
    )

    print(
        f"Input serials:    "
        f"{len(serials)}"
    )

    print(
        f"Logs collected:   "
        f"{len(scanned_serials)}"
    )

    print(
        f"Missing/errors:   "
        f"{len(missing_serials)}"
    )

    print()

    print(
        f"Report:\n"
        f"{REPORT_FILE}"
    )

    print()

    print(
        f"Scanned serials:\n"
        f"{SCANNED_SERIALS_FILE}"
    )

    print()

    print(
        f"Missing serials:\n"
        f"{MISSING_SERIALS_FILE}"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()