import os
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

url = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "?key=" + api_key
)

request = urllib.request.Request(url)

try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print("HTTP Status:", response.status)
        print("Gemini API connection successful!")

except urllib.error.HTTPError as error:
    print("HTTP Status:", error.code)
    print("Gemini rejected the request.")

    error_body = error.read().decode("utf-8")
    print("Gemini response:")
    print(error_body)

except Exception as error:
    print("Unexpected error:")
    print(type(error).__name__)
    print(error)