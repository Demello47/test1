import ijson

FILE = "drain_templates.json"

keywords = [
    "attempt",
    "ssh",
    "cpld",
    "firmware",
    "error",
    "fail"
]

found = 0

with open(FILE, "rb") as f:
    for item in ijson.items(f, "templates.item"):

        template = item["template"]
        count = item["count"]

        if any(
            word in template.lower()
            for word in keywords
        ):
            print(f"{count:>10}  {template}")

            found += 1

            if found >= 100:
                break

print()
print("Shown:", found)