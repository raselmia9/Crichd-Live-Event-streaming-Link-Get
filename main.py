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

            # ২. টেবিলের ভেতর থাকা "Watch" বাটন বা লিংকগুলো খুঁজে বের করা
            # স্ক্রিনশট অনুযায়ী টেবিলে Link 1, Link 2 এবং Watch লেখা থাকে
            rows = await page.query_selector_all("table tr, .channels-list tr, div.flex")
            
            link_count = 1
            for row in rows:
                row_text = await row.inner_text()
                if "Link" in row_text or "Watch" in row_text:
                    # রো এর ভেতরে থাকা a ট্যাগ খোঁজা
                    link_elem = await row.query_selector("a")
                    if link_elem:
                        href = await link_elem.get_attribute("href")
                        if href:
                            full_link = href if href.startswith("http") else "https://m.crichd.pk" + href
                            formatted_link = f"Link{link_count},,{full_link}"
                            if formatted_link not in page_links:
                                page_links.append(formatted_link)
                                link_count += 1
                    else:
                        # যদি সরাসরি a ট্যাগ না থাকে, পুরো রো তে ক্লিক করার ব্যবস্থা বা ডিফল্ট স্ট্রাকচার হ্যান্ডেল করা
                        pass

            # যদি ওপরের নিয়মে না পায়, সাধারণ সব a ট্যাগ চেক করা যাতে Watch বা Link আছে
            if not page_links:
                all_links = await page.query_selector_all("a")
                for l in all_links:
                    text = await l.inner_text()
                    href = await l.get_attribute("href")
                    if href and ("watch" in href.lower() or "stream" in href.lower() or "link" in text.lower()):
                        full_link = href if href.startswith("http") else "https://m.crichd.pk" + href
                        if full_link != detail_url and f"Link,,{full_link}" not in str(page_links):
                            page_links.append(f"Link{len(page_links) + 1},,{full_link}")

    except Exception as e:
        print(f"Error for {match.get('detail_url')}: {e}")

    await page.close()

    # ফরম্যাট তৈরি করা (যেমন: Link1,,URL),Link2,,URL))
    multi_streaming_str = ")".join(page_links) + ")" if page_links else match.get("multi_streaming", "")

    # আউটপুট থেকে detail_url বাদ দেওয়া হয়েছে
    return {
        "event_name": match.get("event_name", "Live Sports"),
        "team1_logo": match.get("team1_logo", ""),
        "team2_logo": match.get("team2_logo", ""),
        "team1_name": match.get("team1_name", "Team 1"),
        "team2_name": match.get("team2_name", "Team 2"),
        "date_and_time": match_date_time if match_date_time != "N/A" else match.get("date_and_time", "CrichD"),
        "multi_streaming": multi_streaming_str,
    }

async def main():
    print("গিটহাব JSON থেকে ম্যাচ লিস্ট লোড করা হচ্ছে...")
    response = requests.get(GITHUB_JSON_URL)
    if response.status_code != 200:
        print("গিটহাব থেকে ডেটা লোড করা যায়নি!")
        return

    matches_data = response.json()
    print(f"মোট {len(matches_data)} টি ম্যাচ পাওয়া গেছে। মাল্টি-পেজ লিংক সংগ্রহ করা হচ্ছে...")

    final_output = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # একসাথে সব পেজ প্রসেস করার জন্য টাস্ক
        tasks = [fetch_match_details(context, match) for match in matches_data]
        final_output = await asyncio.gather(*tasks)

        await browser.close()

    # ফাইনাল ডেটা crichd_matches.json ফাইলে সেভ করা (detail_url ছাড়া)
    with open("crichd_matches.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)

    print("সফলভাবে `detail_url` বাদ দিয়ে এবং সঠিক মাল্টি-পেজ লিংকসহ ফাইল আপডেট করা হয়েছে!")

if __name__ == "__main__":
    asyncio.run(main())
