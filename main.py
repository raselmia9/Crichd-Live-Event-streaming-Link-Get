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

            # পুরো পেজের টেক্সট একবারে নিয়ে লাইন বাই লাইন আলাদা করা
            body_text = await page.inner_text("body")
            lines = [line.strip() for line in body_text.split("\n") if line.strip()]

            # ১. যেভাবে ডেট ও টাইম নেওয়া হয়, ঠিক একইভাবে ইভেন্টের নাম এবং ডেট-টাইম বের করা
            for i in range(len(lines)):
                line = lines[i]
                
                # ডেট এবং টাইম খোঁজার লজিক
                if "UTC" in line or ("AM" in line or "PM" in line and ("at" in line or "," in line)):
                    if match_date_time == "N/A":
                        match_date_time = line
                    
                    # যেহেতু ডেট-টাইমের ঠিক উপরেই লিগের নাম থাকে, তাই এক বা দুই ধাপ আগের লাইন চেক করা
                    if i > 0 and event_title == "Live Sports":
                        possible_event = lines[i - 1]
                        # শর্ত: নামটা খুব বড় হবে না এবং এতে কোনো সময় বা 'vs' থাকবে না
                        if len(possible_event) < 30 and "UTC" not in possible_event and "vs" not in possible_event.lower() and "Starts" not in possible_event:
                            event_title = possible_event

            # যদি ওপরের লজিকে না পায়, ব্যাকআপ হিসেবে কমন লিগগুলোর নাম টেক্সটে খোঁজা
            if event_title == "Live Sports":
                known_leagues = ["LaLiga", "EPL", "Champions League", "MotoGP", "Bundesliga", "French Ligue 1", "Serie A", "Premier League", "Liga Portugal", "EFL", "ICC", "BPL", "IPL"]
                for l in known_leagues:
                    if l in body_text:
                        event_title = l
                        break

            # ২. টেবিল বা Watch বাটন থেকে লিংক সংগ্রহ করা
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
        "date_and_time": match_date_time,
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

    print("সফলভাবে সঠিক ইভেন্ট নাম, টাইম এবং লিংকসহ ফাইল আপডেট করা হয়েছে!")

if __name__ == "__main__":
    asyncio.run(main())
