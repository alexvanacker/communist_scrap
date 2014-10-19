#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string
import requests
import time
import re
import cPickle as pickle
from nltk import word_tokenize
import logging
import logging.config
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound


charset = 'iso-8859-1'
parser_lxml = "lxml"
parser_html5 = "html5lib"

# Main url for crawling
search_url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php'

logger = logging.getLogger(__name__)

months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
          'août', 'septembre',
          'octobre', 'novembre', 'décembre']


parser = parser_html5

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

    soup = BeautifulSoup(contents, parser)
    return soup


def test_access_url(url, time_pause_sec=5):
    """ Test if URL is accessible

    If fails, tries again in timeout seconds.
    If a second fail occurs, considers URL not accessible

    url -- URL to test_soup
    time_pause_sec -- Time to wait between two tries in seconds
    """
    r = requests.get(url)
    if r.status_code != requests.codes.ok:
        time.sleep(5)
        r = requests.get(url)
        if r.status_code != requests.codes.ok:
            raise Exception('Error: status code is %s for URL: %s' %
                            (str(r.status_code), url))


def extract_infos(url, soup=None):
    ''' Extract infos from given person url

    Returns dict of informations
    url -- URL for the person's page
    soup -- BeautifulSoup object if already created
    '''

    infos = {}

    if soup is None:
        soup = make_soup(url)

    # Testing encoding
    detected_encoding = soup.original_encoding
    logger.info('Detected encoding: '+str(detected_encoding))

    # In id=header, class=nom-notice : nom/prenoms
    header = soup.find(id='header')
    nom_notice = header.find(class_='nom-notice')
    print str(nom_notice)
    # Make one string only
    full_name = ''.join(map(unicode, nom_notice.contents))

    # Now parse:
    #LAST_NAME First_name [LAST_NAME, first_name_1, ... <em> first_name </em>]
    in_brackets = full_name.split('[')[1]
    # Relace <em>
    in_brackets = in_brackets.replace('<em>', '').replace('</em>', '')
    # And split
    names = map(lambda x: x.replace(',', ''), in_brackets.split(' '))
    # Cleanup: remove empty string
    while '' in names:
        names.remove('')

    # Now get the names, finally
    last_name = names[0]
    other_first_names = []
    for i in range(1, len(names)-1):
        other_first_names.append(names[i])
    first_name = names[-1].replace(']', '')

    infos['last_name'] = last_name
    infos['first_name'] = first_name
    infos['other_first_names'] = ' '.join(other_first_names)

    # First paragraph: extract some data, like birthdate, place, date of death
    notice = soup.find(class_='notice')
    first_para = notice.find(class_='chapo')
    first_para_text = first_para.string
    extract_info_from_first_para(first_para_text)

    logger.debug(str(infos))

    return infos


def extract_info_from_first_para(para_text):
    ''' Returns birthdate, place and death '''

    # Tokenize bitch
    words = word_tokenize(para_text)
    birth_index = -1
    death_index = -1
    for index, word in enumerate(words):
        if word.startswith('Né'):
            birth_index = index
            logger.debug('Detected birth word')

        if 'mort' in word:
            death_index = index
            logger.debug('Detected death word')

    birth_day = None
    birth_month = None
    birth_year = None
    birth_place = None

    one_digit = re.compile('\d{1}')
    four_digits = re.compile('\d{4}')

    for l in range(birth_index, len(words)-1):
        word = words[l]
        if one_digit.match(word):
            birth_day = word
        elif word in months:
            birth_month = word
        elif four_digits.match(word):
            birth_year = word
        elif word == "à":
            birth_place = words[l+1]

    print str(birth_day, birth_month, birth_year, birth_place)


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


def get_all_urls_from_cat(category_param):
    """ Given a category URL param,
    returns the list of urls for all names in it.
    """
    # to get by letter, add parameter: &lettre=^[aA]
    logger.info('Extracting URLs for category parameter: %s',
                category_param)
    cat_urls = []
    for letter in string.lowercase:
        # Make parameter
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
                cat_urls.extend(extract_list_urls_from_list_page(l))
        except:
            logger.error('Could not extract URLs for parameter: %s'
                         'and letter %s' %
                         (category_param, letter))
            raise

    return cat_urls


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
        urls = [l['href'] for l in links]
        return urls
    else:
        # No articles
        return []


def crawl(home_url):
    ''' Returns a dictionary of URLs

    Each URL has a dict to link an epoch, theme, or place
    '''
    final_dict = {}
    cat_dict = get_categories_dict()
    for cat in cat_dict.keys():
        for subcat in cat_dict[cat].keys():
            #TODO: add check on pickle! If exists, then skip!
            urls = get_all_urls_from_cat(cat_dict[cat][subcat])
            logger.info('For %s , number of persons: %s' % (subcat, len(urls)))
            for url in urls:
                if url in final_dict:
                    final_dict[url].append[subcat]
                else:
                    final_dict[url] = [subcat]

            pickle.dump(urls, open('comm_urls_'+subcat+'.p', 'wb'))
