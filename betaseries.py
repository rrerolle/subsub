#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib2, urllib
import json
import difflib

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

class Subtitle(object):
    def __init__(self, name, season, episode):
        self.name = name
        self.season = season
        self.episode = episode
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

    def parse(self, filename):
        for serie in SERIES:
            parser = SeriesParser(name=serie)
            parser.parse(data=filename)
            if parser.valid:
                break
        return parser

    def clean_string(self, string):
        return string.lower().replace('.', ' ').replace('-', ' ')

    def get_subtitle_info(self, subtitle, name, season, episode):
        subtitles = []
        if subtitle['episode'] != str(episode):
            return

        if 'content' not in subtitle and '.srt' in subtitle['file']:
            subtitle['content'] = {'0': subtitle['file']}

        for sub_filename in subtitle['content'].values():
            if not sub_filename:
                continue
            ignore = False
            for tag in EXCLUDED_TAGS:
                if tag in sub_filename:
                    ignore = True
                    break
            if ignore:
                continue
            sub = Subtitle(name, season, episode)
            sub.filename = sub_filename
            sub.url = subtitle['url']
            sub.language = subtitle['language']
            sub.score = difflib.SequenceMatcher(
                None,
                filename,
                sub.filename,
            ).ratio()
            filename_clean = self.clean_string(filename)
            sub_filename_clean = self.clean_string(sub.filename)
            for keyword in KEYWORDS:
                keyword_full = self.clean_string(' %s ' % keyword)
                keyword_short = self.clean_string(' %s ' % keyword[:3])
                stop = False
                for j in [keyword_full, keyword_short]:
                    for k in [keyword_full, keyword_short]:
                        if j in filename_clean and k in sub_filename_clean:
                            sub.keyword_count += 1
                            stop = True
                            break
                    if stop:
                        break
            sub.quality = subtitle['quality']
            subtitles.append(sub)
        return subtitles

    def get_subtitles(self, filename):
        parser = self.parse(filename)
        if not parser.valid:
            return []
        url = self.get_show_url(parser.name)
        if not url:
            return
        results = self.query(
            '/subtitles/show/%s.json' % url, {
                'season': parser.season,
                'episode': parser.episode,
            }
        ).get('subtitles', {})

        subtitles = []
        for subtitle in results.values():
            subtitles.extend(self.get_subtitle_info(
                    subtitle,
                    parser.name,
                    parser.season,
                    parser.episode,
                ) or []
            )

        return subtitles

    def find_best(self, filename):
        subtitles = b.get_subtitles(filename)
        print '\n'.join(str(s) for s in subtitles)
        ignored_subtitle = None
        for language_index, language in enumerate(LANGUAGE_ORDER):
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
                best_subtitle = best_subtitles[-1]
                if (language_index == len(LANGUAGE_ORDER) - 1
                    or best_subtitle.quality >= 2
                    or best_subtitle.score >= 5
                    or best_subtitle.keyword_count >= 1
                ):
                    if (ignored_subtitle
                        and ignored_subtitle.quality >= best_subtitle.quality
                        and ignored_subtitle.score >= best_subtitle.score
                        and ignored_subtitle.keyword_count >= best_subtitle.keyword_count
                    ):
                        best_subtitle = ignored_subtitle
                    print "BEST: %s" % best_subtitle
                    return best_subtitle
                else:
                    ignored_subtitle = best_subtitle
                    print "ignored %s" % ignored_subtitle


files = [
#    "The Good Wife S03E01 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E02 PROPER 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E04 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E05 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E06 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E07 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "The Good Wife S03E08 720p WEB-DL DD5.1 H.264-NFHD.mkv",
#    "Californication.S05E01.720p.HDTV.x264-IMMERSE.mkv",
#    "Desperate Housewives - 8x12 - What's the Good of Being Good.mkv",
#    "Dexter.S06E01.720p.HDTV.x264-IMMERSE.mkv",
#    "Breaking.Bad.S04E07.VOSTFR.720p.WEB-DL.DD5.1.H.264-GKS.mkv",
#    "Breaking.Bad.S04E08.Hermanos.720p.WEB-DL.DD5.1.H.264-TB.mkv",
    "Breaking.Bad.S04E09.Bug.720p.WEB-DL.DD5.1.H.264-TB.mkv",
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

from flexget.utils.titles.series import SeriesParser

b = BetaSeries()

for filename in files:
    print ' -- ', filename
    print b.find_best(filename)
    from time import sleep
    sleep(1)
