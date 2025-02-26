# a minmalist python3 script to list all the record streams in directories of warc files

import argparse
import os
import warcio
from warcio.archiveiterator import ArchiveIterator


def read_warc(fname):

    with open(fname,'rb') as stream:
        for record in ArchiveIterator(stream):
            if record.rec_type == 'warcinfo':
                print(record.raw_stream.read())
            if record.rec_type == 'response':
                if record.content_type == 'text/dns': continue

                try:
                    print("%s,%s" % (record.http_headers.get_statuscode(),record.rec_headers.get_header('WARC-Target-URI')))
                except:
                    print("exception")

parser = argparse.ArgumentParser()
parser.add_argument("dirlist", type=str, nargs='+', help="One or more directories with warcs in them")
args = parser.parse_args()

for d in args.dirlist:
    for fname in os.listdir(d):
        fpath = os.path.join(d,fname)
        read_warc(fpath)
