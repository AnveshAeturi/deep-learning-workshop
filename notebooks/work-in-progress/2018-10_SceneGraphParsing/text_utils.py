import re
import ftfy
import json
import spacy

from tqdm import tqdm

def get_pairs(word):
    """
    Return set of symbol pairs in a word.
    word is represented as tuple of symbols (symbols being variable-length strings)
    """
    pairs = set()
    prev_char = word[0]
    for char in word[1:]:
        pairs.add((prev_char, char))
        prev_char = char
    return pairs

def text_standardize(text):
    """
    fixes some issues the spacy tokenizer had on books corpus
    also does some whitespace standardization
    """
    text = text.replace('—', '-')
    text = text.replace('–', '-')
    text = text.replace('―', '-')
    text = text.replace('…', '...')
    text = text.replace('´', "'")
    text = re.sub(r'''(-+|~+|!+|"+|;+|\?+|\++|,+|\)+|\(+|\\+|\/+|\*+|\[+|\]+|}+|{+|\|+|_+)''', r' \1 ', text)
    text = re.sub(r'\s*\n\s*', ' \n ', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    return text.strip()

class TextEncoder(object):
    """
    mostly a wrapper for a public python bpe tokenizer
    """

    def __init__(self, encoder_path, bpe_path):
        #self.nlp = spacy.load('en', disable=['parser', 'tagger', 'ner', 'textcat'])
        self.nlp = spacy.load('en', disable=['ner', 'textcat']) # 'parser', 'tagger', 
        
        self.encoder = json.load(open(encoder_path))
        self.decoder = {v:k for k,v in self.encoder.items()}
        merges = open(bpe_path, encoding='utf-8').read().split('\n')[1:-1]
        merges = [tuple(merge.split()) for merge in merges]
        self.bpe_ranks = dict(zip(merges, range(len(merges))))
        self.cache = {}

    def bpe(self, token):
        word = tuple(token[:-1]) + ( token[-1] + '</w>',)
        if token in self.cache:
            return self.cache[token]
        pairs = get_pairs(word)

        if not pairs:
            return token+'</w>'

        while True:
            bigram = min(pairs, key = lambda pair: self.bpe_ranks.get(pair, float('inf')))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new_word = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                    new_word.extend(word[i:j])
                    i = j
                except:
                    new_word.extend(word[i:])
                    break

                if word[i] == first and i < len(word)-1 and word[i+1] == second:
                    new_word.append(first+second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            new_word = tuple(new_word)
            word = new_word
            if len(word) == 1:
                break
            else:
                pairs = get_pairs(word)
        word = ' '.join(word)
        if word == '\n  </w>':
            word = '\n</w>'
        self.cache[token] = word
        return word

    def encode(self, texts, verbose=False):
        texts_tokens = []
        if verbose:
            for text in tqdm(texts, ncols=80, leave=False):
                text = self.nlp(text_standardize(ftfy.fix_text(text)))
                text_tokens = []
                for token in text:
                    text_tokens.extend([self.encoder.get(t, 0) for t in self.bpe(token.text.lower()).split(' ')])
                texts_tokens.append(text_tokens)
        else:
            for text in texts:
                #print("ENCODING text='%s'" % (text, ))
                # example : ENCODING text='Javier went to the convenience store after school.'
                text = self.nlp(text_standardize(ftfy.fix_text(text)))
                text_tokens = []
                for token in text:
                    text_tokens.extend([self.encoder.get(t, 0) for t in self.bpe(token.text.lower()).split(' ')])
                texts_tokens.append(text_tokens)
        return texts_tokens

    def encode_and_clean(self, text):
        texts_bpes, texts_clean, lens_bpes = [], [], []
        if True:
            for text in texts:
                text = self.nlp(text_standardize(ftfy.fix_text(text)))
                text_tokens, text_bpe, len_bpe = [], [], []
                for token in text:
                    token_text = token.text
                    text_tokens.append(token_text)
                    new_bpe = [self.encoder.get(t, 0) for t in self.bpe(token_text.lower()).split(' ')]
                    text_bpe.extend(new_bpe)
                    len_bpe.append(len(new_bpe))
                texts_clean.append(' '.join(text_tokens))  # Reassemble
                texts_bpes.append(text_bpe)
                lens_bpes.append(len_bpe)
        return texts_bpes, texts_clean, lens_bpes

    def encode_nlp(self, text_nlp):  # text_nlp is a spacy nlp(text)
        #text_nlp = self.nlp(text_standardize(ftfy.fix_text(text)))
        bpes = []
        for token in text_nlp:
            token_text = token.text
            bpe = [self.encoder.get(t, 0) for t in self.bpe(token_text.lower()).split(' ')]
            bpes.append(bpe)
        return bpes # This is an array of word-ish arrays
        
    def encode_tokenized_text(self, text_arr):  # text_arr is a pre-tokenized array
        bpes = []
        for token_text in text_arr:
            bpe = [self.encoder.get(t, 0) for t in self.bpe(token_text.lower()).split(' ')]
            bpes.append(bpe)
        return bpes # This is an array of word-ish arrays
        
    def flatten_bpes(self, bpes):
      return [item for sublist in bpes for item in sublist]
      
    def cumlen_bpes(self, bpes):
      lens,tot=[0],0
      for b in bpes:
        tot+= len(b)
        lens.append(tot)
      return lens  # Returns arr[ word_idx ] -> bpe_offset

    def decode(self, bpe_arr, inter_bpe=''):  # This is a flat array # Maybe : inter_bpe='@@'
      #for s in bpe_arr:
      #  print(s, self.decoder[s])
      #dec = ''.join([ self.decoder[s] for s in bpe])
      
      lendec = len(self.decoder)
      dec, w = [], ''
      for s in bpe_arr:
        #print(s, self.decoder[s])
        #d = self.decoder[s]
        d = self.decoder[s] if s<lendec else '|</w>'
        if d.endswith('</w>'):
          dec.append(w+d[:-4])
          w=''
        else:
          w+=d+inter_bpe
      return ' '.join(dec)

    #def decode_as_fragments(self, bpe_arr):  # This is a flat array
    #  dec = []
    #  for s in bpe_arr:
    #    d = self.decoder[s] if s<len(self.decoder) else '|'
    #    if d.endswith('</w>'):
    #      dec.append(d[:-4])
    #    else:
    #      dec.append(d)
    #  return ' '.join(dec)

# Ought to have bpe decoder ...
# https://github.com/eladhoffer/seq2seq.pytorch/blob/master/seq2seq/tools/tokenizer.py
## Better : https://github.com/soaxelbrooke/python-bpe

