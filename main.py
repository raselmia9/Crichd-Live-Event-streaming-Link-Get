import asyncio
import json
from playwright.async_api import async_playwright
import requests

# গিটহাবের লাইভ JSON লিংক যেখান থেকে প্রথম পেজের ডেটা নেওয়া হবে
GITHUB_JSON_URL = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event/refs/heads/main/crichd_matches.json"


async def fetch_match_details(context, match):
  page = await context.new_page()

  # গতি বাড়ানোর জন্য ইমেজ, সিএসএস বা ফালতু রিকোয়েস্ট ব্লক করা
  await page.route(
      "**/*.{png,jpg,jpeg,gif,css,svg}", lambda route: route.abort()
  )

  match_date_time = "N/A"
  streams_list = []

  def handle_request(request):
    nonlocal streams_list
    if ".m3u8" in request.url:
      stream_url = request.url
      referer_url = request.headers.get("referer", "https://crichdsee.st/")

      link_name = f"Link{len(streams_list) + 1}"
      formatted_stream = f"{link_name},,{stream_url}|Referer={referer_url},"

      if formatted_stream not in streams_list:
        streams_list.append(formatted_stream)

  page.on("request", handle_request)

  try:
    # ডিটেইল পেজে প্রবেশ করা (যেমন: /event/...)
    detail_url = match.get("detail_url")
    if detail_url:
      await page.goto(detail_url, timeout=20000)

      # সঠিক তারিখ ও সময় সংগ্রহ করা (যেমন: Aug 18, 2026...)
      date_elem = await page.query_selector(".date-time, .schedule-date, time, span")
      if date_elem:
        match_date_time = await date_elem.inner_text()

      # Link 1, Link 2 বা Watch অপশনগুলোতে ক্লিক করা যাতে m3u8 ট্রিগার হয়
      channel_links = await page.query_selector_all(
          "table tr td a, .channels-list a, a"
      )
      for link in channel_links[:3]:
        try:
          await link.click()
          await asyncio.sleep(1)
        except:
          pass

      # লিংক ক্যাপচার হওয়ার জন্য একটু অপেক্ষা করা
      for _ in range(5):
        if streams_list:
          break
        await asyncio.sleep(1)

  except Exception as e:
    print(f"Error for {match.get('detail_url')}: {e}")

  await page.close()

  # আপনার কাঙ্ক্ষিত মাল্টি-স্ট্রিমিং ফরম্যাট তৈরি
  multi_streaming_str = ")".join(streams_list) + ")" if streams_list else ""

  return {
      "event_name": match.get("event_name", "Live Sports"),
      "team1_logo": match.get("team1_logo", ""),
      "team2_logo": match.get("team2_logo", ""),
      "team1_name": match.get("team1_name", "Team 1"),
      "team2_name": match.get("team2_name", "Team 2"),
      "date_and_time": match_date_time.strip(),
      "multi_streaming": multi_streaming_str,
  }


async def main():
  print("গিটহাব JSON থেকে ম্যাচ লিস্ট লোড করা হচ্ছে...")
  response = requests.get(GITHUB_JSON_URL)
  if response.status_code != 200:
    print("গিটহাব থেকে ডেটা লোড করা যায়নি!")
    return

  matches_data = response.json()
  print(
      f"মোট {len(matches_data)} টি ম্যাচ পাওয়া গেছে। মাল্টি-ট্যাবে প্রসেস করা"
      " হচ্ছে..."
  )

  final_output = []

  async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context()

    # একসাথে ৫টি করে ট্যাব ব্যাকগ্রাউন্ডে প্রসেস করা (গতি বাড়ানোর জন্য)
    batch_size = 5
    for i in range(0, len(matches_data), batch_size):
      batch = matches_data[i : i + batch_size]
      tasks = [fetch_match_details(context, match) for match in batch]
      results = await asyncio.gather(*tasks)
      final_output.extend(results)

    await browser.close()

  # ফাইনাল ডেটা crichd_matches.json ফাইলে সেভ করা
  with open("crichd_matches.json", "w", encoding="utf-8") as f:
    json.dump(final_output, f, indent=4, ensure_ascii=False)

  print("সফলভাবে সমস্ত স্ট্রিমিং লিংকসহ 'crichd_matches.json' আপডেট করা হয়েছে!")


if __name__ == "__main__":
  asyncio.run(main())
    
