import shutil
import zipfile
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

# Папка со скачанными ZIP из первого скрипта
ZIP_DIR = Path(
    r"C:\Logs\DOWNLOADED_ZIPS"
)


# Временная папка для распаковки
EXTRACT_ROOT = Path(
    r"C:\Logs\EXTRACTED"
)


# Сюда будут собраны нужные CSV
FINAL_CSV_DIR = Path(
    r"C:\Logs\FINAL_CSV"
)


# Отчёты
EXTRACTED_SERIALS_FILE = Path(
    "extracted_serials.txt"
)

MISSING_CSV_FILE = Path(
    "missing_csv.txt"
)

REPORT_FILE = Path(
    "extract_csv_report.txt"
)


# ==========================================================
# GET SERIAL FROM ZIP NAME
#
# Первый скрипт сохраняет:
#
# SERIAL__original_name.zip
#
# Например:
#
# 692608000023__result_692608000023.zip
#
# ->
#
# 692608000023
# ==========================================================

def get_serial_from_zip(zip_path):

    name = zip_path.name

    if "__" not in name:
        return None

    serial = name.split(
        "__",
        1
    )[0].strip()

    if not serial:
        return None

    return serial


# ==========================================================
# SAFE ZIP EXTRACTION
#
# Защита от путей вида:
#
# ../../file
# ==========================================================

def safe_extract(
    zip_path,
    destination
):

    destination.mkdir(
        parents=True,
        exist_ok=True
    )

    base = destination.resolve()


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
                    base
                )

            except ValueError:

                raise RuntimeError(
                    f"Unsafe ZIP path: "
                    f"{member.filename}"
                )


        archive.extractall(
            destination
        )


# ==========================================================
# FIND CSV WITH SERIAL
#
# Serial может быть не в начале имени.
#
# Например:
#
# 123456_692608000023_result.csv
#
# serial:
#
# 692608000023
#
# ->
# MATCH
# ==========================================================

def find_matching_csv(
    root,
    serial
):

    matches = []

    serial_lower = serial.lower()


    for path in root.rglob("*"):

        if not path.is_file():
            continue


        if path.suffix.lower() != ".csv":
            continue


        if (
            serial_lower
            in path.name.lower()
        ):

            matches.append(
                path
            )


    return matches


# ==========================================================
# SELECT NEWEST CSV
#
# Если внутри архива несколько CSV
# с этим serial — выбираем самый новый.
# ==========================================================

def select_newest_csv(
    files
):

    if not files:
        return None


    return max(
        files,
        key=lambda path:
        path.stat().st_mtime
    )


# ==========================================================
# UNIQUE DESTINATION
#
# Чтобы один файл случайно
# не перезаписал другой.
# ==========================================================

def get_destination(
    serial,
    source_csv
):

    destination = (
        FINAL_CSV_DIR
        / source_csv.name
    )


    if not destination.exists():
        return destination


    return (
        FINAL_CSV_DIR
        / f"{serial}__{source_csv.name}"
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    # ======================================================
    # CHECK SOURCE
    # ======================================================

    if not ZIP_DIR.is_dir():

        print(
            f"ZIP directory not found: "
            f"{ZIP_DIR}"
        )

        return


    # ======================================================
    # CREATE DIRECTORIES
    # ======================================================

    EXTRACT_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )


    FINAL_CSV_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # ======================================================
    # FIND ZIPS
    # ======================================================

    zip_files = sorted(
        ZIP_DIR.glob("*.zip")
    )


    print(
        f"ZIP files found: "
        f"{len(zip_files)}"
    )


    if not zip_files:

        print(
            "No ZIP files found."
        )

        return


    extracted_serials = []
    missing = []
    report = []


    # ======================================================
    # PROCESS ZIP FILES
    # ======================================================

    for number, zip_path in enumerate(
        zip_files,
        start=1
    ):

        print()
        print(
            "=" * 70
        )

        print(
            f"[{number}/{len(zip_files)}]"
        )

        print(
            f"ZIP: {zip_path.name}"
        )


        # ==================================================
        # SERIAL
        # ==================================================

        serial = get_serial_from_zip(
            zip_path
        )


        if serial is None:

            print(
                "Cannot determine serial "
                "from ZIP filename."
            )

            missing.append(
                f"{zip_path.name}\t"
                f"SERIAL_NOT_FOUND"
            )

            report.append(
                f"\tSERIAL_NOT_FOUND\t"
                f"{zip_path}\t\t"
            )

            continue


        print(
            f"Serial: {serial}"
        )


        # ==================================================
        # EXTRACTION DIRECTORY
        # ==================================================

        extract_dir = (
            EXTRACT_ROOT
            / serial
        )


        # Удаляем старую распаковку
        # этого serial перед новым запуском.
        if extract_dir.exists():

            shutil.rmtree(
                extract_dir
            )


        extract_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        # ==================================================
        # EXTRACT
        # ==================================================

        try:

            safe_extract(
                zip_path,
                extract_dir
            )


        except zipfile.BadZipFile:

            print(
                "BAD ZIP FILE"
            )

            missing.append(
                f"{serial}\tBAD_ZIP"
            )

            report.append(
                f"{serial}\tBAD_ZIP\t"
                f"{zip_path}\t\t"
            )

            continue


        except Exception as error:

            print(
                f"EXTRACT FAILED: "
                f"{error}"
            )

            missing.append(
                f"{serial}\t"
                f"EXTRACT_FAILED"
            )

            report.append(
                f"{serial}\t"
                f"EXTRACT_FAILED\t"
                f"{zip_path}\t\t"
            )

            continue


        print(
            f"Extracted to:"
        )

        print(
            f"  {extract_dir}"
        )


        # ==================================================
        # FIND CSV
        # ==================================================

        matches = find_matching_csv(
            extract_dir,
            serial
        )


        print(
            f"Matching CSV files: "
            f"{len(matches)}"
        )


        if not matches:

            print(
                "CSV NOT FOUND"
            )

            missing.append(
                f"{serial}\t"
                f"CSV_NOT_FOUND"
            )

            report.append(
                f"{serial}\t"
                f"CSV_NOT_FOUND\t"
                f"{zip_path}\t\t"
            )

            continue


        # ==================================================
        # SELECT NEWEST CSV
        # ==================================================

        selected_csv = (
            select_newest_csv(
                matches
            )
        )


        print(
            "Selected CSV:"
        )

        print(
            f"  {selected_csv}"
        )


        # ==================================================
        # COPY FINAL CSV
        # ==================================================

        destination = (
            get_destination(
                serial,
                selected_csv
            )
        )


        shutil.copy2(
            selected_csv,
            destination
        )


        print(
            "Copied to:"
        )

        print(
            f"  {destination}"
        )


        # ==================================================
        # SUCCESS
        # ==================================================

        extracted_serials.append(
            serial
        )


        report.append(
            f"{serial}\t"
            f"OK\t"
            f"{zip_path}\t"
            f"{selected_csv}\t"
            f"{destination}"
        )


    # ======================================================
    # WRITE EXTRACTED SERIALS
    # ======================================================

    with EXTRACTED_SERIALS_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        for serial in extracted_serials:

            file.write(
                serial
                + "\n"
            )


    # ======================================================
    # WRITE MISSING
    # ======================================================

    with MISSING_CSV_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        for item in missing:

            file.write(
                item
                + "\n"
            )


    # ======================================================
    # REPORT
    # ======================================================

    with REPORT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "SERIAL\t"
            "STATUS\t"
            "ZIP\t"
            "SOURCE_CSV\t"
            "FINAL_CSV\n"
        )


        for item in report:

            file.write(
                item
                + "\n"
            )


    # ======================================================
    # FINAL
    # ======================================================

    print()
    print(
        "=" * 70
    )

    print(
        "CSV EXTRACTION COMPLETED"
    )

    print(
        "=" * 70
    )

    print(
        f"ZIP files:       "
        f"{len(zip_files)}"
    )

    print(
        f"CSV extracted:   "
        f"{len(extracted_serials)}"
    )

    print(
        f"Missing/errors:  "
        f"{len(missing)}"
    )

    print()

    print(
        "Extracted serial list:"
    )

    print(
        f"  {EXTRACTED_SERIALS_FILE}"
    )

    print(
        "Missing CSV list:"
    )

    print(
        f"  {MISSING_CSV_FILE}"
    )

    print(
        "Report:"
    )

    print(
        f"  {REPORT_FILE}"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()