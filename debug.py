import logging
from scrapper import scrapper

logging.basicConfig(level=logging.DEBUG)


test_urls = ['http://maitron-en-ligne.univ-paris1.fr/spip.php?article16337',
             'http://maitron-en-ligne.univ-paris1.fr/spip.php?article23962']


def debug_infos():
    for url in test_urls:
        scrapper.extract_infos(url)


def test_get_cat():
    scrapper.get_categories_dict()


def test_crawl():
    url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php?mot23'
    scrapper.extract_all_names_from_letter(url)


if __name__ == '__main__':
    test_crawl()
    
