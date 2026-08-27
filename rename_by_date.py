import os
import re
import sys
import argparse
from datetime import datetime


# ==========================================================
# START
#
# Primer:
# python3 rename_by_date.py /path/to/tests/folder
# python3 rename_by_date.py /path/to/tests/folder --dry-run
# ==========================================================


# ==========================================================
# BINARNYE FORMATY KOTORYE PROPUSKAEM PRI POISKE DAT
# ==========================================================

SKIP_EXTENSIONS = {
    ".exe", ".dll", ".so", ".sys",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov",
    ".zip", ".rar", ".7z", ".gz", ".tar", ".iso", ".bin", ".pdf",
}


# ==========================================================
# PATTERNY DAT/VREMENI + FUNKCIA PARSINGA DLIA KAZHDOGO
#
# Poriadok vazhen: bolee spetsifichnye patterny idut pervymi
# ==========================================================

def parse_iso(s):
    s = s.replace("T", " ")
    s = s.split(".")[0]
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def parse_slash(s):
    s = s.split(".")[0]
    return datetime.strptime(s, "%d/%m/%Y %H:%M:%S")


def parse_date_only_iso(s):
    return datetime.strptime(s, "%Y-%m-%d")


def parse_date_only_dot(s):
    return datetime.strptime(s, "%d.%m.%Y")


DATE_PATTERNS = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?\b"), parse_iso),
    (re.compile(r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\b"), parse_slash),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), parse_date_only_iso),
    (re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b"), parse_date_only_dot),
]


# ==========================================================
# PROVERKA FAILA
# ==========================================================

def should_skip_file(filename):
    extension = os.path.splitext(filename)[1].lower()
    return extension in SKIP_EXTENSIONS


# ==========================================================
# NAJTI SAMUJU RANNIUJU DATU VNUTRI PAPKI (REKURSIVNO)
# ==========================================================

def find_earliest_date(folder_path):
    earliest = None

    for directory, _subdirs, files in os.walk(folder_path):
        for filename in files:
            if should_skip_file(filename):
                continue

            file_path = os.path.join(directory, filename)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        for pattern, parser in DATE_PATTERNS:
                            match = pattern.search(line)
                            if not match:
                                continue
                            try:
                                dt = parser(match.group(0))
                            except ValueError:
                                continue

                            if dt.year == 1970:
                                continue

                            if earliest is None or dt < earliest:
                                earliest = dt
                            # nashli datu v etoj stroke - dalshe stroki ne smotrim
                            break
            except (PermissionError, OSError):
                continue

    return earliest


# ==========================================================
# UBRAT STARYJ CHISLOVOJ PREFIKS (esli skript zapuskaetsia povtorno)
# ==========================================================

OLD_PREFIX_RE = re.compile(r"^\d+_")


def strip_old_prefix(name):
    return OLD_PREFIX_RE.sub("", name)


# ==========================================================
# MAIN
# ==========================================================

def main():
    parser = argparse.ArgumentParser(
        description="Переименовывает подпапки по порядку дат, найденных в лог-файлах"
    )
    parser.add_argument("folder", help="Корневая папка с папками тестов")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать план переименования, ничего не менять",
    )
    args = parser.parse_args()

    root = os.path.abspath(args.folder)

    if not os.path.isdir(root):
        print(f"Папка не найдена: {root}")
        sys.exit(1)

    subfolders = [
        name for name in sorted(os.listdir(root))
        if os.path.isdir(os.path.join(root, name))
    ]

    if not subfolders:
        print("Подпапок не найдено.")
        sys.exit(0)

    with_date = []
    without_date = []

    print("Сканирование папок и поиск дат в логах...\n")

    for name in subfolders:
        folder_path = os.path.join(root, name)
        print(f"  {name} ...", end=" ", flush=True)

        earliest = find_earliest_date(folder_path)

        if earliest is None:
            print("дата не найдена")
            without_date.append(name)
        else:
            print(earliest)
            with_date.append((earliest, name))

    # Sortiruem po date (rannaja -> pozdnaja)
    with_date.sort(key=lambda item: item[0])

    ordered_names = [name for _dt, name in with_date] + without_date

    print()
    print("=" * 70)
    print("ПЛАН ПЕРЕИМЕНОВАНИЯ")
    print("=" * 70)

    rename_plan = []

    for index, name in enumerate(ordered_names, start=1):
        clean_name = strip_old_prefix(name)
        new_name = f"{index}_{clean_name}"

        if new_name == name:
            continue

        rename_plan.append((name, new_name))
        print(f"  {name}  ->  {new_name}")

    if not rename_plan:
        print("  Переименовывать нечего (всё уже в правильном порядке).")
        return

    print("=" * 70)

    if args.dry_run:
        print("\nЭто был dry-run. Ничего не переименовано.")
        print("Запустите без --dry-run, чтобы применить изменения.")
        return

    print()

    # Perejmenovyvaem cherez vremennye imena, chtoby izbezhat konfliktov
    # (naprimer esli papka '2_test' uzhe suschestvuet, a my hotim
    # pereimenovat '1_test' v '2_test')

    temp_names = []

    for old_name, new_name in rename_plan:
        old_path = os.path.join(root, old_name)
        temp_path = os.path.join(root, f"__tmp_rename__{old_name}")
        os.rename(old_path, temp_path)
        temp_names.append((temp_path, new_name))

    for temp_path, new_name in temp_names:
        new_path = os.path.join(root, new_name)
        os.rename(temp_path, new_path)
        print(f"  Переименовано -> {new_name}")

    print("\nГотово.")


if __name__ == "__main__":
    main()
