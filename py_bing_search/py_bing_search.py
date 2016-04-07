import urllib2
import requests
import time
import datetime
import dateutil.parser
from requests import Request

class PyBingException(Exception):
    pass


class PyBingSearch(object):

    QUERY_URL = 'https://api.datamarket.azure.com/Bing/SearchWeb/Web' \
                 + '?Query={}&$top={}&$skip={}&$format={}'

    def __init__(self, api_key, safe=False):
        self.api_key = api_key
        self.safe = safe

    def search(self, query, limit=50, offset=0, format='json'):
        ''' Returns the result list, and also the uri for next page (returned_list, next_uri) '''
        return self._search(query, limit, offset, format)

    def search_all(self, query, limit=50, format='json'):
        ''' Returns a single list containing up to 'limit' Result objects'''
        results, next_link = self._search(query, limit, 0, format)
        while next_link and len(results) < limit:
            max = limit - len(results)
            more_results, next_link = self._search(query, max, len(results), format)
            if not more_results:
                break
            results += more_results
        return results

    def _search(self, query, limit, offset, format):
        '''
        Returns a list of result objects, with the url for the next page bing search url.
        '''
        url = self.QUERY_URL.format(urllib2.quote("'{}'".format(query)), limit, offset, format)
        r = requests.get(url, auth=("", self.api_key))
        try:
            json_results = r.json()
        except ValueError as vE:
            if not self.safe:
                raise PyBingException("Request returned with code %s, error msg: %s" % (r.status_code, r.text))
            else:
                print "[ERROR] Request returned with code %s, error msg: %s. \nContinuing in 5 seconds." % (r.status_code, r.text)
                time.sleep(5)
        try:
            next_link = json_results['d']['__next']
        except KeyError as kE:
            if not self.safe:
                raise PyBingException("Couldn't extract next_link: KeyError: %s" % kE)
            else:
                print "Couldn't extract next_link: KeyError: %s" % kE
                time.sleep(3)
            next_link = ''
        return [Result(single_result_json) for single_result_json in json_results['d']['results']], next_link


class PyBingNewsSearch(PyBingSearch):

    QUERY_URL = 'https://api.datamarket.azure.com/Bing/Search/v1/News?Query={}'

    def __init__(self, api_key, safe=False, latest_window=7):
        self.api_key = api_key
        self.safe = safe
        self.latest_window = latest_window

    def search(self, query, format='json', **kwargs):
        ''' Returns the result list'''
        return self._search(query, format=format)

    def search_all(self, query, format='json', limit=100, **kwargs):
        ''' Returns a single list containing up to 'limit' Result objects'''
        results = self._search(query, format, **kwargs)
        if not results:
            return results
        current_url = results[-1].url
        prev_url = None
        while len(results) <= limit:
            max = limit - len(results)
            kwargs['$skip'] = len(results)
            more_results = self._search(query, format=format, **kwargs)
            prev_url = current_url
            current_url = more_results[-1].url
            if prev_url == current_url:
                break
            results += more_results
        return results

    def _search(self, query, format='json', **kwargs):
        kwargs['$format'] = "'json'"
        url = self.QUERY_URL.format(urllib2.quote("'{}'".format(query)))
        r = requests.get(url, auth=("", self.api_key), params=kwargs)

        try:
            json_results = r.json()
        except ValueError as vE:
            if not self.safe:
                raise PyBingException("Request returned with code %s, error msg: %s" % (r.status_code, r.text))
            else:
                print "[ERROR] Request returned with code %s, error msg: %s. \nContinuing in 5 seconds." % (r.status_code, r.text)
                time.sleep(5)

        if format == 'json':
            results = json_results['d']['results']
        else:
            results = [Result(single_result_json) for single_result_json in json_results['d']['results']]
        return results

    def search_latest(self, query, format='json', **kwargs):
        before = kwargs.pop('before', None)
        if not before:
            before_date = datetime.date.today() - datetime.timedelta(days=self.latest_window)
        else:
            before_date = dateutil.parser.parse(before).date()

        kwargs['NewsSortBy'] = "'Date'"
        results = []
        current_url = None
        while True:
            kwargs['$skip'] = len(results)
            more_results = self._search(query, format=format, **kwargs)
            for result in more_results:
                current_date = dateutil.parser.parse(result.date).date()
                if current_date < before_date:
                    results.append(result)
            prev_url = current_url
            current_url = more_results[-1].url
            if prev_url == current_url:
                break

        return results

    def get_query_url(self, query, **kwargs):
        url = self.QUERY_URL.format(urllib2.quote("'{}'".format(query)))
        r = Request('GET', url, auth=("", self.api_key), params=kwargs)
        prep = r.prepare()
        return prep.url


class Result(object):
    '''
    The class represents a SINGLE search result.
    Each result will come with the following:

    #For the actual results#
    title: title of the result
    url: the url of the result
    description: description for the result
    id: bing id for the page

    #Meta info#:
    meta.uri: the search uri for bing
    meta.type: for the most part WebResult
    '''

    class _Meta(object):
        '''
        Holds the meta info for the result.
        '''
        def __init__(self, meta):
            self.type = meta['type']
            self.uri = meta['uri']

    def __init__(self, result):
        self.url = result['Url']
        self.title = result['Title']
        self.description = result['Description']
        self.id = result['ID']
        if 'Date' in result:
            self.date = result['Date']

        self.meta = self._Meta(result['__metadata'])
