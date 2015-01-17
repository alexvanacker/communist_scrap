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
        
    def test_name_married_husband_name_first(self):
        name_string = 'DURAND Thérèse [née VIDAL Solange, Thérèse, Marguerite]'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('VIDAL', infos['birthname'])
        self.assertEquals('Solange,Thérèse,Marguerite', infos['other_first_names'])
        
    def test_name_multiple_mariages(self):
        name_string = 'MARTIN Simone, épouse TOUSSAINT, puis FABRE'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('MARTIN', infos['last_name'])
        self.assertEquals('MARTIN', infos['birthname'])
        self.assertEquals('Simone', infos['usual_first_name'])
        self.assertEquals('TOUSSAINT,FABRE', infos['married_names'])
        
    def test_another_woman_case(self):
        name_string = 'THIBAULT Jacqueline [née VIDAL Jacqueline, Suzanne, épouse THIBAULT, puis TOUSSAINT]'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('THIBAULT', infos['last_name'])
        self.assertEquals('VIDAL', infos['birthname'])
        self.assertEquals('THIBAULT,TOUSSAINT', infos['married_names'])
        self.assertEquals('Jacqueline,Suzanne', infos['other_first_names'])
        
        
    def test_name_pseudo(self):
        name_string = 'MARTIN Jean. Pseudonyme dans la Résistance : DESCHAMPS Luc'
        infos = analyzer.extract_names_from_string(name_string)
        self.assertEquals('MARTIN', infos['last_name'])
        self.assertEquals('Jean', infos['usual_first_name'])
        self.assertEquals('DESCHAMPS Luc', infos['pseudos'])
    

def main():
    unittest.main()

if __name__ == '__main__':
    main()