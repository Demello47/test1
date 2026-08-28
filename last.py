import os
import shutil
import zipfile
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

# Gde iskat ZIP arhivy
SOURCE_ROOT = Path(r"C:\LOGS")

# Fail so spiskom serial numbers
SERIALS_FILE = Path(r"C:\work\serials.txt")

# Kuda kopirovat poslednie ZIP
ZIP_OUTPUT = Path(r"C:\work\selected_zips")

# Kuda raspakovyvat ZIP
EXTRACT_OUTPUT = Path(r"C:\work\extracted")

# Kuda kopirovat finalnye najdennye faily
FINAL_OUTPUT = Path(r"C:\work\final_files")


# ==========================================================
# SOZDAEM PAPKI
# ==========================================================

ZIP_OUTPUT.mkdir(
    parents=True,
    exist_ok=True
)

EXTRACT_OUTPUT.mkdir(
    parents=True,
    exist_ok=True
)

FINAL_OUTPUT.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================================
# CHTENIE SERIAL NUMBERS
# ==========================================================

def load_serials():

    with open(
        SERIALS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        serials = [
            line.strip()
            for line in f
            if line.strip()
        ]

    return serials


# ==========================================================
# NAJTI VSE ZIP DLJA SERIAL
# ==========================================================

def find_zip_files(serial):

    found = []

    for root, dirs, files in os.walk(
        SOURCE_ROOT
    ):

        for filename in files:

            if not filename.lower().endswith(
                ".zip"
            ):
                continue

            # Serial dolzhen byt v imeni ZIP
            if serial not in filename:
                continue

            full_path = Path(root) / filename

            found.append(
                full_path
            )

    return found


# ==========================================================
# VYBRAT SAMYJ POSLEDNIJ ZIP
#
# Ispolzuem modification time.
# ==========================================================

def get_latest_zip(zip_files):

    if not zip_files:
        return None

    return max(
        zip_files,
        key=lambda path:
            path.stat().st_mtime
    )


# ==========================================================
# BEZOPASNAYA RASPAKOVKA ZIP
# ==========================================================

def extract_zip(zip_path, destination):

    destination.mkdir(
        parents=True,
        exist_ok=True
    )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as archive:

        for member in archive.infolist():

            member_path = (
                destination
                /
                member.filename
            ).resolve()

            # Zashchita ot path traversal v ZIP
            if not str(
                member_path
            ).startswith(
                str(destination.resolve())
            ):
                print(
                    f"Unsafe ZIP entry skipped: "
                    f"{member.filename}"
                )

                continue

            archive.extract(
                member,
                destination
            )


# ==========================================================
# NAJTI FAIL S SERIAL NUMBER
# VNUTRI RASPAKOVANNOJ PAPKI
# ==========================================================

def find_serial_files(
    extracted_folder,
    serial
):

    found = []

    for root, dirs, files in os.walk(
        extracted_folder
    ):

        for filename in files:

            if serial in filename:

                found.append(
                    Path(root)
                    /
                    filename
                )

    return found


# ==========================================================
# MAIN
# ==========================================================

def main():

    serials = load_serials()

    print(
        f"Serial numbers loaded: "
        f"{len(serials)}"
    )

    print()


    for number, serial in enumerate(
        serials,
        start=1
    ):

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


        # ==================================================
        # STEP 1
        # NAJTI ZIP
        # ==================================================

        zip_files = find_zip_files(
            serial
        )


        if not zip_files:

            print(
                "ZIP not found."
            )

            continue


        print(
            f"ZIP files found: "
            f"{len(zip_files)}"
        )


        # ==================================================
        # STEP 2
        # VYBRAT POSLEDNIJ
        # ==================================================

        latest_zip = get_latest_zip(
            zip_files
        )


        print(
            f"Latest ZIP:"
        )

        print(
            latest_zip
        )


        # ==================================================
        # STEP 3
        # COPY ZIP
        # ==================================================

        copied_zip = (
            ZIP_OUTPUT
            /
            latest_zip.name
        )


        shutil.copy2(
            latest_zip,
            copied_zip
        )


        print(
            f"ZIP copied to:"
        )

        print(
            copied_zip
        )


        # ==================================================
        # STEP 4
        # EXTRACT
        # ==================================================

        serial_extract_folder = (
            EXTRACT_OUTPUT
            /
            serial
        )


        # Esli ot proshlogo zapuska papka est,
        # ochishchaem ee.
        if serial_extract_folder.exists():

            shutil.rmtree(
                serial_extract_folder
            )


        extract_zip(
            copied_zip,
            serial_extract_folder
        )


        print(
            f"Extracted to:"
        )

        print(
            serial_extract_folder
        )


        # ==================================================
        # STEP 5
        # NAJTI FAIL PO SERIAL
        # ==================================================

        serial_files = find_serial_files(
            serial_extract_folder,
            serial
        )


        if not serial_files:

            print(
                "File with serial number "
                "inside ZIP not found."
            )

            continue


        print(
            f"Files with serial found: "
            f"{len(serial_files)}"
        )


        # ==================================================
        # STEP 6
        # COPY FINAL FILES
        # ==================================================

        for source_file in serial_files:

            destination = (
                FINAL_OUTPUT
                /
                source_file.name
            )


            shutil.copy2(
                source_file,
                destination
            )


            print(
                f"Final file copied:"
            )

            print(
                destination
            )


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


if __name__ == "__main__":
    main()