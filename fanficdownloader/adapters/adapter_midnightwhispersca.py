# -*- coding: utf-8 -*-

# Copyright 2011 Fanficdownloader team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import time
import logging
import re
import urllib2

from .. import BeautifulSoup as bs
from ..htmlcleanup import stripHTML
from .. import exceptions as exceptions

from base_adapter import BaseSiteAdapter,  makeDate

# Search for XXX comments--that's where things are most likely to need changing.

# This function is called by the downloader in all adapter_*.py files
# in this dir to register the adapter class.  So it needs to be
# updated to reflect the class below it.  That, plus getSiteDomain()
# take care of 'Registering'.
def getClass():
    return MidnightwhispersCaAdapter # XXX

# Class name has to be unique.  Our convention is camel case the
# sitename with Adapter at the end.  www is skipped.
class MidnightwhispersCaAdapter(BaseSiteAdapter): # XXX

    def __init__(self, config, url):
        BaseSiteAdapter.__init__(self, config, url)

        self.decode = ["Windows-1252",
                       "utf8"] # 1252 is a superset of iso-8859-1.
                               # Most sites that claim to be
                               # iso-8859-1 (and some that claim to be
                               # utf8) are really windows-1252.
        self.is_adult=False
        
        # get storyId from url--url validation guarantees query is only sid=1234
        self.story.setMetadata('storyId',self.parsedUrl.query.split('=',)[1])
        logging.debug("storyId: (%s)"%self.story.getMetadata('storyId'))
        
        # normalized story URL.
        # XXX Most sites don't have the /fanfic part.  Replace all to remove it usually.
        self._setURL('http://' + self.getSiteDomain() + '/viewstory.php?sid='+self.story.getMetadata('storyId'))
        
        # Each adapter needs to have a unique site abbreviation.
        self.story.setMetadata('siteabbrev','mw') # XXX

        # If all stories from the site fall into the same category,
        # the site itself isn't likely to label them as such, so we
        # do.
        self.story.addToList("category","Queer as Folk") # XXX

        # The date format will vary from site to site.
        # http://docs.python.org/library/datetime.html#strftime-strptime-behavior
        self.dateformat = "%B %d, %Y" # XXX
            
    @staticmethod # must be @staticmethod, don't remove it.
    def getSiteDomain():
        # The site domain.  Does have www here, if it uses it.
        return 'www.midnightwhispers.ca' # XXX

    def getSiteExampleURLs(self):
        return "http://"+self.getSiteDomain()+"/viewstory.php?sid=1234"

    def getSiteURLPattern(self):
        return re.escape("http://"+self.getSiteDomain()+"/viewstory.php?sid=")+r"\d+$"

    ## Getting the chapter list and the meta data, plus 'is adult' checking.
    def extractChapterUrlsAndMetadata(self):

        if self.is_adult or self.getConfig("is_adult"):
            # Weirdly, different sites use different warning numbers.
            # If the title search below fails, there's a good chance
            # you need a different number.  print data at that point
            # and see what the 'click here to continue' url says.

            # Furthermore, there's a couple sites now with more than
            # one warning level for different ratings.  And they're
            # fussy about it.  midnightwhispers has three: 10, 3 & 5.
            # we'll try 5 first.
            addurl = "&ageconsent=ok&warning=5" # XXX
        else:
            addurl=""

        # index=1 makes sure we see the story chapter index.  Some
        # sites skip that for one-chapter stories.
        url = self.url+'&index=1'+addurl
        logging.debug("URL: "+url)

        try:
            data = self._fetchUrl(url)
        except urllib2.HTTPError, e:
            if e.code == 404:
                raise exceptions.StoryDoesNotExist(self.url)
            else:
                raise e

        # The actual text that is used to announce you need to be an
        # adult varies from site to site.  Again, print data before
        # the title search to troubleshoot.
            
        # Since the warning text can change by warning level, let's
        # look for the warning pass url.  nfacommunity uses
        # &amp;warning= -- actually, so do other sites.  Must be an
        # eFiction book.
            
        # viewstory.php?sid=1882&amp;warning=4
        # viewstory.php?sid=1654&amp;ageconsent=ok&amp;warning=5
        #print data
        #m = re.search(r"'viewstory.php\?sid=1882(&amp;warning=4)'",data)
        m = re.search(r"'viewstory.php\?sid=\d+((?:&amp;ageconsent=ok)?&amp;warning=\d+)'",data)
        if m != None:
            if self.is_adult or self.getConfig("is_adult"):
                # We tried the default and still got a warning, so
                # let's pull the warning number from the 'continue'
                # link and reload data.
                addurl = m.group(1)
                # correct stupid &amp; error in url.
                addurl = addurl.replace("&amp;","&")
                url = self.url+'&index=1'+addurl
                logging.debug("URL 2nd try: "+url)

                try:
                    data = self._fetchUrl(url)
                except urllib2.HTTPError, e:
                    if e.code == 404:
                        raise exceptions.StoryDoesNotExist(self.url)
                    else:
                        raise e    
            else:
                raise exceptions.AdultCheckRequired(self.url)
            
        if "Access denied. This story has not been validated by the adminstrators of this site." in data:
            raise exceptions.FailedToDownload(self.getSiteDomain() +" says: Access denied. This story has not been validated by the adminstrators of this site.")
            
        # use BeautifulSoup HTML parser to make everything easier to find.
        soup = bs.BeautifulSoup(data)
        # print data


        # Now go hunting for all the meta data and the chapter list.
        
        ## Title
        a = soup.find('a', href=re.compile(r'viewstory.php\?sid='+self.story.getMetadata('storyId')+"$"))
        self.story.setMetadata('title',stripHTML(a)) # title's inside a <b> tag.

        # Find authorid and URL from... author url.
        a = soup.find('a', href=re.compile(r"viewuser.php\?uid=\d+"))
        self.story.setMetadata('authorId',a['href'].split('=')[1])
        self.story.setMetadata('authorUrl','http://'+self.host+'/'+a['href'])
        self.story.setMetadata('author',a.string)

        # Find the chapters:
        for chapter in soup.findAll('a', href=re.compile(r'viewstory.php\?sid='+self.story.getMetadata('storyId')+"&chapter=\d+$")):
            # just in case there's tags, like <i> in chapter titles.
            self.chapterUrls.append((stripHTML(chapter),'http://'+self.host+'/'+chapter['href']+addurl))

        self.story.setMetadata('numChapters',len(self.chapterUrls))

        # eFiction sites don't help us out a lot with their meta data
        # formating, so it's a little ugly.

        # utility method
        def defaultGetattr(d,k):
            try:
                return d[k]
            except:
                return ""

        # <span class="label">Rated:</span> NC-17<br /> etc
        labels = soup.findAll('span',{'class':'label'})
        for labelspan in labels:
            value = labelspan.nextSibling
            label = labelspan.string

            if 'Summary' in label:
                ## Everything until the next span class='label'
                svalue = ""
                while not defaultGetattr(value,'class') == 'label':
                    svalue += str(value)
                    value = value.nextSibling
                self.setDescription(url,svalue)
                #self.story.setMetadata('description',stripHTML(svalue))

            if 'Rated' in label:
                self.story.setMetadata('rating', value)

            if 'Word count' in label:
                self.story.setMetadata('numWords', value)

            if 'Categories' in label:
                cats = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=categories'))
                catstext = [cat.string for cat in cats]
                for cat in catstext:
                    self.story.addToList('category',cat.string)

            if 'Characters' in label:
                chars = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=characters'))
                charstext = [char.string for char in chars]
                for char in charstext:
                    self.story.addToList('characters',char.string)

            ## Not all sites use Genre, but there's no harm to
            ## leaving it in.  Check to make sure the type_id number
            ## is correct, though--it's site specific.
            if 'Genre' in label:
                genres = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=class&type_id=2')) # XXX
                genrestext = [genre.string for genre in genres]
                self.genre = ', '.join(genrestext)
                for genre in genrestext:
                    self.story.addToList('genre',genre.string)

            ## Not all sites use Warnings, but there's no harm to
            ## leaving it in.  Check to make sure the type_id number
            ## is correct, though--it's site specific.
            if 'Warnings' in label:
                warnings = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=class&type_id=2')) # XXX
                warningstext = [warning.string for warning in warnings]
                self.warning = ', '.join(warningstext)
                for warning in warningstext:
                    self.story.addToList('warnings',warning.string)

            if 'Completed' in label:
                if 'Yes' in value:
                    self.story.setMetadata('status', 'Completed')
                else:
                    self.story.setMetadata('status', 'In-Progress')

            if 'Published' in label:
                self.story.setMetadata('datePublished', makeDate(stripHTML(value), self.dateformat))
            
            if 'Updated' in label:
                # there's a stray [ at the end.
                #value = value[0:-1]
                self.story.setMetadata('dateUpdated', makeDate(stripHTML(value), self.dateformat))

        try:
            # Find Series name from series URL.
            a = soup.find('a', href=re.compile(r"viewseries.php\?seriesid=\d+"))
            series_name = a.string
            series_url = 'http://'+self.host+'/'+a['href']

            # use BeautifulSoup HTML parser to make everything easier to find.
            seriessoup = bs.BeautifulSoup(self._fetchUrl(series_url))
            storyas = seriessoup.findAll('a', href=re.compile(r'^viewstory.php\?sid=\d+$'))
            i=1
            for a in storyas:
                # skip 'report this' and 'TOC' links
                if 'contact.php' not in a['href'] and 'index' not in a['href']:
                    if a['href'] == ('viewstory.php?sid='+self.story.getMetadata('storyId')):
                        self.setSeries(series_name, i)
                        break
                    i+=1
            
        except:
            # I find it hard to care if the series parsing fails
            pass
            
    # grab the text for an individual chapter.
    def getChapterText(self, url):

        logging.debug('Getting chapter text from: %s' % url)

        data = self._fetchUrl(url)
        soup = bs.BeautifulStoneSoup(data,
                                     selfClosingTags=('br','hr')) # otherwise soup eats the br/hr tags.
        
        div = soup.find('div', {'id' : 'story'})

        if None == div:
            if "A fatal MySQL error was encountered" in data:
                raise exceptions.FailedToDownload("Error downloading Chapter: %s!  Database error on the site reported!" % url)
            else:
                raise exceptions.FailedToDownload("Error downloading Chapter: %s!  Missing required element!" % url)
    
        return self.utf8FromSoup(url,div)
