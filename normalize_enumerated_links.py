import pandas as pd
import pathlib
from urllib.parse import urlparse, urljoin, ParseResult

in_fname = 'pandas_output.pkl'
out_fname = 'unique_normalized_gov_links.pkl'

df = pd.read_pickle(in_fname)
print("starting out with %d links from %s" % (len(df),in_fname))

# if the link doesn't have a netloc value, use the netloc from the source 
def normalize_links(row):
    # do this even if the link is an absolute URL, because running this
    # through urlparse will make fragments at the end of the path go away
    # in parsed.path, which we can use to build the new link, which
    # makes searchiung for duplicates a lot easier
    tmp_abs_link = urljoin(row['source'],row['link'])
    # parse the absolute URL to get new scheme, netloc, path, path suffix parts
    parsed = urlparse(tmp_abs_link)
    row['scheme'] = parsed.scheme
    row['netloc'] = parsed.netloc
    row['path'] = parsed.path
    path = pathlib.Path(parsed.path)
    row['suffix'] = path.suffix
    # build a new ParseResult with no fragment data. fragments makes finding duplicates hard.
    new_parsed = ParseResult(parsed.scheme,parsed.netloc,parsed.path,parsed.params,parsed.query,'')
    # reassemble the normalized link from the new ParsedResult class
    row['link'] = new_parsed.geturl()
    return row

# apply the netloc normalization function to all rows
print("going to normalize the links:")
print("... rel hrefs into abs hrefs, figure out the suffix, throw away fragments in path. (takes a while) ..." )
normalized_links_df = df.apply(normalize_links, axis=1)
print("finished normalizing the links ...")

# filter all rows that are pointing to a non-.gov site
normalized_gov_df = normalized_links_df[ normalized_links_df['netloc'].str.contains('.gov', case=False)]
print("removed links that point to non-.gov sites ...")

# if we have multiple rows with the same link, filter out all but the first one
unique_normalized_gov_df = normalized_gov_df.drop_duplicates(subset=['link'],keep='first')
print("and if we have multiple rows with the same link value, preserve just the first one")

# write this dataframe out
unique_normalized_gov_df.to_pickle(out_fname)
print("finished. we now have %d unique gov links in %s" % (len(unique_normalized_gov_df),out_fname))


