
import asyncio
from curl_cffi.requests import AsyncSession

async def main():
    print("Testing curl_cffi...")
    try:
        async with AsyncSession(impersonate="chrome") as s:
            r = await s.get("https://www.naukri.com/python-developer-jobs-in-bangalore")
            print(f"Naukri Status: {r.status_code}")
            print(f"Content Length: {len(r.text)}")
            
            r2 = await s.get("https://in.indeed.com/jobs?q=python&l=India")
            print(f"Indeed Status: {r2.status_code}")
            
    except ImportError:
        print("curl_cffi not installed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
