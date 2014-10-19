import logging
from scrapper import scrapper

import os
import json
import logging.config


def setup_logging(
    default_path='logging.json',
    default_level=logging.DEBUG,
    env_key='LOG_CFG'
):
    """Setup logging configuration

    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)

setup_logging()



test_urls = ['http://maitron-en-ligne.univ-paris1.fr/spip.php?article16337',
             'http://maitron-en-ligne.univ-paris1.fr/spip.php?article23962']


def debug_infos():
    for url in test_urls:
        scrapper.extract_infos(url)


def test_get_cat():
    scrapper.get_categories_dict()


def test_crawl():
    scrapper.crawl('http://maitron-en-ligne.univ-paris1.fr')
    # url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php?mot23&lettre=^[aA]'
    # cat_param = 'mot23'
    # print scrapper.get_all_urls_from_cat(cat_param)


if __name__ == '__main__':
    test_crawl()
