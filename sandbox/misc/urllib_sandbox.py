import urllib.parse
# url = "https://foobar.com/search?foo=a&bar=b"
url = "https://foobar.com/search"
parsed = urllib.parse.urlparse(url)
print(parsed)
print(parsed.query)
print(parsed.query.__class__)
print(len(parsed.query))
