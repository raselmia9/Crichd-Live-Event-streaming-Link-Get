import asyncio
import json
from playwright.async_api import async_playwright
import requests

GITHUB_JSON_URL = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event/refs/heads/main/crichd_matches.json"

async def fetch_match_details(context, match):
    page = await context.new_page()
    
    # গতি বাড়ানোর জন্য ফালতু রিকোয়েস্ট ব্লক করা
    await page.route("**/*.{png,jpg,jpeg,gif,css,svg}", lambda route: route.abort())

    match_date_time = "N/A"
    page_links = []

    try:
        detail_url = match.get("detail_url")
        if detail_url:
            await page.goto(detail_url, timeout=20000)

            # ১. সঠিক ডেট এবং টাইম সংগ্রহ করা
            date_elem = await page.query_selector(".date-time, .schedule-date, time, span, h4")
            if date_elem:
                text = await date_elem.inner_text()
                if "UTC" in text or "202" in text:
                    match_date_time = text.strip()

            if match_date_time == "N/A":
                body_text = await page.inner_text("body")
                for line in body_text.split("\n"):
                    if "UTC" in line or "AM" in line or "PM" in line:
                        if "at" in line or "," in line:
                            match_date_time = line.strip()
                            break

            # ২. ডিটেইল পেজের ভেতরের টেবিল বা চ্যানেল সেকশন থেকে সুনির্দিষ্ট লিংকগুলো সংগ্রহ করা
            # এখানে শুধু /watch/ বা /live/ বা সংশ্লিষ্ট স্ট্রিম লিংকগুলো ফিল্টার করা হবে যাতে জেনেরিক লিংক না আসে
            links_elements = await page.query_selector_all("table a, .channels-list a, tr a, td a")
            
            for link in links_elements:
                href = await link.get_attribute("href")
                link_text = await link.inner_text()
                
                if href and ("/watch/" in href or "/live/" in href or "stream" in href or "link" in link_text.lower()):
                    full_link = href if href.startswith("http") else "https://m.crichd.pk" + href
                    
                    # ডুপ্লিকেট এড়াতে এবং নাম ঠিক রাখতে
                    link_name = f"Link{len(page_links) + 1}"
                    formatted_link = f"{link_name},,{full_link}"
                    
                    if formatted_link not in page_links and full_link != detail_url:
                        page_links.append(formatted_link)

    except Exception as e:
        print(f"Error for {match.get('detail_url')}: {e}")

    await page.close()

    # ফরম্যাট তৈরি করা
    multi_streaming_str = ")".join(page_links) + ")" if page_links else match.get("multi_streaming", "")

    return {
        "event_name": match.get("event_name", "Live Sports"),
        "team1_logo": match.get("team1_logo", ""),
        "team2_logo": match.get("team2_logo", ""),
        "team1_name": match.get("team1_name", "Team 1"),
        "team2_name": match.get("team2_name", "Team 2"),
        "date_and_time": match_date_time if match_date_time != "N/A" else match.get("date_and_time", "CrichD"),
        "multi_streaming": multi_streaming_str,
        "detail_url": match.get("detail_url", "")
    }

async def main():
    print("গিটহাব JSON থেকে ম্যাচ লিস্ট লোড করা হচ্ছে...")
    response = requests.get(GITHUB_JSON_URL)
    if response.status_code != 200:
        print("গিটহাব থেকে ডেটা লোড করা যায়নি!")
        return

    matches_data = response.json()
    print(f"মোট {len(matches_data)} টি ম্যাচ পাওয়া গেছে। আলাদা লিংকগুলো প্রসেস করা হচ্ছে...")

    final_output = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        tasks = [fetch_match_details(context, match) for match in matches_data]
        final_output = await asyncio.gather(*tasks)

        await browser.close()

    # ফাইনাল ডেটা crichd_matches.json ফাইলে সেভ করা
    with open("crichd_matches.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)

    print("সফলভাবে প্রতিটি ম্যাচের আলাদা লিংকসহ 'crichd_matches.json' আপডেট করা হয়েছে!")

if __name__ == "__main__":
    asyncio.run(main())
