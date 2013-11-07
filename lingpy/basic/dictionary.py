# author   : Peter Bouda
# email    : pbouda@cidles.eu
# created  : 2013-06-06 11:57
"""
This module provides a basic class for the handling of dictionaries.

"""

__author__="Peter Bouda"
__date__="2013-07-22"

import os
import sys
from datetime import date,datetime
import numpy as np
import pickle
import codecs
import re
from operator import itemgetter
import abc

# basic lingpy imports
from ._parser import _QLCParser
from ..read.qlc import read_qlc
from ..settings import rcParams

# try:
#     from nltk.stem.snowball import SpanishStemmer
# except ImportError:
#    print(rcParams['W_missing_module'].format("nltk"))

# import tokenizer
from ..sequence.tokenizer import Tokenizer


class Dictionary(_QLCParser):
    """
    Basic class for the handling of multilingual word lists.

    Parameters
    ----------
    filename : { string dict }
        The input file that contains the data. Otherwise a dictionary with
        consecutive integers as keys and lists as values with the key 0
        specifying the header.

    row : str (default = "head")
        A string indicating the name of the row that shall be taken as the
        basis for the tabular representation of the dictionary.
    
    col : str (default = "translation")
        A string indicating the name of the column that shall be taken as the
        basis for the tabular representation of the dictionary.

    conf : string (default='')
        A string defining the path to the configuration file. 

    Notes
    -----
    A dictionary is created from a CSV file containing the data. Two keywords
    (head and translation) define, which of the dimensions of the original data
    should be used as heads and as translations of the dictionary content. A
    configuration file can be used to change basic names and aliases for the
    data being used, and the classes (data types) of the entries.

    """

    def __init__(
            self,
            filename,
            row='head',
            col='translation',
            conf = ''
            ):

        # set up basic path for configuration file
        if not conf:
            conf = os.path.join(rcParams['_path'],'data','conf','dictionary.rc')

        # initialize the qlc_parser
        _QLCParser.__init__(self,filename,conf)

        # build a doculect->iso map for @doculect meta data
        self.doculect2iso = {}
        # do we have more than one doculect in the header?
        if type(self._meta["doculect"]) is list:
            for doculect in self._meta["doculect"]:
                doculect_entry = re.split(", ?", doculect)
                self.doculect2iso[doculect_entry[0]] = doculect_entry[1]
        else:
            doculect_entry = self._meta["doculect"]
            self.doculect2iso[doculect_entry[0]] = doculect_entry[1]

        # save ISO for heads and translations in list
        self.head_iso = []
        if type(self._meta["head_iso"]) is list:
            for iso in self._meta["head_iso"]:
                self.head_iso.append(iso)
        else:
            self.head_iso.append(self._meta["head_iso"])

        self.translation_iso = []
        if type(self._meta["translation_iso"]) is list:
            for iso in self._meta["translation_iso"]:
                self.translation_iso.append(iso)
        else:
            self.translation_iso.append(self._meta["translation_iso"])

    def get_tuples(self, columns = [ "head", "translation"]):
        """
        Return tuples from all entries for the given columns.

        Parameters
        ----------
        columns : list
            A list of the column names to extract from each entry.

        Returns
        -------
        entries : list
            A list of all the extracted columns. If there are more than
            one columns then each entry is a tuple. If there is only one column
            then each entry is a string.

        """

        # get the indices
        idxs = []
        for entry in columns:
            if entry in self._header:
                idxs.append(self._header[entry])

        entries = []
        if len(idxs) == 1:
            for row in self._data.values():
                entries.append(row[idxs[0]])
        elif len(idxs) > 1:
            mygetter = itemgetter(*idxs)
            for row in self._data.values():
                entries.append(tuple(mygetter(row)))

        return entries

    def add_entries(
            self,
            entry,
            source,
            function,
            override = False,
            **keywords
            ):
        """
        Add new entry-types to the dictionary by modifying given ones.

        Parameters
        ----------
        entry : string
            A string specifying the name of the new entry-type to be added to the
            dictionary.

        source : string
            A string specifying the basic entry-type that shall be modified. If
            multiple entry-types shall be used to create a new entry, they
            should be passed in a simple string separated by a comma.

        function : function
            A function which is used to convert the source into the target
            value.

        keywords : {dict}
            A dictionary of keywords that are passed as parameters to the
            function.

        Notes
        -----
        This method can be used to add new entry-types to the data by
        converting given ones. There are a lot of possibilities for adding new
        entries, but the most basic procedure is to use an existing entry-type
        and to modify it with help of a function.

        """
        # check for emtpy entries etc.
        if not entry:
            print("[i] Entry was not properly specified!")
            return
        
        # check for override stuff, this causes otherwise an error message
        if entry not in self.header and override:
            return self.add_entries(entry,source,function,override=False)

        # check whether the stuff is already there
        if entry in self._header and not override:
            print(
                    "[?] Datatype <{entry}> has already been produced, ".format(entry=entry),
                    end = ''
                    )
            answer = input("do you want to override? (y/n) ")
            if answer.lower() in ['y','yes','j']:
                keywords['override'] = True
                self.add_entries(entry,source,function,**keywords)
            else:
                print("[i] ...aborting...")
                return
        elif not override:

            # get the new index into the header
            # add a new alias if this is not specified
            if entry.lower() not in self._alias2:
                self._alias2[entry.lower()] = [entry.lower(),entry.upper()]
                self._alias[entry.lower()] = entry.lower()
                self._alias[entry.upper()] = entry.lower()

            # get the true value
            name = self._alias[entry.lower()]

            # get the new index
            newIdx = max(self._header.values()) + 1
            
            # change the aliassed header for each entry in alias2
            for a in self._alias2[name]:
                self._header[a] = newIdx

            self.header[name] = self._header[name]

            # modify the entries attribute
            self.entries = sorted(set(self.entries + [entry]))
            
            # check for multiple entries (separated by comma)
            if ',' in source:
                sources = source.split(',')
                idxs = [self._header[s] for s in sources]

                # iterate over the data and create the new entry
                for key in self:

                    # get the id line
                    s = self[key]

                    # transform according to the function
                    t = function(s,idxs)

                    # add the stuff to the dictionary
                    self[key].append(t)

            # if the source is a dictionary, this dictionary will be directly added to the
            # original data-storage of the dictionary
            elif type(source) == dict:
                
                for key in self:
                    s = source[key]
                    t = function(s)
                    self[key].append(t)
            
            else:
                # get the index of the source in self
                idx = self._header[source]            

                # iterate over the data and create the new entry
                for key in self:
                    
                    # get the source
                    s = self[key][idx]

                    # transform s
                    t = function(s,**keywords)

                    # add
                    self[key].append(t)
        
        elif override:

            # get the index that shall be replaced
            rIdx = self._header[entry.lower()]
            
            # check for multiple entries (separated by comma)
            if ',' in source:
                sources = source.split(',')
                idxs = [self._header[s] for s in sources]

                # iterate over the data and create the new entry
                for key in self:

                    # get the id line
                    s = self[key]

                    # transform according to the function
                    t = function(s,idxs)

                    # add the stuff to the dictionary
                    self[key][rIdx] = t

            # if the source is a dictionary, this dictionary will be directly added to the
            # original data-storage of the wordlist
            elif type(source) == dict:
                
                for key in self:
                    s = source[key]
                    t = function(s)
                    self[key][rIdx] = t

            else:
                # get the index of the source in self
                idx = self._header[source]            

                # iterate over the data and create the new entry
                for key in self:
                    
                    # get the source
                    s = self[key][idx]

                    # transform s
                    t = function(s,**keywords)

                    # add
                    self[key][rIdx] = t

    def tokenize(
            self,
            orthography_profile = '',
            source = "head",
            target = "tokens",
            conversion = 'graphemes',
            ** keywords
            ):
        """
        Tokenize the data with help of orthography profiles.
        
        Parameters
        ----------
        ortho_profile : str (default='')
            Path to the orthographic profile used to convert and tokenize the 
            input data into IPA tokens.
        
        source : str (default="translation")
            The source data that shall be used for the tokenization procedures.
        
        target : str (default="tokens")
            The name of the target column that will be added to the wordlist.

        conversion : str (default="graphemes")
            Tokenization target.


        Notes
        -----
        This is a shortcut to the extended
        :py:class:`~lingpy.basic.wordlist.Wordlist` class that loads data and
        automatically tokenizes it.
        
        """

        t = Tokenizer(orthography_profile)

        # else just return a Unicode grapheme clusters parse
        if target == 'tokens':
            function = lambda x: t.tokenize(x).split(' ')
        else:
            function = lambda x: t.tokenize(x)

        self.add_entries(
            target,
            source,
            function
            )
