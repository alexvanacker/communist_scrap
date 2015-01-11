#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path as osp
import string
import requests
import time
import datetime
import cPickle as pickle
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

# Where to store ignored URLs
ignored_file = '/home/ubuntu/workspace/failed.txt'

# Main url for crawling
search_url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php'

logger = logging.getLogger(__name__)

# Global session object
session = requests.session()

          
def scrap_all_articles(dict_file, articles_folder):
    """ Will scrap all URLs from the pickle file found in the URL folder.
    
    dict_file -- Path to pickel file containing the URL dictionary
    
    """

    start = time.time()

    # Read the URLs
    urls = pickle.load(open(dict_file, 'rb'))
    nb_urls = len(urls)
    logger.debug('Number of URLs: {}'.format(str(nb_urls)))
    
    count = 0
    for url in urls:
        count += 1
        categories = map(unicode, urls[url])
        # Extract article ID
        article_id = url.split('.php?')[1].split('&')[0].replace('article','')
        real_url = get_full_url(article_id)
        write_raw_infos(real_url, articles_folder, categories=categories)
        
        if count % 1000 == 0: 
            logger.info('Processed: {}'.format(str(count)))

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
    test_soup = BeautifulSoup('<html></html>', parser_html5)
    logger.info('Using parser : ' + parser)
except FeatureNotFound:
    logger.info(parser + ' not found, switching to '+parser_lxml)
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


def detect_login(soup):
    """ Returns true if there is a login form in the soup """
    
    main = soup.find(id='main')
    notice = main.find(class_='notice')
    for c in notice.children:
        if c.name == 'div':
            if c.has_attr('class') and 'formulaire_login' in c['class']:
                return True
    
    return False
    
def save_url_to_file(url, filepath):
    """ Appends URL to given file """
    with open(filepath, 'ab') as f:
        f.write(url+'\r\n')

def is_format_wrong(soup):
    """ Returns true if we find the tag <a faire>"""
    a = soup.find('a')
    if a.has_attr('faire'):
        return True
    return False

def get_soup(url):
    """ Main scrapping call

    Tries to access an URL for a person.
    Logins if fails to access on first attempt.
    Returns None if the page is not well formatted.
    """
    
    logger.debug('Scrapping URL: {}'.format(url))
    r = session.get(url)
    soup = BeautifulSoup(r.content, parser, from_encoding='iso-8859-1')
    
    # Detect if login is required:
    if detect_login(soup):
        logger.info('Login needed, posting login information...')
        
        # Note: detect the formulaire_action_args
        # and all other inputs for the form. 
        # only inputs from the FORM (not the search stuff)
        
        main = soup.find(id='main')
        notice = main.find(class_='notice')
        a = notice.find('a')
        
        # Detect fucked up pages, save for later
        if a.has_attr('faire'):
            logger.debug('Ignoring URL, formatting errors with a faire')
            save_url_to_file(url, ignored_file)
            return None     
        
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
        if detect_login(soup):
            logger.error('Login failed, check the login information in : {}'.format(inputs_dict))
            raise Exception
            
        else:
            logger.debug('Login success')
            
    # Now return the soup
    return soup
    

def extract_raw_text(soup, url):
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
    
    # Ignore wrong formats
    if is_format_wrong(notice):
        save_url_to_file(url, ignored_file)
        return None
        
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
    if soup is not None:
        raw_infos = extract_raw_text(soup, url)
        if raw_infos is not None:
            name = raw_infos['name']
            # Remove pseudonym part
            name = name.split('Pseudo')[0].replace('.','').strip()
            name = name.replace(',','').replace(' ','_')
            file_path = osp.join(target_folder, name)
        
            if osp.exists(file_path):
                logger.debug('File already exists: ' + file_path)
                # TODO: add option for overwriting (updates)
                return
                
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