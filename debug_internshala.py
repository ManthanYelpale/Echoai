
import asyncio
import httpx
from bs4 import BeautifulSoup

url = "https://internshala.com/jobs/computer-science-jobs"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def main():
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        r = await client.get(url)
        print(f"Status: {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")
        
        cards = soup.select(".internship_meta, .individual_internship")
        print(f"Found {len(cards)} cards")
        
        for i, card in enumerate(cards[:3]):
            print(f"\n--- Card {i+1} ---")
            title = card.select_one(".profile, .job-title, h3")
            print(f"Title: {title.get_text().strip() if title else 'Not Found'}")
            
            # Check for ANY link in the card
            links = card.select("a")
            for l in links:
                print(f"Link: {l.get('href')}")

if __name__ == "__main__":
    asyncio.run(main())
