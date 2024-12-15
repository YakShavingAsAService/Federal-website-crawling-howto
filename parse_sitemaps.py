from collections import deque
import csv
import requests
from bs4 import BeautifulSoup

start_url = "https://www.cdc.gov/wcms-auto-sitemap-index.xml"
csv_fname = "sitemap_data.csv"

class SitemapData:
  '''utility class for holding a sitemap name, the names of any sub-sitemaps
  found in it, and the URLs for non-sitemap entries in it.'''
  def __init__(self,sitemap):
    self.sitemap = sitemap
    self.subsitemaps = []
    self.urls = []
  def add_url(self,url):
    if url not in self.urls: self.urls.append(url)
  def add_subsitemap(self,loc):
    if loc not in self.subsitemaps: self.subsitemaps.append(loc)
  def to_csv(self,fname):
    with open(fname,'a') as csvfile:
      csvwriter = csv.writer(csvfile, delimiter=',')
      for url in self.urls:
        csvwriter.writerow((self.sitemap,url))
  def __str__(self):
    return "%s has %d urls, %d subsitemaps" % (self.sitemap,len(self.urls),len(self.subsitemaps))

def get_sitemap_locs( sitemap_name ):
  '''get a URL pointing to a sitemap and return a list of all the loc elements in it.'''
  response = requests.get(sitemap_name)
  soup = BeautifulSoup(response.content, "xml")
  loc_elements = soup.find_all("loc")
  urls = [loc.text for loc in loc_elements]
  return urls

# initialize the work queues
sitemaps_work_q = deque([start_url])
processed_sitemaps_q = deque([])

# while there's at least one item on the sitemaps work queue
while len(sitemaps_work_q) > 0: 

  # and this sitemap hasn't been already processed ...
  sitemap = sitemaps_work_q.popleft()
  if sitemap in processed_sitemaps_q:
    print("already processed %s, skipping" % sitemap)
    continue
  print("parsing %s" % start_url)

  # instantiate a class to hold the parsing results
  try:
    sitemapdata = SitemapData(sitemap)
  except Exception as err:
    raise err

  # go get all the locs out of the sitemap
  locs = get_sitemap_locs( sitemap )
  for loc in locs:
    # if a loc is actually just another sitemap ...
    if "sitemap" in loc and ".xml" in loc:
        # ... and it hasn't already been processed ...
        if loc not in sitemaps_work_q: sitemaps_work_q.appendleft( loc )
        # then add it as a subsitemap
        sitemapdata.add_subsitemap(loc)
    else:
      # otherwise, this loc is an actual non-sitemap endpoint
      # add it as just a plain url
      #print("this is a url! %s" % loc )
      sitemapdata.add_url(loc)

  # report sitemapdata statistics
  print(sitemapdata)
  # turn the parsed sitemaps into a csv file
  sitemapdata.to_csv(csv_fname)
  #print(sitemapdata)
  # add this sitemap to the 'already processed' queue
  processed_sitemaps_q.append(sitemap)

print("parsed sitemap URL are in %s" % csv_fname)
