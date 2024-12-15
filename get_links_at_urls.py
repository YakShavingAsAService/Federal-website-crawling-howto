from bs4 import BeautifulSoup
import csv
from datetime import datetime, timezone
import logging
import pandas as pd
import pathlib
import random
import requests
import time
from urllib.parse import urlparse 

csv_in_fname = "sitemap_data.csv" # the input data, which is a csv of loc URLs found by the sitemap tool
pickle_fname = "link_enumeration_output.pkl" # the output data, a list of links found in the URLs in the input data
# each row contains: the source URL, the time the link was accessed, the found link, the protocol used in the URL/URI,
# link's hostname component, the link's path component, and the URL's suffic (.html, .pdf, etc)
logging_fname = "get_links_at_urls.log" # logfile name
request_timeout=30.0 # timeout for http GETs in secs

def get_links( url ):
  '''return a list of all links found at url. if we can't load the url or if it is not a html file log an error and return an empty list.'''
  found_links = []
  response = requests.get(url, timeout=request_timeout)
  if response.status_code == 200:
    if 'text/html' in response.headers['Content-Type']:
      soup = BeautifulSoup(response.content, "html.parser")
      link_elements = soup.find_all("a")
      for l in link_elements:
        href = l.get("href")
        if href: found_links.append(href)
    else:
      logging.info("%s not a html file - skipping" % url)
  else:
    logging.error("could not access %s, response status code is %d" % (url,response.status_code))
  return found_links


counter = 0
logging.basicConfig(level=logging.INFO, filename = logging_fname, filemode='w', format='%(asctime)s %(levelname)s: %(message)s')
df = pd.DataFrame(columns=['source', 'time', 'link', 'scheme', 'netloc', 'path', 'suffix'])

if True:
  with open(csv_in_fname, 'r') as fin:
    reader = csv.reader(fin)

    # for every url in the input file ...
    for [src_sitemap,loc_href] in reader:
      print("input loc href %d: %s" % (counter,loc_href))
      logging.info("input loc href %d: %s" % (counter,loc_href))
      now_utc = datetime.now(timezone.utc)
      utc_time_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')

      try:
        # ... get a list of the links in that url ...
        links = get_links(loc_href)
        # ... write those links to the output file
        for l in links:
          if l in df['link'].values:
            logging.info("link %s in source %s was found  previously- skipping" % (l,loc_href))
            continue
          parsed = urlparse(l)
          if parsed.netloc == "" and parsed.path == '' and bool(parsed.fragment):
            continue # don't process fragment locations within the source HTML file
          path = pathlib.Path(parsed.path)
          suffix = path.suffix
          df.loc[len(df)] = { 'source': loc_href, 'time':utc_time_str, 'link': l, 'scheme': parsed.scheme, 'netloc': parsed.netloc, 'path': parsed.path, 'suffix': suffix }
          logging.info("found link %s" % l)
      except Exception as err:
          logging.error("exception: %s while processing %s" % (err,loc_href))
          print("exception: %s while processing %s" % (err,loc_href))

      sleep_time = random.uniform(0.05, 0.12)  # 50 to 120 milliseconds
      time.sleep(sleep_time)
      counter = counter + 1

df.to_pickle(pickle_fname)
