#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import os
import os.path as osp
import shutil
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound

from scrapper import analyzer


class AnalyzerTest(unittest.TestCase):
    
    def setUp(self):
        tmp_folder = 'test-tmp'
        working_dir = os.getcwd()
        self.tmp_folder_path = osp.join(working_dir, tmp_folder)
        os.mkdir(self.tmp_folder_path)
        
    def tearDown(self):
        shutil.rmtree(self.tmp_folder_path)

    def test_name_simple(self):
        name_string = 'DUPONT Marcel [DUPONT Albert, Marcel, Félix]'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('DUPONT', infos['last_name'])
        self.assertEquals('Marcel', infos['usual_first_name'])
        self.assertEquals('Albert,Marcel,Félix', infos['other_first_names'])
         
    def test_name_different_usual_name(self):
        name_string = 'DURAND Jacques [DURAND Michel, Georges, dit]'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('Michel,Georges', infos['other_first_names'])
        
    def test_name_married_woman(self):
        name_string = 'AUBERT Jeanne, Marie, Lucienne, épouse PICARD'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('AUBERT', infos['last_name'])
        self.assertEquals('Jeanne', infos['usual_first_name'])
        self.assertEquals('PICARD', infos['married_names'])
        self.assertEquals('Marie,Lucienne', infos['other_first_names'])
        
    def test_name_married_woman_birthname_first(self):
        name_string = 'DUVAL Marie [DUVAL Germaine, Marie], épouse THOMAS'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('DUVAL', infos['last_name'])
        self.assertEquals('DUVAL', infos['birthname'])
        self.assertEquals('THOMAS', infos['married_names'])
        self.assertEquals('Germaine,Marie', infos['other_first_names'])
        
        
    

def main():
    unittest.main()

if __name__ == '__main__':
    main()