
import asyncio
import httpx
from bs4 import BeautifulSoup
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

async def debug_naukri():
    print("\n--- Debugging Naukri ---")
    url = "https://www.naukri.com/python-developer-jobs-in-bangalore"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            r = await client.get(url)
            print(f"Status: {r.status_code}")
            print(f"Length: {len(r.text)}")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.select(".jobTuple, article.jobTuple, .cust-job-tuple")
                print(f"Cards found: {len(cards)}")
                if len(cards) == 0:
                     print("Trying new selectors...")
                     # Print first 500 chars of body to see if there's a captcha or blocking msg
                     print(soup.body.get_text()[:500] if soup.body else "No body")
    except Exception as e:
        print(f"Error: {e}")

async def debug_indeed():
    print("\n--- Debugging Indeed ---")
    url = "https://in.indeed.com/jobs?q=python+fresher&l=India"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            r = await client.get(url)
            print(f"Status: {r.status_code}")
            print(f"Length: {len(r.text)}")
            if r.status_code == 200:
                 if "Cloudflare" in r.text or "human" in r.text:
                     print("likely CLOUDFLARE BLOCKED")
                 soup = BeautifulSoup(r.text, "html.parser")
                 cards = soup.select(".job_seen_beacon, .tapItem")
                 print(f"Cards found: {len(cards)}")
                 if len(cards) == 0:
                     # Check newer indeed classes
                     print("Checking alternative selectors...")
                     cards2 = soup.select(".resultContent")
                     print(f"ResultContent found: {len(cards2)}")
    except Exception as e:
        print(f"Error: {e}")

async def debug_wellfound():
    print("\n--- Debugging Wellfound ---")
    url = "https://wellfound.com/role/r/software-engineer?job_listing_type=full_time&country=IN"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            r = await client.get(url)
            print(f"Status: {r.status_code}")
            print(f"Length: {len(r.text)}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await debug_naukri()
    await debug_indeed()
    await debug_wellfound()

if __name__ == "__main__":
    asyncio.run(main())
