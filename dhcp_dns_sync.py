
import os

dhcp_file = "/etc/dhcp/dhcpd.conf"
dns_file = "/etc/bind/db.internal"
temp_file = "/etc/bind/db.internal.tmp"

hosts = []
name = ""
ip = ""

with open(dhcp_file, "r") as file:
    for line in file:
        line = line.strip()

        if line.startswith("#"):
            continue

        if line.startswith("host "):
            name = line.split()[1]
            name = name.lower()

        if line.startswith("fixed-address "):
            ip = line.split()[1].replace(";", "")

            if name != "":
                hosts.append(name + " IN A " + ip)

            name = ""

with open(dns_file, "r") as file:
    dns = file.read()

start = "; BEGIN DHCP"
end = "; END DHCP"

if start in dns and end in dns:
    before = dns.split(start)[0]
    after = dns.split(end)[1]
else:
    before = dns
    after = ""

new_records = "\n".join(sorted(hosts))

new_dns = before + start + "\n"
new_dns += new_records + "\n"
new_dns += end + after

if new_dns == dns:
    print("No changes")
else:
    with open(temp_file, "w") as file:
        file.write(new_dns)

    result = os.system(
        "named-checkzone internal " + temp_file
    )

    if result == 0:
        os.replace(temp_file, dns_file)
        os.system("rndc reload internal")
        print("DNS updated:", len(hosts), "hosts")
    else:
        os.remove(temp_file)
        print("DNS configuration error")
