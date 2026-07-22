import urllib.parse
origin = "http://localhost:7860"
host_header = "localhost:7860"
parsed_origin = urllib.parse.urlparse(origin).hostname
host_hostname = host_header.split(":")[0]
print(parsed_origin, host_hostname)
