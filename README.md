# Archiving U.S. Federal government websites

Are you eagerly awaiting the 2025 presidental transition? Me neither! Much as climate scientists worked to preserve federal datasets before the 2017 transition, I want to preserve vaccine and other information on the CDC website. That's led me to research ways to preserve federal website content. 

Here's what I came up with:

- the Internet Archive's Wayback Machine at: http://web.archive.org/. This is a fabulous resource that you probably already know about and have used. But, if you're an individual user, you're archiving a single URL at a time. So, I plan to archive a few high-profile pages, but it's not a practical solution if you want to archive a lot of material.
- The End of Term project at https://eotarchive.org/ is something I just learned about recently. It's a collaboration between the Internet Archive and some libraries and NGOs to archive the fedweb before and after presidental term changes. You can submit nominations for inclusion in their crawls at their website, or submit bulk nominations at their github repo, at https://github.com/end-of-term/eot2024, or by emailing them directly. I'm told that if you are targetting a crawl before the 2025 transition, you'll need to submit before January 5, 2025. I have submitted a couple of very large files for the CDC's website to this project.
- Roll Your Own crawls. A nomination to the End of Term project doesn't guarantee that your URLs will get crawled. And, they're not set up to archive some specific kinds of content. I started looking into how I could do my own crawls. A big drawback to this approach: when the End of Term project does a crawl, the provenenace of the materials it generates is crystal clear. While the End of Term project very much wants your seed nominations, they can't accept your crawled files, because of the obvious provenance issues involved. The same may be true for other intended downstream consumers of your crawled files. It might make more sense to try to work through established, credible organizations. Are there any other ongoing efforts in your subject area you can join?

What follows are notes about the tooling around running your own crawls, plus a few helper scripts that came in handy for both the End of Term nomination process and for my own crawls. I hope these are useful for people looking into preserving other parts of the fedweb.

# Crawler tooling and hardware

Web archiving has been around for a long time. There's a mature supporting file format, warc, and a surrounding ecosystem for tools: https://wiki.archiveteam.org/index.php/The_WARC_Ecosystem. I settled on using the Internet Archive's well-established tool, Heritrix (https://github.com/internetarchive/heritrix3).

For my server setup, I'm running Ubuntu 24.04 server on a Xeon-D chip with 16GB of RAM and 16TB (!!!) of HDD. My dedicated cloud instance comes with unmetered bandwidth.

## Heritrix features

TODO: describe supported/unsupported content types.

## Heritrix quickstart

### Installation

Heritrix is well documented. You can find installation instructions at https://heritrix.readthedocs.io/en/latest/getting-started.html.

I began by installing Heritrix 3.5 from https://github.com/internetarchive/heritrix3/releases.
Heritrix needs a Java JRE, and Heritrix 3.5 requires version 17 of the JRE. I installed that with my package manager: `sudo apt install openjdk-17-jre`.

Next I set my `JAVA_HOME` and `HERITRIX_HOME` environment variables. I upped the memory allocated to java to 1GB: `export JAVA_OPTS=-Xmx1024M.`

I set execute persmission on `chmod u+x $HERITRIX_HOME/bin/heritrix`

Then I launched Heritrix: `$HERITRIX_HOME/bin/heritrix -a admin:admin`

I am running the crawls on a headless server, so I need to tunnel the Heritrix control pane to my desktop's browser. If you are running
on a full desktop, you can skip this step. I tunneled the control pane via ssh: `ssh -p MY_SERVER_SSH_PORT -L localhost:9999:localhost:8443 MY_SERVER_USERNAME@MY_SERVER -N`
Now I can load the Heritrix control pane on my desktop's browser via https://localhost:9999.

OK, now we've loaded up https://localhost:9999 in our browser. But wait, all I see is garbage on the web page! You'll need to configure a SSL certificate error
exception first. In Firefox, go to about:preferences#privacy and scroll down to the Certificates section. Click "View Certificates" and pick the Servers tab, then click Add Exception at
the bottom. Put "https://localhost:9999" in the location field, then click "Get Certificate." Once the exception is configured, a normal control pane loads.

### First crawl
  
To run crawls, you need two things: some seed URLs, and a valid configuration file, called crawler-beans.cxml. A default one comes with the installation, but you'll
still need to make a couple of changes before the first crawl.

Create a new job, then go to the configuration tab to see crawler-beans.cxml. The first thing to change is metadata.operatorContactUrl in the simpleOverrides section; change its
value to a url associated with your project. Next, find the property key seeds.textSource.value in the longerOverrides section and add in a few test URLs under the seeds.textSource.value property.
Save changes, then go back to the job page and press "build." If there are no errors to fix, press launch. To actually initiate the crawl, press unpause. Now you can monitor the
crawl with the reports on the right side. When you're done, hit terminate and then teardown.

### Configuring crawler-beans.cxml for a real crawl

For my "real" crawl, I made a couple of changes to my crawler-beans.cxml file.

First, I wanted to get my seeds from an external file, not from crawler-beans.cxml.

 - I commented out seeds.textSource.value in the longerOverrides section
 - I commented out the entire org.archive.modules.seeds.TextSeedModule with the ConfigString in the seeds section
 - I un-commented the alternative seeds section just below, the version of the modules.seeds.TextSeedModule that uses the ConfigFile. I set the value of the path property to my seeds file.
   
My second set of changes had to do with the crawl scope. Heritrix's documentation on crawl scope is here: https://heritrix.readthedocs.io/en/latest/configuring-jobs.html#crawl-scope. The scope section is a
list of all the conditions that ACCEPT or REJECT a URL for crawling. You go through the scope chain, and the last disposition wins.

What I wanted was to crawl all my seed files, plus links on the seed URLs that are at most one hop away, *if* those one-hop-away links are at cdc.gov, fda.gov, or nih.gov.

It's straightforward to configure maxHops in the TooManyHopsDecideRule for a maximum of one hop, but it's a little more work to restrict the one-hop links to specific
domains. Heritrix uses a hostname prefix called a surt. Sort of like an IP prefix, it lets you specify top level domains, domains, and hosts, which you can use for scope matches.
The surts that I want to ACCEPT are in SurtPrefixedDecideRule in acceptSurts, and here's what that section of my crawler-beans.cxml looks like:

```xml
<bean id="acceptSurts" class="org.archive.modules.deciderules.surt.SurtPrefixedDecideRule">
      <property name="seedsAsSurtPrefixes" value="true" />
      <property name="surtsSource">
        <bean class="org.archive.spring.ConfigString">
         <property name="value">
          <value>
           +http://(gov,cdc,
           +http://(gov,fda,
           +http://(gov,nih,
          </value>
         </property> 
        </bean>
       </property>
 </bean>
```

That gave me a scope that looks like this:

 ```xml
 <!-- SCOPE: rules for which discovered URIs to crawl; order is very 
      important because last decision returned other than 'NONE' wins. -->
 <bean id="scope" class="org.archive.modules.deciderules.DecideRuleSequence">
  <!-- <property name="logToFile" value="false" /> -->
  <property name="rules">
   <list>
    <!-- Begin by REJECTing all... -->
    <bean class="org.archive.modules.deciderules.RejectDecideRule" />
    <!-- ...then ACCEPT those within configured/seed-implied SURT prefixes. Note: this uses the acceptSurts section I configured above ... -->
    <ref bean="acceptSurts" />
    <!-- ...but REJECT those more than a configured link-hop-count from start... -->
    <bean class="org.archive.modules.deciderules.TooManyHopsDecideRule">
           <property name="maxHops" value="1" />
    </bean>
    <!-- ...but REJECT those from a configurable (initially empty) set of REJECT SURTs Note: I don't use negative surts... -->
    <bean class="org.archive.modules.deciderules.surt.SurtPrefixedDecideRule">
          <property name="decision" value="REJECT"/>
          <property name="seedsAsSurtPrefixes" value="false"/>
          <property name="surtsDumpFile" value="${launchId}/negative-surts.dump" /> 
    </bean>
    <!-- ...and REJECT those from a configurable (initially empty) set of URI regexes... -->
    <bean class="org.archive.modules.deciderules.MatchesListRegexDecideRule">
          <property name="decision" value="REJECT"/>
    </bean>
    <!-- ...and REJECT those with suspicious repeating path-segments... -->
    <bean class="org.archive.modules.deciderules.PathologicalPathDecideRule">
     <!-- <property name="maxRepetitions" value="2" /> -->
    </bean>
    <!-- ...and REJECT those with more than threshold number of path-segments... -->
    <bean class="org.archive.modules.deciderules.TooManyPathSegmentsDecideRule">
     <!-- <property name="maxPathDepth" value="20" /> -->
    </bean>
    <!-- ...but always ACCEPT those marked as prerequisite for another URI... -->
    <bean class="org.archive.modules.deciderules.PrerequisiteAcceptDecideRule">
    </bean>
    <!-- ...but always REJECT those with unsupported URI schemes -->
    <bean class="org.archive.modules.deciderules.SchemeNotInSetDecideRule">
    </bean>
   </list>
  </property>
 </bean>
```
That's it for my configuration changes.

### Running a crawl

I ran my job nights and weekends, where the impact on the CDC's webservers would be minimal. You can use pause/unpause to control this. Also, Heritrix has a handy checkpointing feature. This allows you to preserve mid-crawl state, terminate the crawl, then re-launch with the saved state. You can read about it here: https://github.com/internetarchive/heritrix3/wiki/Checkpointing.

I got hung up trying to add seeds mid-crawl according to this doc: https://github.com/internetarchive/heritrix3/wiki/Adding-URIs-mid-crawl. But I somehow missed that very important first line, the one that notes that this is only relevant for a version of Heritrix that I'm not running. I got some advice about how to do this in Heritrix 3.5 in the issue tracker at https://github.com/internetarchive/heritrix3/issues/635, but haven't tried it yet.

### My real world statistics (so far)

In my current configuration, I crawl about 10,000 URLs in 12 hours. This generates a compressed warc file of around 350 MB. Keep in mind this number is dependent on the type of content you're crawling. I'm collecting many HTML files, which compress nicely. Other content might run slower and take up more disk. I suggest running a test mini-crawl of your seeds and extrapolating your resource needs from there.

### Examining warc files

If you go to $HERITRIX_HOME/jobs, you see a directory with your job name and its associated crawl data. In there there's a directory called warc, and that's where your archived files are collected. 
How do I do I look inside them?

First, there's a useful collection of python tools to work with warc files at https://github.com/internetarchive/warctools. I use ```warcdump <warcfile>``` all the time to look at each archived file's metadata.

Second, you'll want to extract file from warcs, and you can do that with the warc_extractor tool from https://github.com/recrm/ArchiveTools/tree/master. Here's an example:

```python3 warc-extractor.py -dump content -output_path OUTPUT_DIRECTORY```

This will read whatever warc files are in the same directory and extract them into a tree under the output directory.

If you want to examine warc files in a browser, there's https://replayweb.page/.

### Next steps

Heritrix won't pick up the data files at data.cdc.gov. I'll need to write a web scraping tool to do that. It's currently TBD.

I'll need to index my warc files. It too is currently TBD.

It sure would be nice to have a Wayback Machine style interface to the warc files. But I haven't even begun to think about how to do that.

# My helper tools

I wrote several Python tools to help with seed files. They are all MIT-licensed. Modify and use as you see fit.

## Building the seed list

I needed to get a list of CDC URLs to use for my seed files, so I wrote a script, parse_sitemaps.py, to get location entries out of the CDC sitemaps.xml file. https://www.cdc.gov/sitemaps.xml just pointed at an empty page, but I found a sitemap link at the bottom of https://www.cdc.gov/robots.txt that pointed to https://www.cdc.gov/wcms-auto-sitemap-index.xml. That in turn pointed to a long list of inner sitemaps. My script parses through all these to come up with a list of seed files.

My sitemap-parsing script is here: https://github.com/YakShavingAsAService/CDC-website-crawl/blob/main/parse_sitemaps.py

## Understanding the links in the seed files

Those seed files are HTML files that have links to other content: other HTML files, links in the cdc.gov domain and out of it, PDF content, Microsoft Office format files, image files, and so on. I wanted to understand what these were, so I wrote another script to use the data generated by the first script and find the links in those files and break down each one by source, the time the link was found, the link, the protocol specified, the host component of the link, the path component of the link, and the suffix of the link. I stored the results in a pickle file, which is a disk persistence mechanism in Python. These are first-hop links only.

My link enumeration script is here: https://github.com/YakShavingAsAService/CDC-website-crawl/blob/main/get_links_at_urls.py. 

I wrote another script that filters the previous tool's output to create a pickle file of only the unique endpoints in the .gov domain. It also normalizes and relative HREFs into absolute HREFs. That normalizing script is at https://github.com/YakShavingAsAService/CDC-website-crawl/blob/main/normalize_enumerated_links.py.

## Archiving datasets

Heritrix doesn't handle dataset downloads, so I wrote my own script to archive the datasets hosted at data.cdc.gov. After I processed the sitemap to get the individual dataset URLs from the sitemap, I wrote a Selenium 4 script to retrieve the underlying .csv files. That's [cdc_data_download.py.](https://github.com/YakShavingAsAService/Federal-website-crawling-howto/blob/main/cdc_data_download.py)

That worked for most, but not all, the datasets, especially the larger ones. In those cases, I found it better to go directly to the Socrata API endpoints and retrieve the datasets there. Fortunately, there's a great Python package called [retriever](https://github.com/weecology/retriever/tree/main) that made this very easy. I probably should have just used retriever from the beginning.

```python
import retriever as rt
from pprint import pprint

ids = ['vbim-akqf' ] # example id

for id in ids:
    dataset = 'socrata-%s' % id
    resource = rt.find_socrata_dataset_by_id(id)
    pprint(resource)
    rt.download(dataset)
```

# Issues and questions

I'm just learning about web archiving, and I'm sure there are things I've gotten wrong in this writeup. If so feel free to file an issue against this repo. If you have other comments or questions that don't belong in the issue tracker, check my github profile to see how to contact me.



