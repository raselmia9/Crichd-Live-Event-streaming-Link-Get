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
    # প্রথমে গিটহাব JSON থেকে আসা ইভেন্ট নাম বা ডিফল্ট মান ধরা
    event_title = match.get("event_name", "Live Sports")
    page_links = []

    try:
        detail_url = match.get("detail_url")
        if detail_url:
            await page.goto(detail_url, timeout=20000)

            # ১. ডিটেইল পেজ থেকে সঠিক ইভেন্টের নাম সংগ্রহ করার নিখুঁত সিলেক্টর
            # ক্রিকএইচডি পেজে ইভেন্ট বা লিগের নাম সাধারণত ওপরের দিকে বা লোগোর পাশে থাকে
            event_elem = await page.query_selector(".event-title, h3, h4, .league-name, div[style*='font'], .panel-heading")
            if event_elem:
                e_text = await event_elem.inner_text()
                if e_text and len(e_text.strip()) > 2:
                    cleaned_text = e_text.strip().split("\n")[0]
                    if "UTC" not in cleaned_text and "Starts" not in cleaned_text:
                        event_title = cleaned_text

            # যদি ওপরেরটায় না পায়, পেজের প্রথম হেডিং বা টেক্সট চেক করা
            if event_title == "Live Sports" or not event_title:
                h_tags = await page.query_selector_all("h1, h2, h3")
                for h in h_tags:
                    htext = await h.inner_text()
                    if htext and len(htext.strip()) > 2 and "Live" not in htext and "UTC" not in htext:
                        event_title = htext.strip().split("\n")[0]
                        break

            # ২. সঠিক ডেট এবং টাইম সংগ্রহ করা
            date_elem = await page.query_selector(".date-time, .schedule-date, time, span")
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

            # ৩. টেবিল বা Watch বাটন থেকে লিংক সংগ্রহ করা
            rows = await page.query_selector_all("table tr, .channels-list tr, div.flex")
            
            link_count = 1
            for row in rows:
                row_text = await row.inner_text()
                if "Link" in row_text or "Watch" in row_text:
                    link_elem = await row.query_selector("a")
                    if link_elem:
                        href = await link_elem.get_attribute("href")
                        if href:
                            full_link = href if href.startswith("http") else "https://m.crichd.pk" + href
                            formatted_link = f"Link{link_count},,{full_link}"
                            if formatted_link not in page_links:
                                page_links.append(formatted_link)
                                link_count += 1

            # যদি কোনো লিংক না থাকে, নির্দিষ্ট মেসেজ বসবে
            if not page_links:
                page_links.append("Stream links will be activated before 1 hr of starting time.")

    except Exception as e:
        print(f"Error for {match.get('detail_url')}: {e}")

    await page.close()

    # ফরম্যাট তৈরি করা
    if len(page_links) == 1 and "Stream links" in page_links[0]:
        multi_streaming_str = page_links[0]
    else:
        multi_streaming_str = ")".join(page_links) + ")" if page_links else "Stream links will be activated before 1 hr of starting time."

    # ফাইনাল আউটপুট (detail_url বাদ দিয়ে)
    return {
        "event_name": event_title,
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
    print(f"মোট {len(matches_data)} টি ম্যাচ পাওয়া গেছে। ডেটা প্রসেস করা হচ্ছে...")

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

    print("সফলভাবে সঠিক ইভেন্ট নামসহ ফাইল আপডেট করা হয়েছে!")

if __name__ == "__main__":
    asyncio.run(main())
