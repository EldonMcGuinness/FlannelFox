#-------------------------------------------------------------------------------
# Name:        Settings
# Purpose:     Contains the settings for the application and threads
#
# TODO:        Move the reading of config xml into this file
#              Move some setting into external xml file
#              Move the config files to ~/.flannelfox
#-------------------------------------------------------------------------------
# -*- coding: utf-8 -*-

# System Includes
import datetime, json, math, time, os
import xml.etree.ElementTree as ET

# Third party modules
import requests
# Needed to fix an SSL issue with requests
import urllib3.contrib.pyopenssl
urllib3.contrib.pyopenssl.inject_into_urllib3()
from bs4 import BeautifulSoup

import flannelfox

from flannelfox import logging

# #############################################################################
# Special variables to handle formatting names
# #############################################################################

# These are torrentTitle prefixes that should be ignored when creating torrent
# objects. This is mainly to fix rss feeds that have bad file entries in front.
BAD_PREFIXES = [
    u"autofill fail",
    u"TvHD \d+ \d+",
    u"TvSD \d+ \d+"
]

# These are keywords such as sources that come in multiple forms, but need to
# be reconciled into one to make it easier to grab them
KEYWORD_SYNONYMS = {
    u"blu-ray":u"bluray",
    u"bdrip":u"bluray",
    u"brrip":u"bluray",
    u"hd-dvd":u"hddvd",
    u"web-dl":u"webdl",
    u"webrip":u"webdl",
    u"web-rip":u"webdl",
    u"h.264":u"h264",
    u"v0 \(vbr\)":u"v0vbr",
    u"v0\(vbr\)":u"v0vbr",
    u"v1 \(vbr\)":u"v1vbr",
    u"v1\(vbr\)":u"v1vbr",
    u"v2 \(vbr\)":u"v2vbr",
    u"v2\(vbr\)":u"v2vbr",
    u"v8 \(vbr\)":u"v8vbr",
    u"v8\(vbr\)":u"v8vbr",
    u"aps \(vbr\)":u"apsvbr",
    u"aps\(vbr\)":u"apsvbr",
    u"apx \(vbr\)":u"apxvbr",
    u"apx\(vbr\)":u"apxvbr",
    u"apx \(vbr\)":u"apxvbr",
    u"apx\(vbr\)":u"apxvbr"
}

# This is a list of properties that are ignored during torrent comparison
FUZZY_PROPERTIES = [

# Properties that should be ignored, rss fields that should not be considered
# when matching.
    "quality",
    "source",
    "container",
    "codec",

# Properties that should be ignored, rss fields that do not pertain to matching
    "torrentTitle",
    "url",
    "feedDestination",
    
# More properties that should be ignored, database fields that do not pertain to
# matching

    "addedOn",
    "added",
    "queuedOn",
    "minTime",
    "minRatio",
    "comparison",
    # DUPLICATE    "feedDestination",
    "hashString",
    
# More properties that should be ignored, transmission response fields that do 
# not pertain to matching

    # DUPLICATE    "hashString", 
    "id",
    "error",
    "errorString",
    "uploadRatio",
    "percentDone",
    "doneDate",
    "activityDate",
    "rateUpload",
    "downloadDir",
    "seedTime",
    # DUPLICATE    "comparison",
    "status"
]

# #############################################################################


def changeCharset(data, charset="utf-8", type="xml"):

    logger = logging.getLogger(__name__)
    logger.debug("Tyring to convert {0} to {1}".format(charset, type))

    if charset is None:
        charset = "utf-8"

    try:
        data = BeautifulSoup(data, type)
        data = data.encode(encoding=charset, errors="xmlcharrefreplace")
    except Exception as e:
        logger.debug("Charset Conversion issue".format(e))
        data = ""

    return data


def modificationDate(filename):
    logger = logging.getLogger(__name__)
    try:
        return int(datetime.datetime.fromtimestamp(os.path.getmtime(filename)).strftime("%s"))
    except:
        logger.error("There was a problem getting the timestamp for:\n{0}".format(filename))
        return -1


def isCacheUpdateNeeded(force=False, cacheFilename=None, frequency=360):
    logger = logging.getLogger(__name__)
    try:
        # Get the modification time
        lastModified = modificationDate(cacheFilename)

        if lastModified == -1:
            return True

        logger.debug("Checking cache: {0} {1}:{2}".format(cacheFilename, frequency, math.ceil((time.time()/60 - lastModified/60)))    )
        difference = math.ceil((time.time()/60 - lastModified/60))
        if difference >= frequency:
            logger.debug("Cache update needed".format(cacheFilename) )
            return True
        else:
            logger.debug("Cache update not needed".format(cacheFilename))
            return False
            
    except Exception as e:
        logger.error("Cache update for {0} could not be preformed".format(cacheFilename))



def updateCacheFile(force=False, cacheFilename=None, data=None, frequency=360):
    '''
    Used to update cache files for api calls. This is needed so we do not keep
    asking the api servers for the same information on a frequent basis. The
    fault frequency is to ask once an hour.

    force: preform the update reguardless of frequency
    location: where to save the file
    frequency: how often to update the file in minutes
    '''

    logger = logging.getLogger(__name__)

    try:
        if isCacheUpdateNeeded(cacheFilename=cacheFilename, frequency=frequency):
            logger.debug("Cache update for {0} needed".format(cacheFilename))
            with open(cacheFilename, 'w') as cache:
                cache.write(data)

        else:
            logger.debug("Cache update for {0} not needed".format(cacheFilename)    )

    except Exception as e:
        logger.error("There was a problem writing a cache file {0}: {1}".format(cacheFilename, e))


def readLastfmArtists(configFolder=flannelfox.settings['files']['lastfmConfigDir']):
    logger = logging.getLogger(__name__)
    majorFeeds = {}

    try:

        for configFile in os.listdir(configFolder):

            # Skip non-json files
            if not configFile.endswith('.json'):
                continue

            logger.debug("Loading LastFM config file: {0}".format(os.path.join(configFolder,configFile)))

            # Try to read in the lastfm lists
            try:
                with open(os.path.join(configFolder,configFile)) as lastfmJson:
                    lastfmAritstsLists = json.load(lastfmJson)
            except Exception as e:
                logger.error("There was a problem reading the lastfm config file\n{0}".format(e))
                continue

            try:
                for artistsList in lastfmAritstsLists:

                    # Make sure our list at least has some basic parts
                    if (artistsList.get("username", None) is None or
                        artistsList.get("api_key", None) is None or
                        artistsList.get("list_name", None) is None or
                        artistsList.get("type", None) is None or
                        artistsList.get("feedDestination", None) is None or
                        artistsList.get("minorFeeds", None) is None):

                        continue

                    headers = {
                        "Content-Type":"application/json",
                        "user-agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.99 Safari/537.36"
                    }

                    currentPage = 1
                    maxPages = 2
                    replies = []
                    artists = []
                    feedName = None
                    feedType = None
                    feedDestination = None
                    minorFeeds = []
                    feedFilters = []
                    httpResponse = -1
                    useCache = False

                    cacheFileName = "{0}/{1}".format(flannelfox.settings['files']['lastfmCacheDir'],artistsList.get("list_name")+'.'+configFile)
                    if not os.path.exists(os.path.dirname(cacheFileName)):
                        try:
                            os.makedirs(os.path.dirname(cacheFileName))
                        except OSError as exc: # Guard against race condition
                            continue

                    # Get the feedName
                    try:
                        feedName = unicode(artistsList.get("list_name",u"").lower().strip())
                        if feedName == u"":
                            raise ValueError
                    except (ValueError, KeyError) as e:
                        logger.warning("Feeds with out names are not permitted")
                        continue

                    # Get the feedType
                    try:
                        feedType = unicode(artistsList.get("type",u"none").lower().strip())
                    except (ValueError, KeyError) as e:
                        feedType = u"none"
                        continue

                    # Get the feedDestination
                    try:
                        feedDestination = unicode(artistsList.get("feedDestination",u"").strip())
                        # TODO: Check if the location exists
                    except (ValueError, KeyError) as e:
                        logger.warning("The feed has an invalid destination value")
                        continue

                    # Collect the feeds
                    try:
                        if artistsList.get("minorFeeds",[]) is not None and len(artistsList.get("minorFeeds",[])) > 0:
                            for minorFeed in artistsList.get("minorFeeds",[]):
                                url = unicode(minorFeed.get("url",u"").strip())
                                minTime = int(minorFeed.get("minTime",u"0").strip()) # Hours Int
                                minRatio = float(minorFeed.get("minRatio",u"0.0").strip()) # Ratio Float
                                comparison = minorFeed.get("comparison",u"or").strip() # Comparison String
                                minorFeeds.append({u"url":url,u"minTime":minTime,u"minRatio":minRatio,u"comparison":comparison})
                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning("The feed contains an invalid minorFeed:\n{0}".format(e))
                        continue

                    if not isCacheUpdateNeeded(cacheFilename=cacheFileName):
                        useCache = True

                    if not useCache:
                        while currentPage <= maxPages:
                            reply = None

                            call = {}
                            call.update({"method":"library.getArtists"})
                            call.update({"api_key":artistsList.get("api_key")})
                            call.update({"user":artistsList.get("username")})
                            call.update({"format":"json"})
                            call.update({"page":currentPage})

                            try:
                                # TODO: Covert this to a pool
                                r = requests.get(flannelfox.settings['apis']['lastfm'], headers=headers, params=call, timeout=60)
                                httpResponse = r.status_code
                            except Exception as e:
                                httpResponse = -1
                                logger.error("There was a problem fetching a Lastfm album page\n{0}".format(httpResponse))

                            if httpResponse == 200:
                                reply = r.json()
                            else:
                                logger.error("There was a problem fetching a Lastfm album page\n{0}".format(httpResponse))
                                replies = []
                                break # TODO: Replace this with an exception

                            maxPages = int(reply["artists"]["@attr"]["totalPages"])
                            replies.extend(reply["artists"]["artist"][:])
                            logger.error("Fetching Lastfm album page {0} of {1}: [{2}]".format(currentPage, maxPages, httpResponse))
                            currentPage = currentPage + 1

                        for artist in replies:
                            artists.append(artist["name"])

                        # If we are able to get a list then cache it
                        # TODO: See if Last-Modified can be added to save this step when possible
                        if httpResponse == 200:
                            updateCacheFile(cacheFilename=cacheFileName, data=json.dumps(artists))
                        else:
                            useCache = True

                    if useCache:
                        try:
                            logger.debug("Reading cache file for [{0}]".format(cacheFileName))
                            with open(cacheFileName) as cache:
                                artists = json.load(cache)
                        except Exception as e:
                            logger.error("There was a problem reading a lastfm list cache file: {0}".format(e))
                            continue

                    # Collect the feedFilters
                    try:
                        feedFilterList = []

                        majorFeedFilters = artistsList.get("filters", [])

                        for filterItem in majorFeedFilters:
                        
                            # Loop through each show and append a filter for it
                            for artist in artists:

                                ruleList = []

                                # Clean the artist name
                                artist = artist.lower().strip().replace(u" & ", u" and ")

                                ruleList.append({u"key":"artist", u"val":artist, u"exclude":False})

                                # Load the excludes
                                for exclude in filterItem.get("exclude", []):
                                    key, val = exclude.items()[0]
                                    ruleList.append({u"key":key, u"val":val, u"exclude":True})

                                for include in filterItem.get("include", []):
                                    key, val = include.items()[0]
                                    ruleList.append({u"key":key, u"val":val, u"exclude":False})

                                feedFilterList.append(ruleList)

                    except Exception as e:
                        logger.warning("The feedFilters contains an invalid rule:\n{0}".format(e))
                        continue

                    # Append the Config item to the dict
                    majorFeeds[feedName] = {u"feedName":feedName,u"feedType":feedType,u"feedDestination":feedDestination,u"minorFeeds":minorFeeds,u"feedFilters":feedFilterList}

            except Exception as e:
                logger.error("There was a problem reading a lastfm artists list file:\n{0}".format(e))
                httpResponse = -1
                artists = []
    except Exception as e:
        # This should only happen if there was an issue getting files names from the directory
        pass


    return majorFeeds


def readTraktTV(configFolder=flannelfox.settings['files']['traktConfigDir']):
    '''
    Reads the tv I want from the trakt.tv api
    Content-Type:application/json
    trakt-api-version:2
    trakt-api-key:XXXX
    '''

    logger = logging.getLogger(__name__)
    logger.debug("Reading TraktTV Feed")

    majorFeeds = {}
    TRAKT_TV_LISTS = []

    try:

        for configFile in os.listdir(configFolder):
            
            # Skip non-json files
            if not configFile.endswith('.json'):
                continue

            logger.debug("Loading TraktTV config file: {0}".format(os.path.join(configFolder,configFile)))

            # Try to read in the trakt lists
            try:
                with open(os.path.join(configFolder,configFile)) as traktJson:
                    TRAKT_TV_LISTS = json.load(traktJson)
            except Exception as e:
                logger.error("There was a problem reading the trakt config file\n{0}".format(e))
                continue

            # Loop through the trakt.tv lists
            try:

                for traktList in TRAKT_TV_LISTS:

                    # Make sure our list at least has some basic parts
                    if (traktList.get("username", None) is None or
                        traktList.get("api_key", None) is None or
                        traktList.get("list_name", None) is None or
                        traktList.get("type", None) is None or
                        traktList.get("feedDestination", None) is None or
                        traktList.get("minorFeeds", None) is None):

                        continue

                    # Setup some variables for the feed
                    feedName = None
                    feedType = None
                    feedDestination = None
                    minorFeeds = []
                    feedFilters = []
                    traktListResults = []
                    httpResponse = -1
                    title = None
                    year = None
                    useCache = False

                    # Get the feedName
                    try:
                        feedName = unicode(traktList.get("list_name",u"").lower().strip())
                        if feedName == u"":
                            raise ValueError
                    except (ValueError, KeyError) as e:
                        logger.warning("Feeds with out names are not permitted")
                        continue

                    cacheFileName = os.path.join(flannelfox.settings['files']['traktCacheDir'],feedName+'.'+configFile)

                    if not os.path.exists(os.path.dirname(cacheFileName)):
                        try:
                            os.makedirs(os.path.dirname(cacheFileName))
                        except OSError as exc: # Guard against race condition
                            continue

                    headers = {
                        "user-agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.99 Safari/537.36",
                        "Content-Type":"application/json",
                        "trakt-api-version":"2",
                        "trakt-api-key":traktList.get("api_key","")
                    }

      
                    # Get the feedType
                    try:
                        feedType = unicode(traktList.get("type",u"none").lower().strip())
                    except (ValueError, KeyError) as e:
                        feedType = u"none"
                        continue

                    # Get the feedDestination
                    try:
                        feedDestination = unicode(traktList.get("feedDestination",u"").strip())
                        # TODO: Check if the location exists
                    except (ValueError, KeyError) as e:
                        logger.warning("The feed has an invalid destination value")
                        continue

                    # Collect the feeds
                    try:
                        if traktList.get("minorFeeds",[]) is not None and len(traktList.get("minorFeeds",[])) > 0:
                            for minorFeed in traktList.get("minorFeeds",[]):
                                url = unicode(minorFeed.get("url",u"").strip())
                                minTime = int(minorFeed.get("minTime",u"0").strip()) # Hours Int
                                minRatio = float(minorFeed.get("minRatio",u"0.0").strip()) # Ratio Float
                                comparison = minorFeed.get("comparison",u"or").strip() # Comparison String
                                minorFeeds.append({u"url":url,u"minTime":minTime,u"minRatio":minRatio,u"comparison":comparison})
                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning("The feed contains an invalid minorFeed:\n{0}".format(e))
                        continue

                    if not isCacheUpdateNeeded(cacheFilename=cacheFileName):
                        useCache = True

                    if not useCache:
                        try:
                            r = requests.get("{0}/users/{1}/lists/{2}/items".format(flannelfox.settings['apis']['trakt'], traktList["username"], traktList["list_name"]), headers=headers, timeout=60)
                            httpResponse = r.status_code

                            if httpResponse == 200:
                                traktListResults = r.json()
                            else:
                                logger.error("There was a problem fetching a trakt list file: {0}".format(httpResponse))
                            
                        except Exception as e:
                            logger.error("There was a problem fetching a trakt list file: {0}".format(e))
                            traktListResults = []
                            httpResponse = -1

                        logger.error("Fetching trakt list page: [{0}]".format(httpResponse))

                        # If we are able to get a list then cache it
                        # TODO: See if Last-Modified can be added to save this step when possible
                        if httpResponse == 200:
                            updateCacheFile(cacheFilename=cacheFileName, data=json.dumps(traktListResults))
                        else:
                            useCache = True

                    if useCache:
                        try:
                            logger.debug("Reading cache file for [{0}]".format(cacheFileName))
                            with open(cacheFileName) as cache:
                                traktListResults = json.load(cache)
                        except Exception as e:
                            logger.error("There was a problem reading a trakt list cache file: {0}".format(e))
                            continue

                    # Collect the feedFilters
                    try:
                        feedFilterList = []

                        majorFeedFilters = traktList.get("filters", [])

                        for filterItem in majorFeedFilters:

                            # Loop through each show and append a filter for it
                            for item in traktListResults:
                                ruleList = []

                                if traktList.get("like", False):
                                    titleMatchMethod = u"titleLike"
                                else:
                                    titleMatchMethod = u"title"

                                # Make sure we have some shows to fetch
                                # TODO: make this use the type field in the json file to determine if it should be show or movie
                                if "show" not in item and feedType == "tv":
                                    # This happens if you select the wrong type of media tv/movie
                                    continue;
                                elif "movie" not in item and feedType == "movie":
                                    # This happens if you select the wrong type of media tv/movie
                                    continue;

                                elif "show" in item and feedType == "tv":
                                    item = item["show"]
                                    title = item["title"].lower().strip().replace(u" & ", u" and ")

                                elif "movie" in item and feedType == "movie":
                                    item = item["movie"]
                                    title = item["title"].lower().strip().replace(u" & ", u" and ")
                                    year = item["year"]

                                else:
                                    continue


                                ruleList.append({u"key":titleMatchMethod, u"val":title, u"exclude":False})
                                
                                if year is not None:
                                    ruleList.append({u"key":"year", u"val":year, u"exclude":False})

                                # Load the excludes
                                for exclude in filterItem.get("exclude", []):
                                    key, val = exclude.items()[0]
                                    ruleList.append({u"key":key, u"val":val, u"exclude":True})

                                for include in filterItem.get("include", []):
                                    key, val = include.items()[0]
                                    ruleList.append({u"key":key, u"val":val, u"exclude":False})


                                feedFilterList.append(ruleList)

                    except Exception as e:
                        logger.warning("The feedFilters contains an invalid rule:\n{0}".format(e))
                        continue

                    # Append the Config item to the dict
                    majorFeeds[configFile+'.'+feedName] = {u"feedName":feedName,u"feedType":feedType,u"feedDestination":feedDestination,u"minorFeeds":minorFeeds,u"feedFilters":feedFilterList}
                #f = open("feeds_new.json", 'w')
                #json.dump(majorFeeds, f)
            except Exception as e:
                logger.error("There was a problem reading a trakt list file:\n{0}".format(e))

    except Exception as e:
        # This should only happen if there was an issue getting files names from the directory
        pass
    logger.debug("=================")
    logger.debug("TraktMajorFilters")
    logger.debug("=================")
    logger.debug(majorFeeds)
    logger.debug("=================")
    return majorFeeds


def readGoodreads(configFolder=flannelfox.settings['files']['goodreadsConfigDir']):
    '''
    Get the authors I like from goodreads
    '''

    logger = logging.getLogger(__name__)
    logger.debug("Reading Goodreads Feed")

    majorFeeds = {}
    goodreadsLists = []

    try:

        for configFile in os.listdir(configFolder):
            
            # Skip non-json files
            if not configFile.endswith('.json'):
                continue

            logger.debug("Loading Goodreads config file: {0}".format(os.path.join(configFolder,configFile)))

            # Try to read in the goodreads lists
            try:
                with open(os.path.join(configFolder,configFile)) as goodreadsJson:
                    goodreadsLists = json.load(goodreadsJson)
            except Exception as e:
                logger.error("There was a problem reading the goodreads config file\n{0}".format(e))
                continue

            # Loop through the goodreads lists
            try:

                for goodreadsList in goodreadsLists:

                    # Make sure our list at least has some basic parts
                    if (goodreadsList.get("username", None) is None or
                        goodreadsList.get("api_key", None) is None or
                        goodreadsList.get("list_name", None) is None or
                        goodreadsList.get("type", None) is None or
                        goodreadsList.get("feedDestination", None) is None or
                        goodreadsList.get("minorFeeds", None) is None):

                        continue

                    # Setup some variables for the feed
                    feedName = None
                    feedType = None
                    feedDestination = None
                    minorFeeds = []
                    feedFilters = []
                    goodreadsListResults = []
                    httpResponse = -1
                    title = None
                    year = None
                    useCache = False

                    # Get the feedName
                    try:
                        feedName = unicode(goodreadsList.get("list_name",u"").lower().strip())
                        if feedName == u"":
                            raise ValueError
                    except (ValueError, KeyError) as e:
                        logger.warning("Feeds with out names are not permitted")
                        continue

                    cacheFileName = os.path.join(flannelfox.settings['files']['goodreadsCacheDir'],feedName+'.'+configFile)

                    if not os.path.exists(os.path.dirname(cacheFileName)):
                        try:
                            os.makedirs(os.path.dirname(cacheFileName))
                        except OSError as exc: # Guard against race condition
                            continue

                    headers = {
                        "user-agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.99 Safari/537.36",
                    }

                    params = {
                        'key':goodreadsList.get("api_key", None)
                    }
      
                    # Get the feedType
                    try:
                        feedType = unicode(goodreadsList.get("type",u"none").lower().strip())
                    except (ValueError, KeyError) as e:
                        feedType = u"none"
                        continue

                    # Get the feedDestination
                    try:
                        feedDestination = unicode(goodreadsList.get("feedDestination",u"").strip())
                        # TODO: Check if the location exists
                    except (ValueError, KeyError) as e:
                        logger.warning("The feed has an invalid destination value")
                        continue

                    # Collect the feeds
                    try:
                        if goodreadsList.get("minorFeeds",[]) is not None and len(goodreadsList.get("minorFeeds",[])) > 0:
                            for minorFeed in goodreadsList.get("minorFeeds",[]):
                                url = unicode(minorFeed.get("url",u"").strip())
                                minTime = int(minorFeed.get("minTime",u"0").strip()) # Hours Int
                                minRatio = float(minorFeed.get("minRatio",u"0.0").strip()) # Ratio Float
                                comparison = minorFeed.get("comparison",u"or").strip() # Comparison String
                                minorFeeds.append({u"url":url,u"minTime":minTime,u"minRatio":minRatio,u"comparison":comparison})
                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning("The feed contains an invalid minorFeed:\n{0}".format(e))
                        continue

                    if not isCacheUpdateNeeded(cacheFilename=cacheFileName):
                        useCache = True

                    if not useCache:
                        try:
                            r = requests.get("{0}/user/show/{1}.xml".format(flannelfox.settings['apis']['goodreads'], goodreadsList["username"]), headers=headers, params=params, timeout=60)
                            httpResponse = r.status_code

                            if httpResponse == 200:
                                # Parse the RSS XML and turn it into a json list
                                xmldata = ET.fromstring(r.text)
                                authors = xmldata.find('favorite_authors')
                                goodreadsListResults = []

                                for item in authors.iter('author'):
                                    try:
                                        author = item.find('name').text

                                        if author is not None and author != "":
                                            author = unicode(author.strip())
                                            author = author.replace(u" & ",u" and ")
                                            goodreadsListResults.append(author)
                                        else:
                                            continue
                                    except:
                                        continue

                            else:
                                logger.error("There was a problem fetching a goodreads list file: {0}".format(httpResponse))
                            
                        except Exception as e:
                            logger.error("There was a problem fetching a goodreads list file: {0}".format(e))
                            goodreadsListResults = []
                            httpResponse = -1

                        logger.error("Fetching goodreads list page: [{0}]".format(httpResponse))

                        # If we are able to get a list then cache it
                        # TODO: See if Last-Modified can be added to save this step when possible
                        if httpResponse == 200:
                            updateCacheFile(cacheFilename=cacheFileName, data=json.dumps(goodreadsListResults))
                        else:
                            useCache = True

                    if useCache:
                        try:
                            logger.debug("Reading cache file for [{0}]".format(cacheFileName))
                            with open(cacheFileName) as cache:
                                goodreadsListResults = json.load(cache)
                        except Exception as e:
                            logger.error("There was a problem reading a goodreads list cache file: {0}".format(e))
                            continue

                    # Collect the feedFilters
                    try:
                        feedFilterList = []

                        majorFeedFilters = goodreadsList.get("filters", [])

                        for filterItem in majorFeedFilters:

                            # Loop through each author and append a filter for it
                            for item in goodreadsListResults:
                                ruleList = []

                                if goodreadsList.get("like", False):
                                    titleMatchMethod = u"titleLike"
                                else:
                                    titleMatchMethod = u"title"

                                ruleList.append({u"key":titleMatchMethod, u"val":title, u"exclude":False})
                                
                                # Load the excludes
                                for exclude in filterItem.get("exclude", []):
                                    key, val = exclude.items()[0]
                                    ruleList.append({u"key":key, u"val":val, u"exclude":True})

                                for include in filterItem.get("include", []):
                                    key, val = include.items()[0]
                                    ruleList.append({u"key":key, u"val":val, u"exclude":False})


                                feedFilterList.append(ruleList)

                    except Exception as e:
                        logger.warning("The feedFilters contains an invalid rule:\n{0}".format(e))
                        continue

                    # Append the Config item to the dict
                    majorFeeds[configFile+'.'+feedName] = {u"feedName":feedName,u"feedType":feedType,u"feedDestination":feedDestination,u"minorFeeds":minorFeeds,u"feedFilters":feedFilterList}
                #f = open("feeds_new.json", 'w')
                #json.dump(majorFeeds, f)
            except Exception as e:
                logger.error("There was a problem reading a goodreads list file:\n{0}".format(e))

    except Exception as e:
        # This should only happen if there was an issue getting files names from the directory
        pass
    logger.debug("=================")
    logger.debug("GoodreadsFilters")
    logger.debug("=================")
    logger.debug(majorFeeds)
    logger.debug("=================")
    return majorFeeds


def readRSS(configFolder=flannelfox.settings['files']['rssConfigDir']):
    '''
    Read the RSSFeedConfig file

    rssFilter children are stackable and help to refine the filter

    An empty or non-existant rssFilters will result in all items being a
    match

    Takes the location of the config file as a parameter
    Returns a dict of filters to match torrents with

    TODO: Convert this feed from XML to JSON
    '''
    logger = logging.getLogger(__name__)

    majorFeeds = {}
    RSS_LISTS = []

    configFiles = os.listdir(configFolder)

    logger.debug("Reading Count: {0} feeds".format(len(configFiles)))

    try:

        for configFile in configFiles:
            
            # Skip non-json files
            if not configFile.endswith('.json'):
                continue

            logger.debug("Loading RSS config file: {0}".format(os.path.join(configFolder,configFile)))

            # Try to read in the rss lists
            try:
                with open(os.path.join(configFolder,configFile)) as rssJson:
                    RSS_LISTS = json.load(rssJson)
            except Exception as e:
                logger.error("There was a problem reading the rss config file\n{0}".format(e))
                continue

            # Loop through the rss lists
            try:

                for rssList in RSS_LISTS:
                    rssList = rssList.get("majorFeed")

                    # Make sure our list at least has some basic parts
                    if (rssList.get("list_name", None) is None or
                        rssList.get("feedDestination", None) is None or
                        rssList.get("minorFeeds", None) is None):
                        continue

                    # Setup some variables for the feed
                    feedName = None
                    feedType = None
                    feedDestination = None
                    minorFeeds = []
                    feedFilters = []
                    httpResponse = -1
                    title = None
                    year = None
                    useCache = False

                    # Get the feedName
                    try:
                        feedName = unicode(rssList.get("list_name",u"").lower().strip())
                        if feedName == u"":
                            raise ValueError
                    except (ValueError, KeyError) as e:
                        logger.warning("Feeds with out names are not permitted")
                        continue

                    headers = {
                        "user-agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.99 Safari/537.36",
                    }
      
                    # Get the feedType
                    try:
                        feedType = unicode(rssList.get("type",u"none").lower().strip())
                    except (ValueError, KeyError) as e:
                        feedType = u"none"
                        continue

                    # Get the feedDestination
                    try:
                        feedDestination = unicode(rssList.get("feedDestination",u"").strip())
                        # TODO: Check if the location exists
                    except (ValueError, KeyError) as e:
                        logger.warning("The feed has an invalid destination value")
                        continue

                    # Collect the feeds
                    try:
                        if rssList.get("minorFeeds",[]) is not None and len(rssList.get("minorFeeds",[])) > 0:
                            for minorFeed in rssList.get("minorFeeds",[]):
                                url = unicode(minorFeed.get("url",u"").strip())
                                minTime = int(minorFeed.get("minTime",u"0").strip()) # Hours Int
                                minRatio = float(minorFeed.get("minRatio",u"0.0").strip()) # Ratio Float
                                comparison = minorFeed.get("comparison",u"or").strip() # Comparison String
                                minorFeeds.append({u"url":url,u"minTime":minTime,u"minRatio":minRatio,u"comparison":comparison})
                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning("The feed contains an invalid minorFeed:\n{0}".format(e))
                        continue

                    # Collect the feedFilters
                    try:
                        feedFilterList = []

                        feedFilters = rssList.get("filters", [])

                        # Loop through each show and append a filter for it
                        for filterItem in feedFilters:

                            ruleList = []

                            # Load the excludes
                            for exclude in filterItem.get("exclude", []):
                                key, val = exclude.items()[0]
                                ruleList.append({u"key":key, u"val":val, u"exclude":True})

                            for include in filterItem.get("include", []):
                                key, val = include.items()[0]
                                ruleList.append({u"key":key, u"val":val, u"exclude":False})

                            feedFilterList.append(ruleList)

                    except Exception as e:
                        logger.warning("The feedFilters contains an invalid rule:\n{0}".format(e))
                        continue

                    # Append the Config item to the dict
                    majorFeeds[configFile+'.'+feedName] = {u"feedName":feedName,u"feedType":feedType,u"feedDestination":feedDestination,u"minorFeeds":minorFeeds,u"feedFilters":feedFilterList}

            except Exception as e:
                logger.error("There was a problem reading a rss list file:\n{0}".format(e))

    except Exception as e:
        # This should only happen if there was an issue getting files names from the directory
        pass

    return majorFeeds