#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib2, urllib
import cookielib
import json
import difflib
import sys
import os
import zipfile
try:
    from flexget.utils.titles.series import SeriesParser
except ImportError:
    print 'Please install flexget (sudo pip install flexget)'
    sys.exit(1)

BETASERIES_URL = 'http://api.betaseries.com'
BETASERIES_KEY = 'ca7b28296588'

# Series to handle
SERIES = [
    'The Good Wife',
    'Californication',
    'Desperate Housewives',
    'Damages',
    'Breaking Bad',
    'Dexter',
]
# String similarity threshold to consider a match
SCORE_THRESHOLD = 0.8
# Specify the preferred language here
LANGUAGE_ORDER = ['VF', 'VO']
# Discard any subtitle with one of those tags
EXCLUDED_TAGS = ['.TAG.', '.ass', '.txt']
# Scene release groups
GROUP_KEYWORDS = [
    'aAF', '0TV', '2HD', 'ASAP', 'CRiMSON', 'CTU', 'Caph', 'DIMENSION', 'FQM',
    'IMMERSE', 'LOKi', 'LOL', 'NoTV', 'OMiCRON', 'ORENJI', 'RiVER', 'SFM',
    'SYS', 'TLA', 'XOR', 'YesTV',
]
# Quality related tags
QUALITY_KEYWORDS = [
    '720p', 'AC3', 'DVDRIP', 'DVDSCR', 'H.264', 'HDTV', 'HR' 'WEB-DL', 'XViD',
    'x264',
]

class UrlGrabber(object):
    def __init__(self, url, handle_cookies=False, debug=False):
        self.url = url
        self.handle_cookies = handle_cookies
        self.debug = debug
        self._stream = None
        self.open()

    def open(self):
        request =  urllib2.Request(self.url)
        handlers = []
        if self.handle_cookies:
            handlers.append(
                urllib2.HTTPCookieProcessor(cookielib.LWPCookieJar()),
            )
        if self.debug:
            handlers.append(
                urllib2.HTTPHandler(debuglevel=1),
            )
        opener = urllib2.build_opener(*handlers)
        self._stream = opener.open(request)

    def close(self):
        self._stream.close()

    @property
    def filename(self):
        return urllib2.unquote(os.path.basename(
            self._stream.geturl()))

    def read(self):
        return self._stream.read()

    def readlines(self):
        return self._stream.readlines()

    def download(self, dest_filename):
        self.open()
        try:
            with open(dest_filename, 'w') as out_stream:
                out_stream.write(self.read())
        except IOError, exc:
            print 'Error while writing file %s: %s' % (
                dest_filename,
                str(exc),
            )
        finally:
            self.close()


class Subtitle(object):
    def __init__(self, movie_filename):
        self.movie_filename = os.path.basename(movie_filename)
        self.movie_dirname = os.path.dirname(movie_filename)
        self.show = ''
        self.season = 0
        self.episode = 0
        self.filename = ''
        self.url = ''
        self.quality = 0
        self.score = 0.0
        self.language = ''
        self.group_keyword_count = 0
        self.quality_keyword_count = 0
        self.keyword_count = 0

    def __repr__(self):
        return (' * Filename: %s \n'
                ' * Languages: %s\n'
                ' * Betaseries rating: %d\n'
                ' * Filename similarity: %0.2f\n'
                ' * Scene group keyword matches: %d\n'
                ' * Video quality keyword matches: %d') % (
            self.filename,
            self.language,
            self.quality,
            self.score,
            self.group_keyword_count,
            self.quality_keyword_count,
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
        for keyword in GROUP_KEYWORDS + QUALITY_KEYWORDS:
            keyword_full = self.clean_string(' %s ' % keyword)
            keyword_short = self.clean_string(' %s ' % keyword[:3])
            stop = False
            for j in [keyword_full, keyword_short]:
                for k in [keyword_full, keyword_short]:
                    if j in clean_movie_filename and k in clean_filename:
                        if keyword in GROUP_KEYWORDS:
                            self.group_keyword_count += 1
                        elif keyword in QUALITY_KEYWORDS:
                            self.quality_keyword_count += 1
                        stop = True
                        break
                if stop:
                    break
        self.keyword_count = self.quality_keyword_count + self.group_keyword_count

    def has_forbidden_tags(self):
        for tag in EXCLUDED_TAGS:
            if tag in self.filename:
                return True
        return False

    def download(self):
        dest_prefix = os.path.join(
            self.movie_dirname,
            os.path.splitext(self.movie_filename)[0],
        )
        grabber = UrlGrabber(self.url)
        srt_filename = dest_prefix + '.srt'
        print ' >>> Downloading to: %s' % srt_filename
        if '.zip' in grabber.filename:
            zip_filename = dest_prefix + '.zip'
            grabber.download(zip_filename)
            zip_object = zipfile.ZipFile(zip_filename)
            namelist = zip_object.namelist()
            if self.filename not in namelist:
                print 'ERROR, %s not in zip' % self.filename
                return
            sub_data = zip_object.read(self.filename)
            try:
                with open(srt_filename, 'w') as srt_file:
                    srt_file.write(sub_data)
            except IOError, exc:
                print 'Error while writing file %s: %s' % (
                    filename,
                    str(exc),
                )
            zip_object.close()
            os.remove(zip_filename)
        else:
            grabber.download(srt_filename)

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
            },
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
        parser = self.parse(os.path.basename(movie_filename))
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
                filenames = [result['file']]
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
        if not subtitles:
            return None
        for language in LANGUAGE_ORDER:
            best_subtitles =  [s for s in subtitles
                               if s.language == language
                               and s.quality > 0]
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


if __name__ == '__main__':
    beta = BetaSeries()
    if len(sys.argv) > 1:
        for filename in sys.argv[1:]:
            print ' >>> Checking', filename
            best = beta.find_best(filename)
            if best:
                print ' >>> Found best subtitle:'
                print best
                best.download()
            else:
                print ' >>> No subtitles found.'
    else:
        print 'Please specify at least one file'

