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
    event_title = "Live Sports"
    page_links = []

    try:
        detail_url = match.get("detail_url")
        if detail_url:
            await page.goto(detail_url, timeout=20000)

            # ১. আপনার নতুন আইডিয়া অনুযায়ী: ডিটেইল পেজের ডেট/টাইম সেকশনের ওপর থেকে লিগের নাম (যেমন: LaLiga, EPL) তোলা
            try:
                # ক্যালেন্ডার আইকন বা ডেটের আশপাশের এলিমেন্ট বা হেডার টার্গেট করা
                # ক্রিকএইচডিতে এই টেক্সট সাধারণত ডেটের ঠিক উপরে বা লোগোর পাশের হেডিংয়ে থাকে
                league_elem = await page.query_selector(".event-title, h3, h4, .league-name, div[style*='font'], .panel-heading, div > span")
                if league_elem:
                    # পেজের ওপরের অংশ থেকে টেক্সট স্ক্যান করা
                    full_body_lines = (await page.inner_text("body")).split("\n")
                    for line in full_body_lines:
                        l_clean = line.strip()
                        # লিগের নামগুলো সাধারণত ছোট হয় এবং এগুলোতে UTC বা ব্লা-ব্লা থাকে না
                        if l_clean and l_clean in ["LaLiga", "EPL", "Champions League", "MotoGP", "Bundesliga", "French Ligue 1", "Serie A", "Premier League", "Liga Portugal", "EFL"]:
                            event_title = l_clean
                            break
                
                # যদি নির্দিষ্ট লিস্টে না মিলে, তবে ক্যালেন্ডার আইকনের আগের বা ওপরের টেক্সট খোঁজা
                if event_title == "Live Sports":
                    # পেজের একদম ওপরের হেডিং বা টেক্সট ব্লক চেক করা
                    possible_titles = await page.evaluate('''() => {
                        let elements = document.querySelectorAll('div, span, h3, h4');
                        for (let el of elements) {
                            let text = el.innerText.trim();
                            if (text && text.length > 2 && text.length < 25 && !text.includes('UTC') && !text.includes('Starts') && !text.includes('vs')) {
                                // যদি এর নিচে ক্যালেন্ডার বা ডেট থাকে
                                if (el.nextElementSibling && el.nextElementSibling.innerText.includes('UTC')) {
                                    return text;
                                }
                            }
                        }
                        return null;
                    }''')
                    if possible_titles:
                        event_title = possible_titles

            except Exception as ex:
                print(f"Event name extract error: {ex}")

            # যদি এখনো না পাওয়া যায়, JSON থেকে আসা নাম বা আগের ব্যাকআপ রাখা
            if event_title == "Live Sports" and match.get("event_name"):
                event_title = match.get("event_name")

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

            # যদি কোনো লিংক বা Watch বাটন না থাকে, আপনার নির্দিষ্ট মেসেজ বসবে
            if not page_links:
                page_links.append("Stream links will be activated before 1 hr of starting time.")

    except Exception as e:
        print(f"Error for {match.get('detail_url')}: {e}")

    await page.close()

    # মাল্টি স্ট্রিমিং ফরম্যাট তৈরি
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

    print("সফলভাবে সঠিক লিগ নাম, টাইম এবং লিংকসহ ফাইল আপডেট করা হয়েছে!")

if __name__ == "__main__":
    asyncio.run(main())
