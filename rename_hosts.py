#Скрипт обрабатывает все записи JUPITER, #сохраняет остальные настройки и создаёт #резервную копию.


import re
import shutil

filename = "dhcpd.conf"

shutil.copy(filename, filename + ".backup")

with open(filename, "r") as f:
    text = f.read()

def rename(match):
    number = match.group(1)
    device = match.group(2).upper()
    old_name = match.group(0).split()[1]

    if device == "WIN":
        letter = "w"
    else:
        letter = "r"

    new_name = f"Jupiter{number}{letter}"

    return f"# {old_name}\nhost {new_name} {{"

pattern = r"host\s+JUPITER-(\d+)_(WIN|RPI)_IP\s*\{"

text = re.sub(pattern, rename, text, flags=re.IGNORECASE)

with open(filename, "w") as f:
    f.write(text)

print("Done!")
