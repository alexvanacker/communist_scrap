import unittest
import os
import os.path as osp
import shutil
from scrapper import scrapper


class ScraperTest(unittest.TestCase):
    
    def setUp(self):
        tmp_folder = 'test-tmp'
        working_dir = os.getcwd()
        self.tmp_folder_path = osp.join(working_dir, tmp_folder)
        os.mkdir(self.tmp_folder_path)
        
    def tearDown(self):
        shutil.rmtree(self.tmp_folder_path)

    def test_no_article(self):
        url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php?page=article_long&id_article=151143'
        scrapper.write_raw_infos(url, self.tmp_folder_path)
        
    def test_a_faire_shit(self):
        url = 'http://maitron-en-ligne.univ-paris1.fr/spip.php?page=article_long&id_article=124004'
        scrapper.write_raw_infos(url, self.tmp_folder_path)
        


def main():
    unittest.main()

if __name__ == '__main__':
    main()