#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import re
import gzip
import os.path as osp
import os
import nltk
import scrapper
from bs4 import BeautifulSoup
from nltk import word_tokenize

logger = logging.getLogger(__name__)


months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
          'août', 'septembre',
          'octobre', 'novembre', 'décembre']
          
class_id = 'id'
class_category = 'category'
class_name = 'name'
class_article = 'article'
class_sources = 'sources'
class_summary = 'summary'
          
def extract_infos_from_file(filepath):
    ''' Extract infos from given person article

    Returns dict of informations
    filepath -- Path to the person's article HTML file
    '''
    logger.debug('Analyzing file: {}'.format(filepath))
    
    if not osp.exists(filepath):
        logger.error('Could not find article file: {}'.format(filepath))
        raise Exception

    # detect compression
    compress = False
    if filepath.endswith('.gz'):
        compress = True
        
    if compress:
        soup = BeautifulSoup(gzip.open(filepath, 'rb'))
    else:
        soup = BeautifulSoup(open(filepath, 'rb'))

    print soup
    infos = {}

    # Testing encoding
    detected_encoding = soup.original_encoding
    
    # Name extraction    
    infos.update(extract_names_from_soup(soup))

    # Summary analysis
    

    # # First paragraph: extract some data, like birthdate, place, date of death
    # notice = soup.find(class_='notice')
    # first_para = notice.find(class_='chapo')
    # # Take the last paragraph of the notice actually
    # first_para = first_para.find_all('p', recursive=False)[-1]
    # first_para_text = first_para.string
    # if first_para_text is None:
    #     full_contents = ''
    #     # There can be tags instead of strings in contents...
    #     for c in first_para.contents:
    #         try:
    #             full_contents += c
    #         except:
    #             full_contents += c.string
    #     first_para_text = full_contents
    # birth_and_death = extract_info_from_first_para(first_para_text)
    # infos.update(birth_and_death)
    # logger.debug(str(infos))

    return infos


def analyze_summary(soup):
    """ Extracts info from the summary """
    logger.debug("Analyzing summary...")
    summary = soup.find(class_=class_summary)
    print summary
    

def extract_names_from_soup(soup):
    """ Extract name infos from the full article
    """
    logger.debug('Extracting names...')
    name_tag = soup.find(class_=class_name)
    # Make one string only
    full_name = ''.join(name_tag.contents)
    return extract_names_from_string(full_name)


def extract_names_from_string(name_string):
    """ Extract name info from a name string 
    
    last_name: last name known for the person
    birthname: last name given at birth (only for women)
    married_names: last name(s) after marriages
    
    """
    try:
        # Input can already be unicode, so try/except block
        name_string = unicode(name_string, 'utf-8')
    except:
        pass
    names = name_string.split(' ')
    infos = {}
    infos['last_name'] = names[0]
    if len(names) > 1:
        infos['usual_first_name'] = names[1].replace(',', '').replace('.','')
        infos['usual_name_is_in_birthnames'] = 1
        names = names[2::]
        remove_commas = lambda x: x.replace(',','')
        names = map(remove_commas, names)
    
    # Much unicode
    epouse = u'épouse'
    nee = u'née'
    
    if '[' in name_string:
        in_brackets = name_string.split('[')[1]
        names_in_brackets = in_brackets.split(']')[0].replace(',','').split(' ')
        
        max_index = len(names_in_brackets)
        start_index = 1
        if names_in_brackets[-1] == 'dit':
            infos['usual_name_is_in_birthnames'] = 0
            max_index = len(names_in_brackets) - 1

        if names_in_brackets[0].strip() == nee:
            infos['birthname'] = names_in_brackets[1]
            start_index = 2
        
        other_names = []
        for i in xrange(start_index, max_index):
            if names_in_brackets[i] == epouse:
                break
            other_names.append(names_in_brackets[i])    
            
        infos['other_first_names'] = ','.join(other_names)
    elif '(' in name_string:
        # TODO
        pass
    
    else:
        # Every other first name, if any, are
        # separated by commas after the usual first name
        # Example: AUBERT Jeanne, Marie, Lucienne, épouse PICARD
        other_names = []
        for i, name in enumerate(names):
            if epouse in name:
                break
            other_names.append(name)
        
        infos['other_first_names'] = ','.join(other_names)
    
    if nee in name_string:
        married_names = [] 
        married_names.append(infos['last_name'])
    
    if epouse in name_string:
        split = name_string.split(epouse)
        married_names = split[1].strip()
        married_names = married_names.split(u'puis')
        married_names_array = []
        for m in married_names:
            married_names_array.append(m.replace(',','').replace(']','').replace(' ',''))
        infos['married_names'] = ','.join(married_names_array)
        if nee not in name_string:
            infos['birthname'] = infos['last_name']
            
    # pseudos 
    if 'Pseudo' in name_string:
        split = name_string.split('Pseudonyme')
        pseudonym_part = re.sub(r'.*:', '', split[1])
        infos['pseudos'] = pseudonym_part.strip()
            
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