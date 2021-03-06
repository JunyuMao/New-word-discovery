#coding=utf-8

"""
Chinese word segmentation algorithm without corpus
"""
import math
import re
import codecs
import pandas as pd
from probability import entropyOfList
from sequence import genSubparts, genSubstr
from position import posrecord, pwprobability
from config import Hyperparamters as hp

def extract_newword(words,dictionary):
    """
    extract new word.
    """
    new_words = []
    for i in words:
        if i not in dictionary:
            new_words.append(i)
    return new_words

def indexOfSortedSuffix(doc, max_word_len):
    """
    Treat a suffix as an index where the suffix begins.
    Then sort these indexes by the suffixes.
    """
    indexes = []
    length = len(doc)
    for i in range(0, length):
        for j in range(i + 1, min(i + 1 + max_word_len, length + 1)):
            indexes.append((i, j))
    return sorted(indexes, key=lambda i_j: doc[i_j[0]:i_j[1]])


class WordInfo(object):
    """
    Store information of each word, including its freqency, left neighbors and right neighbors
    """
    def __init__(self, text):
        super(WordInfo, self).__init__()
        self.text = text
        self.freq = 0.0
        self.left = []
        self.right = []
        self.aggregation = 0

    def update(self, left, right):
        """
        Increase frequency of this word, then append left/right neighbors
        @param left a single character on the left side of this word
        @param right as left is, but on the right side
        """
        self.freq += 1
        if left: self.left.append(left)
        if right: self.right.append(right)

    def compute(self, length):
        """
        Compute frequency and entropy of this word
        @param length length of the document for training to get words
        """
        self.freq /= length
        self.left = entropyOfList(self.left)
        self.right = entropyOfList(self.right)

    def computeAggregation(self, words_dict):
        """
        Compute aggregation of this word
        @param words_dict frequency dict of all candidate words
        """
        parts = genSubparts(self.text)
        if len(parts) > 0:
            self.aggregation = min([self.freq/words_dict[p1_p2[0]].freq/words_dict[p1_p2[1]].freq for p1_p2 in parts])
            self.aggregation = math.log(self.aggregation,2)/len(self.text)


class WordSegment(object):

    """
    Main class for Chinese word segmentation
    1. Generate words from a long enough document
    2. Do the segmentation work with the document
    """

    # if a word is combination of other shorter words, then treat it as a long word
    L = 0
    # if a word is combination of other shorter words, then treat it as the set of shortest words
    S = 1
    # if a word contains other shorter words, then return all possible results
    ALL = 2

    def __init__(self, doc, max_word_len=5, min_entropy=2, min_aggregation=1.5):
        super(WordSegment, self).__init__()
        self.max_word_len = max_word_len
        self.min_entropy = min_entropy
        self.min_aggregation = min_aggregation
        self.word_infos = self.genWords(doc)
        # Result infomations, i.e., average data of all words
        word_count = float(len(self.word_infos))
        self.avg_len = sum([len(w.text) for w in self.word_infos])/word_count
        self.avg_freq = sum([w.freq for w in self.word_infos])/word_count
        self.avg_left_entropy = sum([w.left for w in self.word_infos])/word_count
        self.avg_right_entropy = sum([w.right for w in self.word_infos])/word_count
        self.avg_aggregation = sum([w.aggregation for w in self.word_infos])/word_count
        # Filter out the results satisfy all the requirements
        filter_func = lambda v: len(v.text) > 1 and v.aggregation > self.min_aggregation and\
                                v.left > self.min_entropy and v.right > self.min_entropy
        self.word_with_freq = [(w.text, w.freq) for w in list(filter(filter_func, self.word_infos))]
        self.words = [w[0] for w in self.word_with_freq]

    def genWords(self, doc):
        """
        Generate all candidate words with their frequency/entropy/aggregation informations
        @param doc the document used for words generation
        """
        pattern = re.compile('[\\s\\d,.<>/?:;\'\"[\\]{}()\\|~!@#$%^&*\\-_=+a-zA-Z，。《》、？：；“”‘’｛｝【】（）…￥！—┄－]+')
        doc = re.sub(pattern, ' ', doc)
        suffix_indexes = indexOfSortedSuffix(doc, self.max_word_len)
        word_cands = {}
        # compute frequency and neighbors
        for suf in suffix_indexes:
            word = doc[suf[0]:suf[1]]
            if word not in word_cands:
                word_cands[word] = WordInfo(word)
            word_cands[word].update(doc[suf[0] - 1:suf[0]], doc[suf[1]:suf[1] + 1])
        # compute probability and entropy
        length = len(doc)
        for k in word_cands:
            word_cands[k].compute(length)
        # compute aggregation of words whose length > 1
        values = sorted(list(word_cands.values()), key=lambda x: len(x.text))
        for v in values:
            if len(v.text) == 1: continue
            v.computeAggregation(word_cands)
        return sorted(values, key=lambda v: v.freq, reverse=True)

    def segSentence(self, sentence, method=ALL):
        """
        Segment a sentence with the words generated from a document
        @param sentence the sentence to be handled
        @param method segmentation method
        """
        i = 0
        res = []
        while i < len(sentence):
            if method == self.L or method == self.S:
                j_range = list(range(self.max_word_len, 0, -1)) if method == self.L else list(range(2, self.max_word_len + 1)) + [1]
                for j in j_range:
                    if j == 1 or sentence[i:i + j] in self.words:
                        res.append(sentence[i:i + j])
                        i += j
                        break
            else:
                to_inc = 1
                for j in range(2, self.max_word_len + 1):
                    if i + j <= len(sentence) and sentence[i:i + j] in self.words:
                        res.append(sentence[i:i + j])
                        if to_inc == 1: to_inc = j
                if to_inc == 1: 
                    res.append(sentence[i])
                i += to_inc
        return res



if __name__ == '__main__':
    dict_bank = []
    corpus_path = hp.corpus_path
    dict_path = hp.dict_path
    doc = codecs.open(corpus_path, "r", "utf-8").read()
    for i in codecs.open(dict_path, 'r', "utf-8"):
        dict_bank.append(i.strip())
    ws = WordSegment(doc, max_word_len=hp.max_n, min_entropy=hp.min_entropy, min_aggregation=hp.min_aggregation)
    new_segs = ws.segSentence(doc)
    charpos = posrecord(new_segs)
    words = pwprobability(new_segs,charpos,doc,hp.threshold)
    new_words = extract_newword(words,dict_bank)
    print('the new words:')
    print(new_words)


