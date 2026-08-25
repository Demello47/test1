import os
import sys
import re
import json


# ==========================================================
# START
#
# Primer:
# python3 build_baseline.py /logs/PASS_FOLDER
# ==========================================================

if len(sys.argv) < 2:
    print("Usage: python3 build_baseline.py PASS_FOLDER")
    sys.exit(1)


PASS_ROOT = os.path.abspath(sys.argv[1])

OUTPUT_FILE = os.path.join(
    os.path.dirname(PASS_ROOT),
    "baseline.json"
)


# ==========================================================
# BINARNYE I NENUZHNYE FORMATY
# ==========================================================

SKIP_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".sys",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".mp3",
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".zip",
    ".rar",
    ".7z",
    ".gz",
    ".tar",
    ".iso",
    ".bin",
    ".pdf",
}


# ==========================================================
# ROTACIONNYE LOGI
#
# Primer:
# test.log.1
# test.log.17
# test.log.250
# ==========================================================

SKIP_FILE_PATTERNS = [
    r'\.log\.\d+$',
]


# ==========================================================
# NORMALIZACIJA SHUMA
#
# ZDES MY UBIRAEM TOLKO TO,
# CHTO NE DOLZHNO VLijat NA SRAVNENIE.
#
# Diagnosticheskie chisla poka NE TROGAEM.
# ==========================================================

NORMALIZE_PATTERNS = [

    # Timestamp:
    # 2026-08-25 14:20:31
    (
        re.compile(
            r'\b\d{4}-\d{2}-\d{2}[ T]'
            r'\d{2}:\d{2}:\d{2}(?:\.\d+)?\b'
        ),
        '<TIMESTAMP>'
    ),

    # Primer:
    # 08/25/2026 14:20:31
    (
        re.compile(
            r'\b\d{2}/\d{2}/\d{4}\s+'
            r'\d{2}:\d{2}:\d{2}(?:\.\d+)?\b'
        ),
        '<TIMESTAMP>'
    ),

    # UUID
    (
        re.compile(
            r'\b[0-9a-fA-F]{8}-'
            r'[0-9a-fA-F]{4}-'
            r'[0-9a-fA-F]{4}-'
            r'[0-9a-fA-F]{4}-'
            r'[0-9a-fA-F]{12}\b'
        ),
        '<UUID>'
    ),

    # MAC address
    (
        re.compile(
            r'\b(?:[0-9A-Fa-f]{2}:){5}'
            r'[0-9A-Fa-f]{2}\b'
        ),
        '<MAC>'
    ),

    # PID=1234
    (
        re.compile(
            r'\bPID\s*[=:]\s*\d+\b',
            re.IGNORECASE
        ),
        'PID=<PID>'
    ),

]


# ==========================================================
# SERIAL NUMBER
#
# VAZHNO:
# Eta chast poka obobshchennaja.
# Esli u tebja serial imeet opredelennyj format,
# potom sdelayem ego bolee tochnym.
# ==========================================================

SERIAL_PATTERNS = [

    # Serial: 702615000143
    re.compile(
        r'(?i)\b(serial|serial_number|sn)'
        r'\s*[=:]\s*[A-Za-z0-9_-]+'
    ),

]


# ==========================================================
# NORMALIZACIJA STROKI
# ==========================================================

def normalize_line(line):

    # Udaljaem tolko perevod stroki
    # Probely vnutri stroki ostajutsja
    normalized = line.rstrip("\r\n")


    # ------------------------------------------
    # Serial numbers
    # ------------------------------------------

    for pattern in SERIAL_PATTERNS:

        normalized = pattern.sub(
            lambda m: (
                m.group(1)
                + "=<SERIAL>"
            ),
            normalized
        )


    # ------------------------------------------
    # Ostalnoj dinamicheskij shum
    # ------------------------------------------

    for pattern, replacement in NORMALIZE_PATTERNS:

        normalized = pattern.sub(
            replacement,
            normalized
        )


    return normalized


# ==========================================================
# POLUCHIT TEST DIRECTORY
#
# Berem pervuju papku posle PASS_ROOT.
#
# PASS_ROOT/TEST_A/logs/file.log
#            ^
#            TEST_A
# ==========================================================

def get_test_directory(directory):

    relative_path = os.path.relpath(
        directory,
        PASS_ROOT
    )

    if relative_path == ".":
        return "ROOT"

    return relative_path.split(
        os.sep
    )[0]


# ==========================================================
# PROVERKA IMENI FAILA
# ==========================================================

def should_skip_file(filename):

    extension = os.path.splitext(
        filename
    )[1].lower()

    if extension in SKIP_EXTENSIONS:
        return True


    for pattern in SKIP_FILE_PATTERNS:

        if re.search(
            pattern,
            filename,
            re.IGNORECASE
        ):
            return True


    return False


# ==========================================================
# CHTENIE FAILA
# ==========================================================

def process_file(file_path):

    events = []

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1
            ):

                original = line.rstrip("\r\n")

                normalized = normalize_line(
                    line
                )


                # Pustye stroki ne sohranjaem
                if normalized.strip() == "":
                    continue


                events.append({
                    "line": line_number,
                    "original": original,
                    "normalized": normalized
                })


    except (PermissionError, OSError) as error:

        print(
            f"Cannot read: {file_path}"
        )

        return []


    return events


# ==========================================================
# MAIN
# ==========================================================

def main():

    if not os.path.isdir(PASS_ROOT):

        print(
            f"PASS directory not found: {PASS_ROOT}"
        )

        sys.exit(1)


    baseline = {

        "pass_root": PASS_ROOT,

        "tests": {}

    }


    total_files = 0
    total_events = 0


    # ======================================================
    # REKURSIVNYJ OBHOD PASS
    # ======================================================

    for directory, subdirectories, files in os.walk(
        PASS_ROOT
    ):

        test_name = get_test_directory(
            directory
        )


        if test_name not in baseline["tests"]:

            baseline["tests"][test_name] = {
                "files": {}
            }


        for filename in files:

            if should_skip_file(filename):
                continue


            file_path = os.path.join(
                directory,
                filename
            )


            print(
                f"Scanning: {file_path}",
                flush=True
            )


            events = process_file(
                file_path
            )


            # Net chitaemyh strok
            if not events:
                continue


            # Put otnositelno samogo testa
            if test_name == "ROOT":

                relative_file = os.path.relpath(
                    file_path,
                    PASS_ROOT
                )

            else:

                test_root = os.path.join(
                    PASS_ROOT,
                    test_name
                )

                relative_file = os.path.relpath(
                    file_path,
                    test_root
                )


            baseline["tests"][test_name]["files"][
                relative_file
            ] = {

                "event_count": len(events),

                "events": events

            }


            total_files += 1
            total_events += len(events)


    # ======================================================
    # UDALJAEM PUSTYE TESTY
    # ======================================================

    empty_tests = [

        test_name

        for test_name, data
        in baseline["tests"].items()

        if not data["files"]

    ]


    for test_name in empty_tests:

        del baseline["tests"][test_name]


    # ======================================================
    # SOHRANENIE BASELINE
    # ======================================================

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as output:

        json.dump(
            baseline,
            output,
            indent=2,
            ensure_ascii=False
        )


    print()
    print("=" * 70)
    print("PASS BASELINE CREATED")
    print("=" * 70)

    print(
        f"PASS root:       {PASS_ROOT}"
    )

    print(
        f"Tests:           {len(baseline['tests'])}"
    )

    print(
        f"Files:           {total_files}"
    )

    print(
        f"Events/lines:    {total_events}"
    )

    print(
        f"Baseline file:   {OUTPUT_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()