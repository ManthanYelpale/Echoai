
import requests

url = "http://localhost:8000/api/resume/upload"
files = {'file': open('test_resume.txt', 'rb')}
try:
    r = requests.post(url, files=files)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)
