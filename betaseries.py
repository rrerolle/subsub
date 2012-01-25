#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib2, urllib
import cookielib
import json
import difflib
import os
import zipfile

from flexget.utils.titles.series import SeriesParser

BETASERIES_URL = 'http://api.betaseries.com'
BETASERIES_KEY = 'ca7b28296588'
SERIES = [
    'The Good Wife',
    'Californication',
    'Desperate Housewives',
    'Damages',
    'Breaking Bad',
    'Dexter',
]
SCORE_THRESHOLD = 0.8
LANGUAGE_ORDER = ['VF', 'VO']
EXCLUDED_TAGS = ['.TAG.', '.ass', '.txt']
KEYWORDS = {
    'DIMENSION',
    'IMMERSE',
    'ORENJI',
    '720P',
    'WEB-DL',
    'X264',
    'H.264',
}

class UrlGrabber(object):
    def __init__(self, url, handle_cookies=False, debug=False):
        self.url = url
        self.handle_cookies = handle_cookies
        self.debug = debug
        self._stream = None
        self.open()

    @property
    def filename(self):
        return urllib2.unquote(os.path.basename(
            self._stream.geturl()))

    def read(self):
        return self._stream.read()

    def readlines(self):
        return self._stream.readlines()

    def open(self):
        request =  urllib2.Request(self.url)
        handlers = []
        if self.handle_cookies:
            handlers.append(urllib2.HTTPCookieProcessor(cookielib.LWPCookieJar()))
        if self.debug:
            handlers.append(urllib2.HTTPHandler(debuglevel=1))

        opener = urllib2.build_opener(*handlers)

        self._stream = opener.open(request)

    def close(self):
        self._stream.close()

    def download(self, filename):
        out_stream = open(filename, 'w')
        self.open()
        out_stream.write(self.read())
        self.close()
        out_stream.close()

class Subtitle(object):
    def __init__(self, movie_filename):
        self.movie_filename = movie_filename
        self.show = ''
        self.season = 0
        self.episode = 0
        self.filename = ''
        self.url = ''
        self.quality = 0
        self.score = 0.0
        self.language = ''
        self.keyword_count = 0

    def __repr__(self):
        return '[Subtitle file %s, quality:%d, score:%0.2f, keywords:%d, %s]' % (
            self.filename,
            self.quality,
            self.score,
            self.keyword_count,
            self.language,
        )

    def update_score(self):
        self.score = difflib.SequenceMatcher(
            None,
            self.movie_filename,
            self.filename,
        ).ratio()

    def clean_string(self, string):
        return string.lower().replace('.', ' ').replace('-', ' ')

    def update_keyword_count(self):
        clean_filename = self.clean_string(self.filename)
        clean_movie_filename = self.clean_string(self.movie_filename)
        for keyword in KEYWORDS:
            keyword_full = self.clean_string(' %s ' % keyword)
            keyword_short = self.clean_string(' %s ' % keyword[:3])
            stop = False
            for j in [keyword_full, keyword_short]:
                for k in [keyword_full, keyword_short]:
                    if j in clean_movie_filename and k in clean_filename:
                        self.keyword_count += 1
                        stop = True
                        break
                if stop:
                    break

    def has_forbidden_tags(self):
        for tag in EXCLUDED_TAGS:
            if tag in self.filename:
                return True
        return False

    def download(self):
        prefix = os.path.splitext(self.movie_filename)[0] 
        grabber = UrlGrabber(self.url)
        print "Downloading %s" % grabber.filename
        if '.zip' in grabber.filename:
            grabber = grabber.download(prefix + '.zip')
            zip_object = zipfile.ZipFile(prefix + '.zip')
            namelist = zip_object.namelist()
            if self.filename not in namelist:
                print 'ERROR, %S not in zip' % self.filename
                return
            sub_data = zip_object.read(self.filename)
            with open(prefix + ".srt", 'w') as srt_file:
                srt_file.write(sub_data)
            zip_object.close()
            os.remove(prefix + ".zip")
        else:
            grabber.download(prefix + '.srt')

class BetaSeries(object):
    def __init__(self, key=BETASERIES_KEY):
        self.key = key

    def query(self, path, params):
        params['key'] = self.key
        request = urllib2.Request(
            url=BETASERIES_URL + path,
            data=urllib.urlencode(params),
        )
        data = urllib2.urlopen(request).read()
        return json.loads(data)['root']

    def get_show_url(self, name):
        result = self.query(
            '/shows/search.json', {
                'title': name,
            }
        )
        return result.get('shows', {}).get('0', {}).get('url', '')

    def parse(self, movie_filename):
        for serie in SERIES:
            parser = SeriesParser(name=serie)
            parser.parse(data=movie_filename)
            if parser.valid:
                break
        return parser

    def get_subtitles(self, movie_filename):
        parser = self.parse(movie_filename)
        if not parser.valid:
            return []
        url = self.get_show_url(parser.name)
        if not url:
            return []
        results = self.query(
            '/subtitles/show/%s.json' % url, {
                'season': parser.season,
                'episode': parser.episode,
            }
        ).get('subtitles', {})

        subtitles = []
        for result in results.values():
            if 'content' in result:
                filenames = result['content'].values()
            else:
                filenames = [result.get('file')]
            for filename in filenames:
                subtitle = Subtitle(movie_filename)
                subtitle.filename = filename
                subtitle.show = result['title']
                subtitle.season = int(result['season'])
                subtitle.episode = int(result['episode'])
                subtitle.url = result['url']
                subtitle.language = result['language']
                subtitle.quality = result['quality']
                if (subtitle.has_forbidden_tags()
                    or subtitle.episode != parser.episode
                    or subtitle.filename == u''
                ):
                    continue
                subtitle.update_score()
                subtitle.update_keyword_count()
                subtitles.append(subtitle)

        return subtitles

    def find_best(self, filename):
        subtitles = self.get_subtitles(filename)
        for language in LANGUAGE_ORDER:
            best_subtitles =  [s for s in subtitles
                               if s.language == language]
            max_count = max(s.keyword_count for s in best_subtitles)
            best_subtitles = [s for s in subtitles
                              if s.language == language
                              and s.keyword_count == max_count]
            best_subtitles.sort(key=lambda x:x.quality)
            if not best_subtitles:
                best_subtitles = [s for s in subtitles
                                  if s.score > SCORE_THRESHOLD
                                  and s.language == language]
                best_subtitles.sort(key=lambda x: x.score)
                if not best_subtitles:
                    best_subtitles = [s for s in subtitles
                                      if s.language == language
                                      if s.keyword_count > 0]
                    best_subtitles.sort(key=lambda x:x.keyword_count)
                    if not best_subtitles:
                        best_subtitles = [s for s in subtitles
                                          if s.language == language]
                        best_subtitles.sort(key=lambda x:x.score)
            if best_subtitles:
                return best_subtitles[-1]

files = [
#    "The Good Wife S03E01 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E02 PROPER 720p WEB-DL DD5.1 H.264-NFHD.mkv",
    "The Good Wife S03E04 720p WEB-DL DD5.1 H.264-NFHD.mkv",
    "The Good Wife S03E05 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E06 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E07 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E08 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "Californication.S05E01.720p.HDTV.x264-IMMERSE.mkv",
#    "Desperate Housewives - 8x12 - What's the Good of Being Good.mkv",
#    "Dexter.S06E01.720p.HDTV.x264-IMMERSE.mkv",
#    "Breaking.Bad.S04E07.VOSTFR.720p.WEB-DL.DD5.1.H.264-GKS.mkv",
#    "Breaking.Bad.S04E08.Hermanos.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Breaking.Bad.S04E09.Bug.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Breaking.Bad.S04E10.VOSTFR.720p.WEB-DL.DD51.H264-SLT.mkv",
#    "Breaking.Bad.S04E12.End_Times.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Breaking.Bad.S04E13.Face_Off.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Californication.S05E02.720p.HDTV.X264-DIMENSION.mkv",
#    "Damages.S04E06.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Damages.S04E07.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Damages.S04E08.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Damages.S04E09.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Damages.S04E10.720p.WEB-DL.DD5.1.H.264-TB.mkv",
#    "Desperate.Housewives.S08E01.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E02.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E03.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E04.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E07.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E08.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E09.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E10.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E11.720p.HDTV.X264-DIMENSION.mkv",
#    "Desperate.Housewives.S08E12.720p.HDTV.X264-DIMENSION.mkv",
#    "Dexter.S06E01.REPACK.720p.HDTV.x264-IMMERSE.mkv",
#    "Dexter.S06E02.720p.HDTV.x264-ORENJI.mkv",
#    "Dexter.S06E03.720p.HDTV.x264-IMMERSE.mkv",
#    "Dexter.S06E04.720p.HDTV.X264-DIMENSION.mkv",
#    "Dexter.S06E06.PROPER.720p.HDTV.X264-DIMENSION.mkv",
#    "Dexter.S06E07.720p.HDTV.X264-DIMENSION.mkv",
#    "Dexter.S06E09.720p.HDTV.X264-DIMENSION.mkv",
#    "Dexter.S06E10.720p.HDTV.x264-IMMERSE.mkv",
#    "Dexter.S06E12.FINAL.FASTSUB.VOSTFR.HDTV.720P.X264-ATeam.mkv",
#    "The.Good.Wife.S03E02.720p.HDTV.X264.DIMENSION.mkv",
]


beta = BetaSeries()

for filename in files:
    print ' -- ', filename
    best = beta.find_best(filename)
    print best
    best.download()
    from time import sleep
    sleep(1)
