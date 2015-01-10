#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path as osp
import string
import requests
import time
import datetime
import cPickle as pickle
import nltk
from nltk import word_tokenize
import logging
import logging.config
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound
from multiprocessing.dummy import Pool as ThreadPool

# Max number of concurrent accesses to the server
nb_threads = 5

charset = 'iso-8859-1'
parser_lxml = "lxml"
parser_html5 = "html5lib"


# Main url for crawling
search_url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php'

logger = logging.getLogger(__name__)

months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
          'août', 'septembre',
          'octobre', 'novembre', 'décembre']
          

# Global session object
session = requests.session()
    
          
          
def scrap_all_articles(dict_file, articles_folder):
    """ Will scrap all URLs from the pickle file found in the URL folder.
    
    dict_file -- Path to pickel file containing the URL dictionary
    
    """

    start = time.time()

    # Read the URLs
    urls = pickle.load(open(dict_file, 'rb'))
    logger.debug('Number of URLs: {}'.format(str(len(urls))))
    for url in urls:
        categories = map(unicode, urls[url])
        # Extract article ID
        article_id = url.split('.php?')[1].split('&')[0].replace('article','')
        real_url = get_full_url(article_id)
        write_raw_infos(real_url, articles_folder, categories=categories)

    end = time.time()
    total_time_sec = end - start
    total_time_delta = datetime.timedelta(seconds=total_time_sec)
    logger.debug('Scrapping total time: {}'.format(str(total_time_delta)))
    
    
def write_article(short_url, target_folder):
    """ Scraps an article then writes a simplified version
    
    short_url -- URL containing the article id
    target_folder -- Where to write the file 
    """
    # Extract article ID
    article_id = short_url.split('.php?')[1].split('&')[0].replace('article','')
    
    real_url = get_full_url(article_id)
    write_raw_infos(real_url, target_folder)
    

def get_full_url(article_id):
    """ Returns URL for full article """
    full_url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php?page=article_long&id_article='
    full_url = full_url + article_id
    return full_url


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


def get_soup(url):
    """ Main scrapping call

    Tries to access an URL for a person.
    Logins if fails to access on first attempt.
    """
    
    logger.debug('Scrapping URL: {}'.format(url))
    r = session.get(url)
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
        
        r = session.post(url, data=inputs_dict)
        soup = BeautifulSoup(r.content, parser, from_encoding='iso-8859-1')
        login_code = soup.find(id='var_login')
        if login_code is not None:
            logger.error('Login failed, check the login information in : {}'.format(inputs_dict))
            
        else:
            logger.debug('Login success')
            
            
    # Now return the soup
    return soup
    
def extract_raw_text(soup):
    """ Extract raw content from the BeautifulSoup object 
    
    This include:
     - name
     - summary
     - contents
     - sources
     - works
     
    Formatting is kept for post analysis (links to other articles, etc.), but everything
    is sent as unicode (not string bytes).
    Classes are renamed as above for easier post analysis.
    """
    
    title_class = "nom-notice"
    title = soup.find(class_=title_class)
    raw_infos = {}
    raw_infos['name'] = title.contents[0].replace(u'\xa0', ' ')
    
    notice = soup.find(class_="notice")
    summary = notice.find(class_="chapo")
    if summary is not None:
        first_para = summary.find_all('p', recursive=False)[-1]
        first_para.tag = 'div'
        first_para['class'] = 'summary'
        raw_infos['summary'] = unicode(first_para)
        
    else:
        raw_infos['summary'] = unicode('')

    article = notice.find(class_='texte')
    if article is not None:
        article['class'] = 'article'
    raw_infos['article'] = unicode(article)
    
    sources = notice.find(class_='sources')
    raw_infos['sources'] = unicode(sources)
    
    works = notice.find(class_='oeuvres')
    if works is not None:
        works['class'] = 'works'
    raw_infos['works'] = unicode(works)
    
    # In function that writes, encode everything to bytes! .encode('utf-8')
    return raw_infos
    
    
def write_raw_infos(url, target_folder, categories=None):
    """ Writes raw info an html file, named after the 
    raw info name (spaces replaced by underscores).
    
    The file will have the following format:
    <div class='name'>
    <div class='summary'>
    <div class='article'>
    <div class='works'>
    <div class='sources'>
    
    The header will contain a div will class 'id' for reference.
    
    url -- URL from which to scrap the data
    target_folder -- Folder in which the html file will be placed
    categories -- Website category list (era, ...)
    
    """
    if categories is None or len(categories) == 0:
        logger.debug('No categories found.')
        categories = []
        
    if not osp.exists(target_folder):
        # Create it
        os.mkdir(target_folder)
        
    # Extract id
    article_id = url.split('id_article=')[1]
    
    soup = get_soup(url)
    raw_infos = extract_raw_text(soup)
    name = raw_infos['name']
    # Remove pseudonym part
    name = name.split('Pseudo')[0].replace('.','').strip()
    name = name.replace(',','').replace(' ','_')
    file_path = osp.join(target_folder, name)

    if osp.exists(file_path):
        logger.debug('File already exists: '+file_path)
        
    f = open(file_path, 'wb')
    
    html_code = """
    <html>
        <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        </head>
        <body>
    """
    html_code += '<div class="id">'
    html_code += article_id
    html_code += '</div>'
    html_code += '\r\n'
    
    for category in categories:
        html_code += '<div class="category">'
        html_code += category
        html_code += '</div>'
        html_code += '\r\n'
    
    
    html_code += '<div class="name">'
    html_code += raw_infos['name']
    html_code += '</div>'
    html_code += '\r\n'
    
    # For article, sources, works, and summary
    # there are already divs in the raw_infos
    
    html_code += raw_infos['summary']
    html_code += '\r\n'
    
    html_code += raw_infos['article']
    html_code += '\r\n'
    

    if raw_infos['sources'] is not None:
        html_code += raw_infos['sources']
        html_code += '\r\n'

    
    if raw_infos['works'] is not None:
        html_code += raw_infos['works']
        html_code += '\r\n'
    
    html_code += """
    </body>
    </html>
    """
    
    f.write(html_code.encode('utf-8'))
    f.close()