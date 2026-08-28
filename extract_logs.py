import shutil
import zipfile
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

SERIALS_FILE = Path(
    "downloaded_serials.txt"
)

ZIP_DIR = Path(
    r"C:\Logs\DOWNLOADED_ZIPS"
)

EXTRACT_ROOT = Path(
    r"C:\Logs\EXTRACTED"
)

FINAL_LOG_DIR = Path(
    r"C:\Logs\FINAL_LOGS"
)

EXTRACTED_SERIALS_FILE = Path(
    "extracted_serials.txt"
)

MISSING_LOGS_FILE = Path(
    "missing_logs.txt"
)

REPORT_FILE = Path(
    "extract_report.txt"
)


# ==========================================================
# LOAD SERIALS
# ==========================================================

def load_serials():

    with SERIALS_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        return [
            line.strip()
            for line in f
            if line.strip()
        ]


# ==========================================================
# FIND ZIP
#
# Pervyj skript sohranjaet:
#
# SERIAL__original_name.zip
# ==========================================================

def find_zip(serial):

    matches = list(
        ZIP_DIR.glob(
            f"{serial}__*.zip"
        )
    )

    if not matches:
        return None

    # Normalno dolzhen byt odin.
    # Na vsjakij sluchaj berem samyj novyj.
    return max(
        matches,
        key=lambda p:
        p.stat().st_mtime
    )


# ==========================================================
# SAFE EXTRACT
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
                    "Unsafe ZIP member: "
                    f"{member.filename}"
                )


        archive.extractall(
            destination
        )


# ==========================================================
# FIND LOG
#
# Primer:
#
# 123456789_692608000023_xxx.log
#
# serial:
# 692608000023
#
# Chisla pered serial ignorirujutsja.
# ==========================================================

def find_matching_logs(
    root,
    serial
):

    result = []

    serial_lower = (
        serial.lower()
    )


    for path in root.rglob(
        "*.log"
    ):

        if serial_lower in (
            path.name.lower()
        ):

            result.append(
                path
            )


    return result


# ==========================================================
# MAIN
# ==========================================================

def main():

    EXTRACT_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    FINAL_LOG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    serials = load_serials()

    extracted = []
    missing = []
    report = []


    for number, serial in enumerate(
        serials,
        start=1
    ):

        print()
        print(
            f"[{number}/{len(serials)}] "
            f"{serial}"
        )


        zip_path = find_zip(
            serial
        )


        if zip_path is None:

            print(
                "ZIP NOT FOUND"
            )

            missing.append(
                f"{serial}\tZIP_NOT_FOUND"
            )

            continue


        extract_dir = (
            EXTRACT_ROOT
            / serial
        )


        if extract_dir.exists():

            shutil.rmtree(
                extract_dir
            )


        try:

            safe_extract(
                zip_path,
                extract_dir
            )

        except Exception as error:

            print(
                f"Extract failed: "
                f"{error}"
            )

            missing.append(
                f"{serial}\tEXTRACT_FAILED"
            )

            continue


        matches = find_matching_logs(
            extract_dir,
            serial
        )


        if not matches:

            print(
                "LOG NOT FOUND"
            )

            missing.append(
                f"{serial}\tLOG_NOT_FOUND"
            )

            report.append(
                f"{serial}\tLOG_NOT_FOUND\t"
                f"{zip_path}"
            )

            continue


        # Esli logov neskolko,
        # berem samyj novyj.
        selected = max(
            matches,
            key=lambda p:
            p.stat().st_mtime
        )


        destination = (
            FINAL_LOG_DIR
            / selected.name
        )


        if destination.exists():

            destination = (
                FINAL_LOG_DIR
                / f"{serial}__"
                  f"{selected.name}"
            )


        shutil.copy2(
            selected,
            destination
        )


        extracted.append(
            serial
        )


        report.append(
            f"{serial}\tOK\t"
            f"{zip_path}\t"
            f"{selected}\t"
            f"{destination}"
        )


        print(
            f"Copied: "
            f"{destination}"
        )


    # ======================================================
    # OUTPUT LISTS
    # ======================================================

    with EXTRACTED_SERIALS_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        for serial in extracted:
            f.write(
                serial + "\n"
            )


    with MISSING_LOGS_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        for item in missing:
            f.write(
                item + "\n"
            )


    with REPORT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "SERIAL\tSTATUS\tZIP\t"
            "SOURCE_LOG\tFINAL_LOG\n"
        )

        for item in report:
            f.write(
                item + "\n"
            )


    print()
    print("=" * 70)
    print("EXTRACTION COMPLETED")
    print("=" * 70)

    print(
        f"Input ZIP serials: "
        f"{len(serials)}"
    )

    print(
        f"Logs extracted: "
        f"{len(extracted)}"
    )

    print(
        f"Missing/errors: "
        f"{len(missing)}"
    )


if __name__ == "__main__":
    main()