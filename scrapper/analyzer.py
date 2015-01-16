#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
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
    
    nom_notice = soup.find(class_=class_name)

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
    
    print str(infos)


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


def extract_names_from_soup(soup):
    """ Extract name infos from the full article
    """
    logger.debug('Extracting names...')
    name_tag = soup.find(class_=class_name)
    # Make one string only
    full_name = ''.join(map(unicode, name_tag.contents))
    return extract_names_from_string(full_name)


def extract_names_from_string(name_string):
    """ Extract name info from a name string 
    
    
    
    """
    names = name_string.split(' ')
    infos = {}
    infos['last_name'] = names[0]
    infos['usual_first_name'] = names[1].replace(',', '')
    infos['usual_name_is_in_birthnames'] = 1
    names = names[2::]
    remove_commas = lambda x: x.replace(',','')
    names = map(remove_commas, names)
    
    # DURAND Jacques [DURAND Michel, Georges, dit]. 
    if '[' in name_string:
        in_brackets = name_string.split('[')[1]
        names_in_brackets = in_brackets.replace(']','').replace(',','').split(' ')
        
        max_index = len(names_in_brackets)
        if names_in_brackets[-1] == 'dit':
            infos['usual_name_is_in_birthnames'] = 0
            max_index = len(names_in_brackets) - 1
        
        assert names_in_brackets[0] == infos['last_name']
        
        other_names = []
        for i in xrange(1, max_index):
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
            if 'épouse' in name:
                break
            other_names.append(name)
        
        infos['other_first_names'] = ','.join(other_names)
        
    if 'épouse' in name_string:
        split = name_string.split('épouse')
        married_name = split[1].strip()
        infos['married_names'] = married_name
        
        
        
            
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