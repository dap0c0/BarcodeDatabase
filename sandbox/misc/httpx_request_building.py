import httpx

# Create a request
request = httpx.Request("GET", "https://docs.twisted.org/en/stable/web/examples/index.html", content="testing..")

# Read its stream
body_content = b"".join(request.stream)
print(str(body_content, "ascii"))
