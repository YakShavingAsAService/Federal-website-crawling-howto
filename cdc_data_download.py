from bs4 import BeautifulSoup
from datetime import datetime
import IPython
import logging
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
import re
import sys
import time
from urllib.parse import urlparse

# this Python script visits CDC data URLs at data.cdc.gov and downloads the datasets using
# selenium 4 with Firefox in headless mode.
# 
# A number of downloads failed because the data.cdc.gov server couldn't serve the large
# datasets. With thos, I had much better luck using a small retriever script to get the
# datasets off socrata.

# I had some errors about "failing to read marionette port" which turned out to be a snap install
# of firefox causing problems. i removed it with "sudo snap remove firefox" and did an apt install of 
# firefox and the problem went away. see @NoPurposeInLife's reply in https://stackoverflow.com/questions/72374955/failed-to-read-marionette-port-when-running-selenium-geckodriver-firefox-a
# however, ubuntu likes to then reinstall the snap version ... so be prepared to rinse and repeat

input_fname = 'cdc_data_urls.csv'
webdriver_log_path = "gecko.log"
app_log_path = "cdc_data_download.log" 
#firefox_binary = "/usr/bin/firefox"
#firefox_profile = "./FirefoxTestProfile.json"
#download_dir = "/media/hdd2/testdownload"
download_directory = "/home/ubuntu/Downloads"

# Set the MOZ_HEADLESS environment variable
os.environ["MOZ_HEADLESS"] = "1"

def init_webdriver():
   '''set up selenium for firefox in headless mode.'''

   #service = Service(log_output=webdriver_log_path, service_args=['--log','debug'],)
   service = Service(log_output=webdriver_log_path, service_args=['--log','info'],)

   # Set up options for headless mode.
   options = Options()
   #options.binary_location = firefox_binary
   options.add_argument("--headless")
   # gack, cannot get profile to work. so aggravating.
   #profile_arg = "--profile %s" % firefox_profile
   #options.add_argument(profile_arg)
   #options.profile = profile

   driver = webdriver.Firefox(service=service,options=options)
   logging.info("headless firefox webdriver is instantiated")
   return driver

def dump_attributes(driver,element):
    driver.execute_script('var items = {}; for (index = 0; index < arguments[0].attributes.length; ++index) { items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value }; return items;', element)

def find_downloaded_file(directory,ts):
    full_paths = [os.path.join(directory, f) for f in os.listdir(directory)]
    files = [f for f in full_paths if os.path.isfile(f)]
    # if firefox is still downloading, it creates XXX.part files. Just return if found.
    partial_files = [f for f in files if f.endswith(".part")]
    if len(partial_files) > 0:
        logging.info("file %s still downloading" % ','.join(partial_files))
        return None
    newly_created_files = [f for f in files if os.path.getctime(f) > ts]
    if not newly_created_files: return None
    for ncf in newly_created_files: logging.info("found this newly created file: %s" % ncf )
    return newly_created_files

def process_downloaded_file(url,start_time):
    for i in range(120):
        time.sleep(10)
        flist = find_downloaded_file(download_directory,start_time.timestamp())
        if not flist: continue
        # found completely downloaded recent file(s)
        for f in flist:
           up = Path(url)
           fp = Path(f)
           new_fname = "%s/%s_%f_%s" % (fp.parent,up.name,start_time.timestamp(),fp.name)
           os.rename(f,new_fname)
           logging.info("%s: downloaded file is now called %s" % (url,new_fname))
        return
    logging.error("%s: never found downloaded file?!?" % url)

def download_from_url(driver,url):
   '''for a url, find the export/download buttons and click them to get the dataset.'''

   try:
      # load the url
      driver.get(url)
      logging.info("%s: title is: %s" % (url,driver.title))
      if 'Page Not Found'.lower() in driver.title.lower():
         logging.info("%s: page NOT FOUND" % url)
         return

      # parse webpage with BeautifulSoup
      soup = BeautifulSoup(driver.page_source, 'html.parser')

   except TimeoutException:
      logging.error("%s: got TIMEOUT trying to load and parse" % (url))
      return

   # some pages are going to be removed and don't have data available.
   # reference: https://support.socrata.com/hc/en-us/articles/26738697457303-Grid-View-Removal
   # see if this page is one of them by looking for a class called grid-deprecation-banner
   try:
      deprecation_banner = driver.find_element(By.CLASS_NAME, "grid-deprecation-banner")
      if deprecation_banner:
         logging.info("%s: grid view is DEPRECATED and doesn't have data available" % url)
         return
   except NoSuchElementException:
      pass

   # some pages have restricted access to the data. see if this page is one of them. 

   # some pages require a login to access
   if "You must be logged in to access this page.".lower() in soup.text.lower():
      logging.info("%s: requires a login to access. SKIPPING." % url)
      return

   # or does it have "Restricted Access" in its title? 
   if "Restricted Access".lower() in driver.title.lower():
      logging.info("%s: missing a Public Access Level but has RESTRICTED ACCESS in its title. SKIPPING." % url)
      return

   # or does it have a Public Access Level row in the Common Core table that has 'restricted' in its?
   try:
      tr_xpath = "//td[text()='Public Access Level']/following-sibling::td[1]"
      public_access_level_element = driver.find_element(By.XPATH, tr_xpath)
      logging.info("%s: has a Public Access Level of %s" % (url,public_access_level_element.text))
      if 'restricted'.lower() in public_access_level_element.text.lower():
          logging.info("%s: has a Public Access Level of RESTRICTED ACCESS: %s. SKIPPING." % (url,public_access_level_element.text))
          return
   except NoSuchElementException: pass

   # or does it have a Access Level Comment row in the Common Core table that has 'restricted' in it?
   try:
      tr_xpath = "//td[text()='Access Level Comment']/following-sibling::td[1]"
      public_access_level_element = driver.find_element(By.XPATH, tr_xpath)
      logging.info("%s: has a Access Level Comment of %s" % (url,public_access_level_element.text))
      if 'restricted'.lower() in public_access_level_element.text.lower():
          logging.info("%s: has a Access Level Comment of RESTRICTED ACCESS: %s. SKIPPING." % (url,public_access_level_element.text))
          return
   except NoSuchElementException: pass

   # ok, in theory this page has publicly accessible data downloads ...

   # find the button with the inner HTML "Export" using XPath
   # and click it to bring up the export dialog popup
   try:
      button_xpath = "//button[text()='Export']"
      wait = WebDriverWait(driver, 10)
      button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
      button.click()
      wait = WebDriverWait(driver, 10)

      # on the popup, find the button with the inner HTML "Download" using XPath
      # and click it to initiate the download
      button_xpath = "//button[text()='Download']"
      wait = WebDriverWait(driver, 10)
      button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))

      #dump_attributes(driver,button)
      start_time = datetime.now()
      button.click()
      logging.info("%s: download initiated" % url)
      process_downloaded_file(url,start_time)
      return
   except NoSuchElementException: pass
   except TimeoutException: pass

   # or maybe this is the alternate socrata download format
   # find the download-link class and find the CSV option within it and
   # click to initiate the download
   try:
       download_links = driver.find_elements(By.CLASS_NAME, "download-link")
       if download_links:
           # look for the plain CSV option
           csv_dl_links = [dl for dl in download_links if dl.text == "CSV"]
           if csv_dl_links:
              csv_href = csv_dl_links[0].find_element(By.TAG_NAME,"a").get_attribute("href")
              logging.info("timed out looking for Download button, but found this: %s" % csv_href) 
              start_time = datetime.now()
              csv_dl_links[0].click()
              logging.info("%s: download initiated" % url)
              process_downloaded_file(url,start_time)
              return
   except NoSuchElementException: pass
   except TimeoutException: pass

   # sometimes there's a non-button element with a class of "download"
   # that wraps an href.
   try:
      download_xpath = "//*[contains(@class, 'download')]//*[self::a]"
      download_element = driver.find_element(By.XPATH,download_xpath)
      href = download_element.get_attribute("href")
      # log the href
      logging.info("%s: found download element is a href: %s" % (url,href))
      parsed_url = urlparse(href)
      last_part = parsed_url.path.split('/')[-1]
      # if the href is one of these application types, click it to download
      if last_part in [ "application%2Fzip", "application%2Fx-zip-compressed", "application%2Fvnd.ms-excel", "application%2Fpdf" ]:
         start_time = datetime.now()
         download_element.click()
         logging.info("%s: download initiated" % url)
         process_downloaded_file(url,start_time)
         return
      # if it's something else, log it and move on
      else: 
         logging.info("%s: SKIPPING DOWNLOAD: download element href %s looks like a ordinary link" % (url,href))
         return
   except NoSuchElementException: pass
   except TimeoutException: pass

   # if i'm here it's because I could not find downloads mechanism. log it and move on.
   logging.error("%s: NO DOWNLOAD element?" % (url))
   return


def url_from_line(line):
   '''take input of form "string1,string2" and return string2 with no trailing whitespace. If input is just "string1", return that with no trailing whitespace'''
   ret = line.rstrip()
   try:
      ret = line.split(',')[1].rstrip()
   except IndexError:
       pass
   return ret

def is_browse_page(line):
   '''return True if this url begins with https://data.cdc.gov/browse?'''
   return line.startswith('https://data.cdc.gov/browse?')

def is_stories_page(line):
   '''return True if this url begins with https://data.cdc.gov/stories/'''
   return line.startswith('https://data.cdc.gov/stories')

logging.basicConfig(level=logging.INFO, filename = app_log_path, filemode='a', format='%(asctime)s %(levelname)s: %(message)s')
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

counter = 0
with open(input_fname) as input_f:
    urls = [url_from_line(l) for l in input_f]

    driver = init_webdriver()

    for u in urls:
        logging.info("%d: looking at %s" % (counter,u))
        if is_browse_page(u): 
            logging.info("%d: skipping BROWSE page: %s" % (counter,u))
        elif is_stories_page(u): 
            logging.info("%d: skipping STORIES page: %s" % (counter,u))
        else:
            download_from_url(driver,u)
        counter = counter + 1






