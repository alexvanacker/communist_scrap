#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
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


# Main url for crawling
search_url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php'

logger = logging.getLogger(__name__)

months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
          'août', 'septembre',
          'octobre', 'novembre', 'décembre']


def define_login_password():
    """ Reads from a file the login information
    """
    file_path = 'login.txt'
    logger.debug('Loading login information')
    login_info = {}
    f = open(file_path, 'rb')
    for l in f.readlines():
        if 'login' in l:
            login_info['login'] = l.split('=')[1].strip()
        else:
            login_info['pwd'] = l.split('=')[1].strip()
    return login_info


login_info = define_login_password()
login = login_info['login']
pwd = login_info['pwd']
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

    soup = BeautifulSoup(contents, parser, from_encoding='iso-8859-1')
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
    # logger.info('Detected encoding: '+str(detected_encoding))

    # In id=header, class=nom-notice : nom/prenoms
    header = soup.find(id='header')
    nom_notice = header.find(class_='nom-notice')

    # Make one string only
    full_name = ''.join(map(unicode, nom_notice.contents))

    if '[' in full_name:
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
    else:
        # Handle pseudonyms
        if 'Pseudo' in full_name:
            pseudos_split = full_name.split('Pseudonymes')
            full_name = pseudos_split[0]
            pseudos = pseudos_split[1]
            pseudos = pseudos.split(':')[1].strip()
            pseudos =pseudos.split(',')
            for i, pseudo in enumerate(pseudos):
                infos['pseudo_'+str(i)] = pseudo
            
        names = map(lambda x: x.replace(',', ''), full_name.split(' '))
        last_name = names[0]
        first_name = names[1]
        other_first_names = []
        for i in names[2::]:
            other_first_names.append(i)

    infos['last_name'] = last_name
    infos['first_name'] = first_name
    infos['other_first_names'] = ' '.join(other_first_names)

    # First paragraph: extract some data, like birthdate, place, date of death
    notice = soup.find(class_='notice')
    first_para = notice.find(class_='chapo')
    # Take the last paragraph of the notice actually
    first_para = first_para.find_all('p', recursive=False)[-1]
    first_para_text = first_para.string
    if first_para_text is None:
        full_contents = ''
        # There can be tags instead of strings in contents...
        for c in first_para.contents:
            try:
                full_contents += c
            except:
                full_contents += c.string
        first_para_text = full_contents
    birth_and_death = extract_info_from_first_para(first_para_text)
    infos.update(birth_and_death)
    logger.debug(str(infos))

    return infos


def extract_info_from_first_para(para_text, encoding='utf-8'):
    ''' Returns birthdate, place and death '''

    # Tokenize bitch
    words = word_tokenize(para_text.encode(encoding))
    birth_index = -1
    death_index = -1

    for index, word in enumerate(words):

        if str(word).startswith('Né'):
            birth_index = index
            logger.debug('Detected birth word, index: '+str(birth_index))

            # birth_day = words[birth_index + 2]
            # birth_month = words[birth_index + 3]
            # birth_year = words[birth_index + 4]

        # avoid detecting twice
        if death_index < 0 and 'mort' in word:
            death_index = index
            logger.debug('Detected death word, index: '+str(death_index))

    if birth_index < 0:
        logger.error('Could not extract birth info')
        logger.error(words)
        raise BaseException()

    if death_index < 0:
        logger.error('Could not extract death index')
        logger.error(words)
        raise BaseException()

    # Find birthstuff
    birth_date_set = False
    birth_place_set = False
    for index, word in enumerate(words[birth_index:death_index]):
        # FInd data pattern:
        if not birth_date_set:
            if word == 'le':
                birth_day = words[birth_index+index+1]
                birth_month = words[birth_index+index + 2]
                birth_year = words[birth_index+index + 3]
                birth_date_set = True

        if 'à' == word and not birth_place_set:
            birth_place = words[birth_index+index+1]
            birth_place_set = True

        if birth_place_set and birth_date_set:
            break

    death_date_set = False
    death_place_set = False
    death_place = None
    for index, word in enumerate(words[death_index::]):
        if word == 'le' and not death_date_set:
            death_day = words[death_index + index + 1]
            death_month = words[death_index + index + 2]
            death_year = words[death_index + index + 3]
            death_date_set = True

        if 'à' == word and not death_place_set:
            death_place = words[death_index+index+1]
            death_place_set = True

        if death_date_set and death_place_set:
            # CLeanup, though ugly
            if death_place.lower() == death_place:
                death_place = None
                logger.warn('Did not detect death place')
            break

    dico = {}
    dico['birth_day'] = birth_day
    dico['birth_month'] = birth_month
    dico['birth_year'] = birth_year
    dico['birth_place'] = birth_place
    dico['death_day'] = death_day
    dico['death_month'] = death_month
    dico['death_year'] = death_year
    dico['death_place'] = death_place
    return dico


def get_first_date_from_words(words):
    """ Returns a tuple day, month, year detected in an array of words

    """
    for index, word in enumerate(words):
        # FInd data pattern:
        if word == 'le':
            birth_day = words[index+1]
            birth_month = words[index + 2]
            birth_year = words[index + 3]
            return (birth_day, birth_month, birth_year)


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


def scrap_article_id(article_id):
    full_url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php?page=article_long&id_article='
    full_url = full_url + article_id
    scrap_url(full_url)


def scrap_url(url):
    """ Main scrapping call

    Tries to access an URL for a person.
    If it has the information, scrap it. Otherwise,
    we need to follow the real link and login.
    """
    
    logger.debug('Scrapping URL: {}'.format(url))
    s = requests.session()
    r = s.get(url)
    soup = BeautifulSoup(r.content, parser, from_encoding='iso-8859-1')
    
    # Detect if login is required:
    login_code = soup.find(id='var_login')
    
    if login_code is not None:
        logger.info('Login needed, posting login information...')
        
        # Note: detect the formulaire_action_args
        # and all other inputs for the form. 
        # only inputs from the FORM (not the search stuff)
        
        login_form = soup.find(id='formulaire_login')
        login_inputs = login_form.find_all('input')
        
        inputs_dict = {}
        for input_ in login_inputs:
            if input_.has_attr('name'):
                inputs_dict[input_['name']] = input_['value']
        
        # OVerwrite with our login info
        inputs_dict['var_login'] = login
        inputs_dict['password'] = pwd
        
        r = s.post(url, data=inputs_dict)
        soup = BeautifulSoup(r.content, parser, from_encoding='iso-8859-1')
        login_code = soup.find(id='var_login')
        if login_code is not None:
            logger.error('Login failed, check the login information in : {}'.format(inputs_dict))
            
        else:
            logger.debug('Login success')
            
            
    # Now analyze the soup
    extract_raw_text(url, soup)
    
def extract_raw_text(url, soup=None):
    """ Extract raw content from the URL 
    
    This include:
     - title
     - summary
     - contents
     - sources
     - works
     
    Formatting is kept for post analysis (links to other articles, etc.)
    Note: function that writes this data should use encode('utf-8')
    
    """
    
    title_class = "nom-notice"
    title = soup.find(class_=title_class)
    raw_infos = {}
    raw_infos['title'] = title.contents[0].replace(u'\xa0', ' ')
    
    notice = soup.find(class_="notice")
    summary = notice.find(class_="chapo")
    first_para = summary.find_all('p', recursive=False)[-1]
    
    raw_infos['summary'] = first_para

    article = notice.find(class_='texte')
    raw_infos['article'] = article
    
    sources = notice.find(class_='sources')
    raw_infos['sources'] = sources
    
    works = notice.find(class_='oeuvres')
    raw_infos['works'] = works
    
    # In function that writes, encode everything to bytes! .encode('utf-8')
    return raw_infos
    
    
    
    
    
        
    

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

                pickle.dump(urls, open('comm_urls_'+subcat+'.p', 'wb'))

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
                print url
                article_split = url.split('article')
                and_split = article_split[1].split('&')
                article_id = and_split[0]
                print article_id
                break
