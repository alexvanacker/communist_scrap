#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path as osp
import string
import requests
import time
import cPickle as pickle
import nltk
from nltk import word_tokenize
import logging
import logging.config
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound
from multiprocessing.dummy import Pool as ThreadPool

# Max number of concurrent accesses to the server
concurrent_limit = 5

charset = 'iso-8859-1'
parser_lxml = "lxml"
parser_html5 = "html5lib"
parser = parser_html5

# Main url for crawling
search_url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php'


logger = logging.getLogger(__name__)

try:
    test_soup = BeautifulSoup('<html></html>', parser)
    logger.info('Using parser : ' + parser)
except FeatureNotFound:
    logger.info(parser + ' not found, switching to '+parser_html5)
    parser = parser_lxml
    try:
        test_soup = BeautifulSoup('<html></html>', parser)
    except:
        logger.error('Could not instantiate parser')
        raise
    
def make_soup(url, params=None):
    """Get soup object from url """

    r = requests.get(url, params=params)
    if r.status_code != requests.codes.ok:
        raise Exception('Error: status code is %s for URL: %s' %
                        (str(r.status_code), url))

    contents = r.content
    
    soup = BeautifulSoup(contents, parser, from_encoding='iso-8859-1')
    return soup


def get_categories_dict():
    ''' Returns dictionary linking categories to their URL params'''

    # Will contain a dict of the form:
    # Type -> {display -> URL}
    types_dicos = {}
    # Links are in the sidebar
    home_url = 'http://maitron-en-ligne.univ-paris1.fr'
    soup = make_soup(home_url)
    nav = soup.find(class_='nav')

    # Types of navigations: Eras/Dicos/Themes
    types = nav.find_all('li', recursive=False)

    for t in types:
        type_title = t.contents[0].strip()
        list_items = t.find_all('li')
        types_dicos[type_title] = {}
        for item in list_items:
            link = item.a['href'].replace('spip.php?', '')
            item_name = item.string
            types_dicos[type_title][item_name] = link

    return types_dicos
    

def get_all_pages_from_letter_page(page_url):
    """ Returns list of URLs for all the pages
    for the given letter URL.
    """
    soup = make_soup(page_url)

    debut_articles_values = []
    # Get all page URLs, paginated by 30
    # FInd the last page first:
    all_pages_links = soup.find_all(class_='lien_pagination')
    if len(all_pages_links) > 0:
        last_page_url = all_pages_links[-1]['href']
        split = last_page_url.split('articles=')
        last_page = split[1].split('#')[0]
        start = 0
        last_page_int = int(last_page)
        all_nbr = range(start, last_page_int + 1)
        url_start = page_url + '&debut_articles='
        debut_articles_values.extend([url_start+str(x) for x in all_nbr[::30]])
        return debut_articles_values
    else:
        # No pages, only one, which we return
        return [page_url]


def extract_list_urls_from_list_page(page_url):
    """ Extracts URLs from a page with a list of URLs

    page_url -- URL of the page with the list of links
    """
    soup = make_soup(page_url)
    list_articles = soup.find(class_='liste-articles')
    if list_articles is not None:
        list_ul = list_articles.ul
        links = list_ul.find_all('a')
        try:
            # Yeah, because it's always nice to find <a> tags without
            # hrefs...
            urls = [l['href'] for l in links if 'href' in l.attrs.keys()]
            return urls
        except:
            logger.error('Error getting href from %s', page_url)
            raise
    else:
        # No articles
        return []


def get_letter_urls(letter, category_param):
    """ Returns list of URLs for a given letter and category parameter

    letter -- letter in lowercase
    category_param -- URL parameter for a category
    """
    # Make parameter
    letter_urls = []
    upper = letter.upper()
    param = '^['+letter+upper+']'
    letter_url = ''.join([search_url,
                          '?',
                          category_param,
                          '&',
                          'lettre=',
                          param])
    logger.debug('Letter url: %s', letter_url)
    try:
        all_letter_pages = get_all_pages_from_letter_page(letter_url)
        for l in all_letter_pages:
            letter_urls.extend(extract_list_urls_from_list_page(l))

        return letter_urls

    except:
        logger.error('Could not extract URLs for parameter: %s'
                     ' and letter: %s' %
                     (category_param, letter))
        raise



def get_all_urls_from_cat_multithread(category_param,
                                      nb_threads=concurrent_limit):
    """ Given a category URL param,
    returns the list of urls for all names in it.
    """
    # to get by letter, add parameter: &lettre=^[aA]
    logger.info('Extracting URLs for category parameter: %s',
                category_param)

    letters = string.lowercase
    pool = ThreadPool(nb_threads)
    try:
        # Lambda function for multiprocessing
        get_url_func = lambda x: get_letter_urls(x, category_param)
        results = pool.map(get_url_func, letters)
        pool.close()
        pool.join()
        # Results is a list of lists, make only one list
        urls = [url for l in results for url in l]
        return urls
    except KeyboardInterrupt:
        pool.terminate()
        
    
def crawl(home_url):
    ''' Returns a dictionary of URLs

    Each URL has a dict to link an epoch, theme, or place
    '''
    final_dict = {}
    cat_dict = get_categories_dict()
    for cat in cat_dict.keys():
        for subcat in cat_dict[cat].keys():
            pickle_file = 'comm_urls_'+subcat+'.p'
            if os.path.exists(pickle_file):
                logger.info('Already extracted %s, skipping', subcat)
            else:
                urls = get_all_urls_from_cat_multithread(cat_dict[cat][subcat])
                logger.info('For %s , number of persons: %s' %
                            (subcat, str(len(urls))))
                for url in urls:
                    if url in final_dict:
                        final_dict[url].append[subcat]
                    else:
                        final_dict[url] = [subcat]

                pickle.dump(urls, open(pickle_file, 'wb'))

    # Read the pickled files
    working_directory = os.getcwd()
    for f in os.listdir(working_directory):
        if f.endswith('.p'):
            # Name of category is file name, cleaned up
            cat_name = f.replace('comm_urls_', '').replace('.p', '')
            cat_name = unicode(cat_name, 'utf-8')
            logger.info('Processing category: '+cat_name)
            # Try opening the pickle file
            full_path = os.path.join(working_directory, f)
            urls = pickle.load(open(full_path))
            for url in urls:
                # print url
                article_split = url.split('article')
                and_split = article_split[1].split('&')
                article_id = and_split[0]
                # print article_id
                break
