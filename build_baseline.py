import os
import json
import hashlib
import sys


if len(sys.argv) < 2:
    print("Usage: python3 build_baseline.py PASS_FOLDER")
    sys.exit(1)


PASS_ROOT = os.path.abspath(sys.argv[1])

OUTPUT_FILE = os.path.join(
    os.path.dirname(PASS_ROOT),
    "baseline.json"
)


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


def file_hash(file_path):
    hasher = hashlib.sha256()

    try:
        with open(
            file_path,
            "rb"
        ) as file:

            while True:

                block = file.read(
                    1024 * 1024
                )

                if not block:
                    break

                hasher.update(block)

        return hasher.hexdigest()

    except OSError:
        return None


def count_lines(file_path):
    count = 0

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            for _ in file:
                count += 1

    except OSError:
        return None

    return count


def get_top_directory(directory):

    relative_path = os.path.relpath(
        directory,
        PASS_ROOT
    )

    if relative_path == ".":
        return "ROOT"

    return relative_path.split(
        os.sep
    )[0]


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


    for directory, subdirectories, files in os.walk(
        PASS_ROOT
    ):

        top_directory = get_top_directory(
            directory
        )

        if top_directory not in baseline["tests"]:
            baseline["tests"][top_directory] = {}


        for filename in files:

            extension = os.path.splitext(
                filename
            )[1].lower()

            if extension in SKIP_EXTENSIONS:
                continue


            file_path = os.path.join(
                directory,
                filename
            )


            relative_file = os.path.relpath(
                file_path,
                os.path.join(
                    PASS_ROOT,
                    top_directory
                )
            )


            try:
                size = os.path.getsize(
                    file_path
                )
            except OSError:
                size = None


            baseline["tests"][top_directory][
                relative_file
            ] = {
                "size": size,
                "lines": count_lines(
                    file_path
                ),
                "sha256": file_hash(
                    file_path
                )
            }


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as output:

        json.dump(
            baseline,
            output,
            indent=4
        )


    print()
    print("=" * 60)
    print("Baseline created.")
    print(f"PASS root: {PASS_ROOT}")
    print(f"Output:    {OUTPUT_FILE}")
    print(
        f"Tests:     {len(baseline['tests'])}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()