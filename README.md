# CDC-website-crawl

As the new US presidental term approaches, I've been looking into archiving the CDC website. I wrote a discovery tool
based on the CDC's sitemaps.xml to discover URLs, and submitted those to the people at the End of Term project: https://eotarchive.org/.
You can do bulk nominations by submitting a PR for a new seed file at their github repo, at https://github.com/end-of-term/eot2024, or by emailing them directly. 

End of Term is an awesome project, but nomination *is* not a guarantee that your submitted URLs will get crawled. I wanted to do my own crawl. This repo is a
set of notes based on my experiences with getting this tooling up and running, along with a few helper scripts I have written.

# The crawler tooling

As anyone who has ever used the Internet's Archive Wayback Machine knows, web archiving has been around
for a long time. There are various tools available, but I settled on using the Internet Archive's tool,
Heritrix (https://github.com/internetarchive/heritrix3).

## Heritrix features

TODO: filetypes

## Heritrix quickstart

### Installation

Heritrix is well documented. You can find installation instructions are at https://heritrix.readthedocs.io/en/latest/getting-started.html.

I installed my crawler on an Ubuntu 24.04 server. I installed Heritrix 3.5 from https://github.com/internetarchive/heritrix3/releases.
Heritrix needs a Java JRE, and Heritrix 3.5 requires version 17 of the JRE. I installed that with my package manager: `sudo apt install openjdk-17-jre`.

Next I set my `JAVA_HOME` and `HERITRIX_HOME` environment variables. I upped the memory allocated to java to 1GB: `export JAVA_OPTS=-Xmx1024M.`

I set execute persmission on `chmod u+x $HERITRIX_HOME/bin/heritrix`

Then I launched Heritrix: `$HERITRIX_HOME/bin/heritrix -a admin:admin`

I am running the crawls on a headless server, so I need to tunnel the Heritrix control pane to my desktop's browser. )If you are running
on a full desktop, you can skip this step.) I tunneled the control pane via ssh: `ssh -p MY_SERVER_SSH_PORT -L localhost:9999:localhost:8443 MY_SERVER_USERNAME@MY_SERVER -N`
Now I can load the Heritrix control pane on my desktop's browser via https://localhost:9999.

OK, now we've loaded up https://localhost:9999 in our browser. But wait -- all I see is garbage on the web page! You'll need to configure a SSL certificate error
exception first. This turned out to be not-straightforward in the most recent of Firefox, so I just used Konquerer instead. Once the exception is configured,
the control pane works.

### First crawl
  
To run crawls, you need two things: some seeds, and a valid configuration file, called crawler-beans.cxml. A default one comes with the installation, but you'll
still need to make a couple of changes before the first crawl.

Create a new job, then go to the configuration tab to see crawler-beans.cxml. The first thing to change is metadata.operatorContactUrl in the simpleOverrides section and change its
value to a url associated with you. Next, find the property key seeds.textSource.value in the longerOverrides section and add in a few test URLs under the seeds.textSource.value property.
Save changes, then go back to the job page and press "build." If there are no errors to fix, press launch. To actually initiate the crawl, press unpause. Now you can monitor the
crawl with the reports on the right side. When you're done, hit terminate and then teardown.

### Configuring crawler-beans.cxml for a real crawl

For my "real" crawl, I made a couple of changes to my crawler-beans.cxml file.

First, I wanted to get my seeds from an external file, not from crawler-beans.cxml.

 - I commented out seeds.textSource.value in the longerOverrides section
 - I commented out the entire org.archive.modules.seeds.TextSeedModule with the ConfigString in the seeds section
 - I un-commented the alternative seeds section just below, the version of the modules.seeds.TextSeedModule that uses the ConfigFile. I set the value of the path property to my seeds file.
   
My second set of changes had to do with the crawl scope. Heritrix's documentation is here: https://heritrix.readthedocs.io/en/latest/configuring-jobs.html#crawl-scope. The scope section is a
list of all the conditions that ACCEPT or REJECT a URL for crawling. You go through the scope chain, and the last disposition wins.

What I wanted was to crawl all my seed files, plus links on the seed URLs that are at most one hop away, *if* those one-hop-away links are at cdc.gov, fda.gov, or nih.gov.

It's straightforward to configure maxHops in the TooManyHopsDecideRule for a maximum of one hop, but it's a little more work to restrict the one-hop links to specific
domains. Heritrix uses a hostname prefix called a surt. Sort of like an IP prefix, it lets you specify top level domains, domains, and hosts, which you can use for scope matches.
The surts that I want to ACCEPT are in SurtPrefixedDecideRule in acceptSurts, and here's what that section of my crawler-beans.cxml ooks like:

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
 
### Examining warc files

If you go to $HERITRIX_HOME/jobs, you see a directory with your job name and its associated crawl data. In there there's a directory called warc, and that's where your archived files are collected. 
How do I do I look inside them?

First, there's a useful collection of python tools to work with warc files at https://github.com/internetarchive/warctools. I use ```warcdump <warcfile>``` all the time to look at each archived file's metadata.

Second, you'll want to extract file from warcs, and you can do that with the warc_extractor tool from https://github.com/recrm/ArchiveTools/tree/master. Here's an example:

```python3 ../warc-extractor.py -dump content -output_path OUTPUT_DIRECTORY```

This will read whatever warc files are in the same directory and extract them into a tree under the output directory.

### Sizing warnc files

How do I create my seed files? My tools.

