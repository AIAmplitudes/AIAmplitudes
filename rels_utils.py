# script to generate json files of a user-defined set of linear relations matched with a given symbol
# script to evaluate various linear relations satisfied by the symbols of the 3-point form factor of phi2

import os
import numpy as np
import datetime
import itertools
from itertools import permutations
import random
import json
import copy

##############################################################################################
# AUXILIARY FUNCTIONS #
##############################################################################################

########################################################################################################################
class fastRandomSampler(object):
    def __init__(self, init_elem, countdict={}, inplace=False):
        # this sampling struct works for dicts and sets, so just flag which it is
        if (not isinstance(init_elem, dict) and not isinstance(init_elem, set)): raise TypeError
        self.is_dict = isinstance(init_elem, dict)

        #the object to sample from. if inplace, edits the original dict,
        # otherwise, edits a copy. inplace is faster, but more dangerous.
        if inplace: self.mystruct = init_elem
        else: self.mystruct = init_elem.copy()

        # optional counter, if items have multiplicity. Used for scramble
        self.countdict = countdict

        # Create the key-to-int maps from the dictionary
        if len(self.mystruct) == 0:
            self.keylist, self.key_to_int = [],{}
        else:

            #self.keylist =
            self.keylist, self.key_to_int = [([*tup] if i == 0 else dict(tup))
                                                           for i,tup in enumerate(zip(*((k, (k, v))
                                                           for v, k in enumerate(self.mystruct))))]

    def __getitem__(self, item):
        if item in self.mystruct:
            return (self.mystruct[item] if self.is_dict else item)
        else:
            return None

    def __contains__(self, item):
        return item in self.mystruct

    def __len__(self):
        return len(self.mystruct)

    def __repr__(self):
        return str(self.mystruct)

    def __str__(self):
        return str(self.mystruct)

    def copy(self):
        return copy.copy(self)

    def keys(self):
        return self.mystruct.keys() if self.is_dict else self.mystruct

    def items(self):
        return self.mystruct.items() if self.is_dict else self.mystruct

    def values(self):
        return self.mystruct.values() if self.is_dict else None

    def add(self, key, value=None):  # O(1)
        # Add key-value pair (no extra work needed for simply changing the value)
        new_int = len(self.mystruct)
        if self.is_dict:
            self.mystruct[key] = value
        else:
            self.mystruct.add(key)

        self.key_to_int[key] = new_int
        self.keylist.append(key)

    def popitem(self, key):  # O(1)

        position = self.key_to_int.pop(key)
        last_item = self.keylist.pop()

        if position != len(self.keylist):
            self.keylist[position] = last_item
            self.key_to_int[last_item] = position
        if self.is_dict:
            return key, self.mystruct.pop(key)
        else:
            self.mystruct.remove(key)
            return key

    def remove(self, key):# O(1)
        if key not in self.key_to_int: return
        self.popitem(key)
        return

    def random_key(self):  # O(1)
    # Select a random key from the dictionary using the int_to_key map
        return self.keylist[int(len(self.mystruct) * random.random())]


    def remove_random(self):  # O(1)
        # Randomly remove a key from the dictionary via the bidirectional maps
        key = self.random_key()
        self.remove(key)

    def pop_random(self):  # O(1)
        # Randomly pop a key from the dictionary via the bidirectional maps
        try:
            key = self.random_key()
            if not self.countdict:
                # if we're not counting, just pop it
                return self.popitem(key)
            else:
                # countdict lets us pop keys multiple times (if keys have multiplicity)
                if self.countdict[key] == 1:
                    # If we're on the last time, pop it
                    self.countdict.pop(key, None)
                    return self.popitem(key)
                else:
                    # otherwise, decrement its counter- we've seen it
                    self.countdict[key] -= 1
                    if self.is_dict:
                        return key, self.mystruct[key]
                    else:
                        return key
        except IndexError:
            print("Error, symbol is exhausted!")

    def pop_random_gen(self, num_to_pop):  # O(1)
        for i in range(num_to_pop):
            yield self.pop_random()

    def pop_inst_gen(self, subdict_size, num_to_gen):
        # Randomly pop instances from the symb
        for i in range(num_to_gen):
            if self.is_dict:
                yield {k: v for k, v in self.pop_random_gen(subdict_size)}
            else:
                yield {k for k in self.pop_random_gen(subdict_size)}


# fixed alphabet
alphabet = ['a', 'b', 'c', 'd', 'e', 'f']
quad_prefix = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']

rels_to_generate= {"first": [[500]*3,[0]*3],
                            "double": [[500]*3,[0]*3],
                            "triple": [[500],[1]],
                            "dihedral": [[500],[1]],
                            "final": [[500]*19+[500]*10,[0]*19+[1]*10],
                            "integral": [[500]*3,[1]*3]
                              }

rels_to_generate_compact_default = {'first': [[500]*3, [0]*3],
                                    'double': [[500]*3, [0]*3],
                                    'triple': [[500], [1]],
                                    'integral': [[500]*3, [1]*3]}



###################################################################################
########################################################################################################################
#Auxiliary Functions
#######################################################################################################################
def find_all(a_str, sub):
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1: return
        yield start
        start += len(sub)

def count_appearances(key,slot):
    # the letter in slot is the Nth appearance, counting from left and starting the count at 1.
    # returns N.
    letter=key[slot]
    return [i for i in find_all(key,letter)].index(slot)+1

def check_slot(word,substr,slotnum):
    res = (word[slotnum: slotnum+len(substr)] == substr)
    return res

def update_counter(word,only_check_nonzeros,symb,min_overlap,count):
    #if we need an overlap of more than 1, increment the counter
    #otherwise, we're guaranteed an overlap of 1 if we draw from the symb, so don't bother
    if min_overlap == 1: count = 1
    else:
        if only_check_nonzeros == True:
            #If the symb has zeros but we want to ignore them
            if (word in symb) or (symb[word] == 0):
                count += 1
        else:
            if word in symb:
                count += 1
    return count

def read_rel_info(rels_to_generate, make_zero_rels=False):
    '''
    Parse a rel_info dict.
    ---------
    INPUTS:
    rels_to_generate: dict; rel type and ID.

    OUTPUTS:
    rels, slots, to_gens, overlaps, relnames: lists; consisting of: relation dicts, slots for rel, num to generate per rel, how much to overlap with sym, name of rel.
    '''

    rels, slots, to_gens, overlaps, relnames =[], [], [], [], []
    for rel_key, rel_info in rels_to_generate.items():
        for i in range(len(rel_info[0])):
            if not make_zero_rels and rel_info[1][i] == 0: continue
            myrel_table = {}
            myslot = None
            if rel_key == 'first':
                myrel_table=get_rel_table_dihedral(first_entry_rel_table)
                myslot=0
            elif rel_key == 'initial':
                myrel_table=get_rel_table_dihedral(initial_entries_rel_table)
                myslot=0
            elif rel_key == 'double':
                myrel_table=get_rel_table_dihedral(double_adjacency_rel_table)
                myslot=None
            elif rel_key == 'triple':
                myrel_table=get_rel_table_dihedral(triple_adjacency_rel_table)
                myslot=None
            elif rel_key == 'integral':
                myrel_table=get_rel_table_dihedral(integral_rel_table)
                myslot=None
            elif rel_key == 'final':
                myrel_table=get_rel_table_dihedral(final_entries_rel_table)
                myslot=-1
            elif rel_key == 'dihedral':
                myrel_table = [None] * len(rel_info[0])
                myslot = None
            else:
                print("unknown relation!")
                raise ValueError

            rels.append(myrel_table[i])
            slots.append(myslot)
            to_gens.append(rel_info[0][i])
            overlaps.append(rel_info[1][i])
            relnames.append(f'{rel_key}_{i}')
    return rels, slots, to_gens, overlaps, relnames

def gen_next(letter):
    # hardcode adjacency rules to generate nontrivial zeroes
    if letter == 'a':
        mylist = ['a', 'b', 'c', 'e', 'f']
        letter = mylist[int(len(mylist) * random.random())]
        return letter
    if letter == 'b':
        mylist = ['a', 'b', 'c', 'd', 'f']
        letter = mylist[int(len(mylist) * random.random())]
        return letter
    if letter == 'c':
        mylist = ['a', 'b', 'c', 'd', 'e']
        letter = mylist[int(len(mylist) * random.random())]
        return letter
    if letter == 'd':
        mylist = ['b', 'c', 'd']
        letter = mylist[int(len(mylist) * random.random())]
        return letter
    if letter == 'e':
        mylist = ['a', 'c', 'e']
        letter = mylist[int(len(mylist) * random.random())]
        return letter
    if letter == 'f':
        mylist = ['a', 'b', 'f']
        letter = mylist[int(len(mylist) * random.random())]
        return letter

def gen_first(letter):
    #given the second letter, generate a valid first letter
    if letter == 'a':
        mylist = ['a', 'b', 'c']
    elif letter == 'b':
        mylist = ['a', 'b', 'c']
    elif letter == 'c':
        mylist = ['a', 'b', 'c']
    elif letter == 'd':
        mylist = ['b', 'c']
    elif letter == 'e':
        mylist = ['a', 'c']
    elif letter == 'f':
        mylist = ['a', 'b']
    else: raise ValueError
    return mylist[int(len(mylist) * random.random())]


def gen_last(letter):
    #given the second to last letter, generate a valid last letter
    if letter == 'a':
        mylist = ['e', 'f']
    elif letter == 'b':
        mylist = ['d', 'f']
    elif letter == 'c':
        mylist = ['d', 'e']
    elif letter == 'd':
        mylist=['d']
    elif letter == 'e':
        mylist=['e']
    elif letter == 'f':
        mylist=['f']
    else: raise ValueError
    letter = mylist[int(len(mylist) * random.random())]
    return letter
def gen_valid_substr(to_gen,input=None,suffix=False):
    #generate a valid substring. If input is given, build a string that is compatible with it.
    #If 'suffix', gen a valid substring that can be reversed and prepended to input
    #otherwise, gen a valid substring that can be appended to input
    letter=''
    if input:
        if suffix: letter=input[0]
        else: letter = input[-1]
    for i in range(to_gen):
        if not suffix:
            if i == 0:
                mylist = ['a', 'b', 'c']
                letter = mylist[int(len(mylist) * random.random())]
        if suffix and (i == to_gen-1):
            letter = gen_first(letter)
        else:
            letter=gen_next(letter)
        yield letter

def gen_quad_suffix(letter):
    #hardcode adjacency rules to generate nontrivial zeroes
    if letter == 'a':
        mylist = ['b', 'c', 'd', 'f', 'h']
        return mylist[int(len(mylist) * random.random())]
    if letter == 'b':
        mylist = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        return mylist[int(len(mylist) * random.random())]
    if letter == 'c':
        mylist = ['a', 'b', 'c', 'd', 'e', 'g', 'h']
        return mylist[int(len(mylist) * random.random())]
    if letter == 'd':
        mylist = ['a', 'b', 'c', 'd', 'e', 'g', 'h']
        return mylist[int(len(mylist) * random.random())]
    if letter == 'e':
        return "h"
    if letter == 'f':
        mylist = ['b', 'c', 'd', 'f']
        return mylist[int(len(mylist) * random.random())]

def new_nontriv_key(loops, format):
    if format == "quad":
        key=[letter for letter in gen_valid_substr(2 * loops - 4)]
        suff=gen_quad_suffix(key[-1])
        return ''.join(suff+key)
    else:
        # generate a key that is not a trivial zero.
        key=[letter for letter in gen_valid_substr(2 * loops - 1)]
        last = gen_last(key[-1])
        return ''.join(key+last)


def generate_random_word(word_length, format='full', seed=0):
    '''
    Generate a random word with a specific length.
    ---------
    INPUTS:
    word_length: int; number of letters in the generated word.
    seed: int; random number generating seed; default 0.

    OUTPUTS:
    word: str; a word with letters in the alphabet and the specific length.
    '''
    if format not in ["full","quad","oct"]:
        print("Error, bad format!")
        raise ValueError
    word = ''
    for i in range(word_length):
        random.seed(seed + i)
        word += alphabet[int(len(alphabet) * random.random())]
    if format == 'full':
        return word
    if format == 'quad':
        print(word,quad_prefix)
        random.seed((seed+100)*10) # must generate another random number
        prefix = quad_prefix[int(len(quad_prefix) * random.random())]
        return prefix+word
    if format == 'oct': # not yet implemented
        #random.seed((seed+1000)*100) # must generate another random number
        #prefix = oct_prefix[int((len(quad_prefix) - 1) * random.random())]
        #return prefix+word
        return None

def get_coeff_from_word(word, symb):
    '''
    Get the coeff of a given word in a symbol.
    ---------
    INPUTS:
    word: str; a string of letters such as 'aaae'.
    symb: dict; a dictionary with word as key, and coeff as value, e.g., {'aaae':16, 'aaaf':16}.

    OUTPUTS:
    coeff: float; if word does not exist in symb, then return 0.
    '''
    if word in symb:
        return symb[word]
    return 0


def get_word_from_coeff(coeff, symb):
    '''
    Get the words corresponding to a given coeff in a symbol.
    ---------
    INPUTS:
    coeff: float; e.g., 16.
    symb: dict; a dictionary with word as key, and coeff as value, e.g., {'aaae':16, 'aaaf':16}.

    OUTPUTS:
    word: set; a set of words (strings) with the given coeff;
          if coeff does not exist in symb, then return an empty string.
    '''
    if coeff in symb.values():
        word = {i for i in symb if symb[i] == coeff}  # set
        return word
    return str()


def is_word(word, format='full'):
    '''
    Check if all the letters in a given word are all from the alphabet.
    ---------
    INPUTS:
    word: str.

    OUTPUTS:
    True/False: bool.
    '''
    if format not in ["full","quad","oct"]:
        print("Error, bad format!")
        raise ValueError

    if format == 'full':
        for letter in word:
            if letter not in alphabet:
                return False
        return True

    if format == 'quad':
        if word[0] not in quad_prefix:
            return False
        else:
            for letter in word[1:]:
                if letter not in alphabet:
                    return False
            return True

    if format == 'oct': # not yet implemented
        #if word[0] not in oct_prefix:
            #return False
        #else:
            #for letter in word[1:]:
                #if letter not in alphabet:
                    #return False
            #return True
        return None

def find_nonwords(symb, format='full'):
    '''
    Find all the nonwords in a given symbol;
    nonwords defined as words consisting of illegitimate letters.
    ---------
    INPUTS:
    symb: dict.

    OUTPUTS:
    nonwords: dict; dict for nonwords with {'word': coeff} in the given symbol.
    '''
    nonwords = {}
    for word in symb:
        if not is_word(word, format=format):
            coeff = get_coeff_from_word(word, symb)
            nonwords.update({word: coeff})
    return nonwords


def find_noncoeffs(symb):
    '''
    Find all the noncoeffs in a given symbol;
    noncoeffs defined as non integers.
    ---------
    INPUTS:
    symb: dict.

    OUTPUTS:
    noncoeffs: dict; dict for noncoeffs with {'word': coeff} in the given symbol.
    '''
    noncoeffs = {}
    for coeff in symb.values():
        if not isinstance(coeff, int):
            for word in get_word_from_coeff(coeff, symb):
                noncoeffs.update({word: coeff})
    return noncoeffs


def find_nonterms(symb, format='full'):
    '''
    Find all the nonterms in a given symbol;
    nonterms defined as either the words are nonwords, or the coeffs are noncoeffs, or both.
    ---------
    INPUTS:
    symb: dict.

    OUTPUTS:
    nonterms: dict; dict for nonterms with {'word': coeff} in the given symbol.
    '''

    nonterms = {}
    for word in symb:
        coeff = symb[word]

        if not is_word(word, format=format):
            coeff = get_coeff_from_word(word, symb)
            nonterms.update({word: coeff})

        if not isinstance(coeff, int):
            for word in get_word_from_coeff(coeff, symb):
                nonterms.update({word: coeff})

    return nonterms


def count_nonterms(symb, format='full'):
    '''
    Count the number of nonterms in a given symbol.
    ---------
    INPUTS:
    symb: dict.

    OUTPUTS:
    percent: float; between 0 and 1 (0: all terms are valid).
    '''

    return len(find_nonterms(symb, format=format)) / len(symb)


def remove_nonterms(symb,format='full'):
    '''
    Remove nonterms from a given symbol.
    ---------
    INPUTS:
    symb: dict.

    OUTPUTS:
    symb: dict; all nonterms removed.
    '''

    nonterms = find_nonterms(symb,format=format)
    for key in nonterms:
        symb.pop(key)
    return symb

##############################################################################################
# DIHEDRAL SYMMETRY #
##############################################################################################
# Dihedral symmetry is only meaningful to check with the full data format. If symbol words are
# represented in the compact formats of quad and oct, dihedral symmetry is already baked in,
# and cannot be checked, as a dihedral rotation may take us outside the given quad/oct symbol.
#
# E.g., 'acddc', which spelled out in full is 'cddcdddd', can become 'aeeaeeee' upon
# a dihedral rotation. But aeeaeeee is never in the given symb_quad in the first place,
# as there is no quad letter to designate the suffice 'eeee'.
#
# Therefore, in this section, we assume all words are given in the full format.

# a fixed look-up table for dihedral transformations

def get_dihedral_images(word):
    '''
    Get all the dihedral images of a given word.
    ---------
    INPUTS:
    word: str.

    OUTPUTS:
    dihedral_images: list; each item in the list is a word (str); always has six items.
    '''
    word_idx = [alphabet.index(l) for l in [*word]]
    dihedral_images = [''.join([dihedral_table[row][idx] for idx in word_idx]) for row in range(len(alphabet))]
    return dihedral_images

def get_valid_dihedral_images(word,pruned_symb,badsymb):
    '''
    Get all the dihedral images of a given word that are in a symb and not in a badsymb.
    ---------
    INPUTS:
    word: str.

    OUTPUTS:
    dihedral_images: list; each item in the list is a word (str); always has six items.
    '''
    word_idx = [alphabet.index(l) for l in [*word]]
    dihedral_images = {row:image for row in range(len(alphabet)) if (image := ''.join([dihedral_table[row][idx] for idx in word_idx])) in pruned_symb and image not in badsymb}
    return dihedral_images

def get_dihedral_pair(key,goodkeys,symb,type="cycle"):
    '''
    Given a key, the
    ---------
    INPUTS:
    key: str; key in dict.
    key_images. list; the dihedral images of the key.
    goodkeys. set; the allowed keys.
    symb. dict; the symbol to lookup coeffs.
    OUTPUTS:
    pair; dict. A two-term instance of type "cycle" or "flip".
    '''
    #print(goodkeys)
    if type == "cycle": indices=set([3,4])
    elif type == "flip": indices=set([1,2,5])
    else: raise ValueError
    good_inds=list(indices.intersection(set(goodkeys.keys())))
    if len(good_inds) == 0: return None
    #get random key: ind from goodkeys
    ind = random.choice(good_inds)
    pair = {key: [symb[key], 1], goodkeys[ind]: [symb[goodkeys[ind]], -1]}
    return pair

def get_cycle_images(word):
    '''
    Get all the 3-cycle dihedral images of a given word.
    ---------
    INPUTS:
    word: str.

    OUTPUTS:
    cycle_images: list; each item in the list is a word (str); always has six items.
    '''
    word_idx = [alphabet.index(l) for l in [*word]]
    cycle_images = [''.join([cycle_table[row][idx] for idx in word_idx]) for row in range(int(len(alphabet)/2))]
    return cycle_images

def get_dihedral_terms_in_symb(word, symb, count_coeffs=False, failsymb=None):
    '''
    Get the {word: coeff} of all the dihedral images of a given word in a symbol;
    if word (or its images) is not in the symb, then coeff=0.
    ---------
    INPUTS:
    word: str.
    symb: dict.
    count_coeffs: bool; whether to output the number of occurances of a certain coeff among all dihedral images of a word;
                  default False.

    OUTPUTS:
    images_coeffs: dict; all terms dihedrally related to the given word in the symbol.
    unique_coeffs_counts: dict; number of occurances of each unique coeff among the six dihedral images of a word;
                          e.g., {'16' (coeff): 6 (# of occurances)}; return only if count_coeffs=True.
    '''
    images = get_dihedral_images(word)
    images_coeffs = {}
    for image in images:
        images_coeffs.update({image: get_coeff_from_word(image, symb)})
        if failsymb and image in failsymb: return None

    if not count_coeffs:
        return images_coeffs

    unique_coeffs, counts = np.unique(np.array(list(images_coeffs.values())), return_counts=True)
    return images_coeffs, dict(zip(unique_coeffs, counts))

def get_cycles_flips_terms_in_symb(word, symb, count_coeffs=False):
    '''
    Get the {word: coeff} of all the dihedral images of a given word in a symbol;
    if word (or its images) is not in the symb, then coeff=0.
    ---------
    INPUTS:
    word: str.
    symb: dict.
    count_coeffs: bool; whether to output the number of occurances of a certain coeff among all dihedral images of a word;
                  default False.

    OUTPUTS:
    images_coeffs: dict; all terms dihedrally related to the given word in the symbol.
    unique_coeffs_counts: dict; number of occurances of each unique coeff among the six dihedral images of a word;
                          e.g., {'16' (coeff): 6 (# of occurances)}; return only if count_coeffs=True.
    '''
    images = get_dihedral_images(word)
    cycles = get_cycle_images(word)

    images_coeffs = {}
    cycles_coeffs = {}
    flips_coeffs = {}

    for image in images:
        images_coeffs.update({image: get_coeff_from_word(image, symb)})
        if image == word:
            cycles_coeffs.update({image: get_coeff_from_word(image, symb)})
            flips_coeffs.update({image: get_coeff_from_word(image, symb)})
        elif image in cycles:
            cycles_coeffs.update({image: get_coeff_from_word(image, symb)})
        else:
            flips_coeffs.update({image: get_coeff_from_word(image, symb)})
    if not count_coeffs:
        return images_coeffs, cycles_coeffs, flips_coeffs

    unique_coeffs, counts = np.unique(np.array(list(images_coeffs.values())), return_counts=True)
    return images_coeffs, cycles_coeffs, flips_coeffs,dict(zip(unique_coeffs, counts))


def count_wrong_dihedral(word, coeff_truth, symb, return_wrong_dihedral=False):
    '''
    Get the {word: coeff} of all the dihedral images of a given word in a symbol;
    if word (or its images) is not in the symb, then coeff=0.
    ---------
    INPUTS:
    word: str.
    coeff_truth: int; the ground truth value of the coeff for all dihedral images of the given word.
    symb: dict.
    return_wrong_dihedral: bool; whether to return the dict of dihedrally related words with wrong coeff;
                           default False.

    OUTPUTS:
    percent: float; percent of wrong coeffs; between 0 and 1.
    wrong_dihedral: dict; {word: coeff} where words are dihedrally related to the given word but with wrong coeff;
                    return only if return_wrong_dihedral=True.
    '''
    images_coeffs, coeff_counts = get_dihedral_terms_in_symb(word, symb, count_coeffs=True)
    wrong_dihedral = {}
    for coeff in coeff_counts:
        if coeff != coeff_truth:
            for word in get_word_from_coeff(coeff, images_coeffs):
                wrong_dihedral.update({word: coeff})

    if not return_wrong_dihedral:
        return len(wrong_dihedral) / len(images_coeffs)

    return len(wrong_dihedral) / len(images_coeffs), wrong_dihedral

##############################################################################################
# HOMOGENOUS LINEAR RELATIONS LOOK-UP TABLES#
##############################################################################################
dihedral_table = [list(permutations(alphabet[:3]))[i]+list(permutations(alphabet[3:]))[i] for i in range(len(alphabet))]
cycle_table=[dihedral_table[i] for i in [0,3,4]]
flip_table=[dihedral_table[i] for i in [0,1,2,5]]

# first entry condition
first_entry_rel_table = [{'d': 1}, {'e': 1}, {'f': 1}]  # Sec 3.1 (iv)

# double-adjacency condition: plus dihedral symmetry; any slot
double_adjacency_rel_table = [{'de': 1}, {'ad': 1}, {'da': 1}]  # eq 2.19, 2.20

# triple-adjacency relation: plus dihedral symmetry; any slot
triple_adjacency_rel_table = [{'aab': 1, 'abb': 1, 'acb': 1}]  # eq 2.21

# integrability relations: any slot
integral_rel_table = [{'ab': 1, 'ac': 1, 'ba': -1, 'ca': -1},  # eq 3.6
                      {'ca': 1, 'cb': 1, 'ac': -1, 'bc': -1},  # eq 3.7
                      {'db': 1, 'dc': -1, 'bd': -1, 'cd': 1, 'ec': 1, 'ea': -1, 'ce': -1,
                       'ae': 1, 'fa': 1, 'fb': -1, 'af': -1, 'bf': 1, 'cb': 2,
                       'bc': -2}]  # eq 3.8 coeff (8)! Takes longest time.

# multi-final-entries relations: plus dihedral symmetry
# new order: one-term relations, short relations (<=4 terms), long relations (>4 terms).
final_entries_rel_table = [{'a': 1}, {'b': 1}, {'c': 1},  # eq 4.6 (idx: 0-2)
                           {'ad': 1}, {'ed': 1},  # eq 4.7 (1) (idx: 3-4)
                           {'add': 1}, {'abd': 1}, {'ace': 1}, {'ebd': 1}, {'edd': 1},  # eq 4.9 (idx: 5-9)
                           {'addd': 1}, {'abbd': 1}, {'adbd': 1}, {'cbbd': 1},  # eq 4.10 (idx: 10-13)
                           {'ebbd': 1}, {'ebdd': 1}, {'edbd': 1}, {'eddd': 1}, {'fdbd': 1},  # eq 4.11 (idx: 14-18)

                           {'bf': 1, 'bd': -1},  # eq 4.7 (2) (idx: 19)
                           {'cdd': 1, 'cee': 1},  # eq 4.8 (1) (idx: 20)
                           {'ddbd': 1, 'dbdd': -1},  # eq 4.12 (idx: 21)
                           {'cbdd': 1, 'cdbd': -1},  # eq 4.15(1) (idx: 22)
                           {'fbd': 1, 'dbd': -1, 'bdd': 1},  # eq 4.8 (2) (idx: 23)
                           {'bddd': 1, 'faff': 1, 'dbdd': -1, 'eaff': -1, 'fbdd': 1, 'aeee': -1},  # eq 4.13 (idx: 24)
                           {'abdd': 1, 'cddd': -1 / 2, 'dcee': -1 / 2, 'aeee': 1 / 2, 'eaff': 1 / 2, 'faff': -1 / 2,
                            'ecee': 1 / 2},  # eq 4.14 (idx: 25)
                           {'cbdd': 1, 'bfff': -1 / 2, 'dcee': 1 / 2, 'ecee': -1 / 2, 'cddd': 1 / 2, 'dbdd': 1 / 2,
                            'fbdd': -1 / 2},  # eq 4.15(2) (idx: 26)
                           {'cdbd': 1, 'bfff': -1 / 2, 'dcee': 1 / 2, 'ecee': -1 / 2, 'cddd': 1 / 2, 'dbdd': 1 / 2,
                            'fbdd': -1 / 2},  # eq 4.15(3) (idx: 27)
                           {'fbbd': 1, 'dbbd': -1, 'bbdd': 1, 'faff': -1 / 2, 'dbdd': 1 / 2, 'fbdd': -1 / 2,
                            'eaff': 1 / 2, 'aeee': 1 / 2, 'bfff': -1 / 2}]  # eq 4.16 (idx: 28)

final_entries_multiterm_rel_table = [{'bf': 1, 'bd': -1},  # eq 4.7 (2) (idx: 19)
                           {'cdd': 1, 'cee': 1},  # eq 4.8 (1) (idx: 20)
                           {'ddbd': 1, 'dbdd': -1},  # eq 4.12 (idx: 21)
                           {'cbdd': 1, 'cdbd': -1},  # eq 4.15(1) (idx: 22)
                           {'fbd': 1, 'dbd': -1, 'bdd': 1},  # eq 4.8 (2) (idx: 23)
                           {'bddd': 1, 'faff': 1, 'dbdd': -1, 'eaff': -1, 'fbdd': 1, 'aeee': -1},  # eq 4.13 (idx: 24)
                           {'abdd': 1, 'cddd': -1 / 2, 'dcee': -1 / 2, 'aeee': 1 / 2, 'eaff': 1 / 2, 'faff': -1 / 2,
                            'ecee': 1 / 2},  # eq 4.14 (idx: 25)
                           {'cbdd': 1, 'bfff': -1 / 2, 'dcee': 1 / 2, 'ecee': -1 / 2, 'cddd': 1 / 2, 'dbdd': 1 / 2,
                            'fbdd': -1 / 2},  # eq 4.15(2) (idx: 26)
                           {'cdbd': 1, 'bfff': -1 / 2, 'dcee': 1 / 2, 'ecee': -1 / 2, 'cddd': 1 / 2, 'dbdd': 1 / 2,
                            'fbdd': -1 / 2},  # eq 4.15(3) (idx: 27)
                           {'fbbd': 1, 'dbbd': -1, 'bbdd': 1, 'faff': -1 / 2, 'dbdd': 1 / 2, 'fbdd': -1 / 2,
                            'eaff': 1 / 2, 'aeee': 1 / 2, 'bfff': -1 / 2}]  # eq 4.16 (idx: 28)


# multi-initial-entries relations: plus dihedral symmetry
# new order: one-term relations, short relations (<=4 terms), long relations (>4 terms).
initial_entries_rel_table = [{'ad': 1},
                           {'aad': 1},{'bcf': 1},{'bde': 1},{'bdf': 1},{'bda': 1},{'abd': 1},
                           {'cb': 1, 'bc': -1},
                           {'cd': 1, 'bd': -1},
                           {'aaf': 1, 'bbf': 1, 'abf': -1},
                           {'aab': 1,'aac': 1,'cca': 1,'bba': -1,'aba': -1},
                           {'bba': 1,'bbc': 1,'ccb': 1,'aab': -1,'abb': -1},
                           {'abc': 1,'aac': 1,'bbc': 1,'cca': 1,'ccb': 1},
                           {'aac': 1,'cca': 1,'bbc': -1,'ccb': -1,'afa': 1 / 2,'aaf': -1 / 2,'bbf': 1 / 2,'afb': -1 / 2}]
def trivial_zero_rel_table(format="full"):

    myrel_table = first_entry_rel_table
    slots = [0]*len(first_entry_rel_table)

    if format == "full":
        myrel_table += final_entries_rel_table[:3]
        slots += [-1]*len(final_entries_rel_table[:3])

    steinmanns = get_rel_table_dihedral(double_adjacency_rel_table)

    myrel_table += steinmanns
    slots += [None]*len(steinmanns)
    return myrel_table,slots


##############################################################################################
# GET DIHEDRAL IMAGES OF RELATIONS #
##############################################################################################


def get_rel_dihedral(rel):
    '''
    Given a relation, output all its dihedral images, where duplicated relations are removed.
    ---------
    INPUTS:
    rel: dict; one input relation; e.g. {'aab':1, 'abb':1, 'acb':1}.

    OUTPUTS:
    unique_rel_dihedral: list; each item in the list is a dict corresponding to the dihedral images of the given relation;
                  always has six items and in the fixed order of the dihedral look-up table.
    '''
    nterm = len(rel)
    term_list = list(rel.keys())
    rel_dihedral = []

    term_list_dihedral = [get_dihedral_images(term) for term in term_list]
    for i in range(len(term_list_dihedral[0])):
        rel_dihedral_term = {}

        for iterm in range(nterm):
            rel_dihedral_term.update({term_list_dihedral[iterm][i]: rel[term_list[iterm]]})

        rel_dihedral.append(rel_dihedral_term)

    unique_rel_dihedral = []
    seen_rel_dihedral = set()

    for d in rel_dihedral:
        dict_tuple = tuple(sorted(d.items()))
        if dict_tuple not in seen_rel_dihedral:
            seen_rel_dihedral.add(dict_tuple)
            unique_rel_dihedral.append(d)

    return unique_rel_dihedral


def get_rel_table_dihedral(rel_table):
    '''
    Given a relation table, output all the dihedral images of each relation,
    where duplicated relations are removed.
    ---------
    INPUTS:
    rel_table: list of dicts; e.g., one specific linear relations look-up table.

    OUTPUTS:
    unique_rel_table_dihedral: list of dicts; each item in the list is a dict corresponding to the dihedral images of one relation in the table;
                        total length of the list: nterms of the original table * 6 - duplicated terms.
    '''
    rel_table_dihedral = []
    unique_rel_table_dihedral = []
    for rel in rel_table:
        nterm = len(rel)  # number of terms in the relation
        term_list = list(rel.keys())

        term_list_dihedral = [get_dihedral_images(term) for term in term_list]
        for i in range(len(term_list_dihedral[0])):
            rel_dihedral = {}
            for iterm in range(nterm):
                rel_dihedral.update({term_list_dihedral[iterm][i]: rel[term_list[iterm]]})

            rel_table_dihedral.append(rel_dihedral)

        seen_rel_table_dihedral = set()

        for d in rel_table_dihedral:
            dict_tuple = tuple(sorted(d.items()))
            if dict_tuple not in seen_rel_table_dihedral:
                seen_rel_table_dihedral.add(dict_tuple)
                unique_rel_table_dihedral.append(d)

    return unique_rel_table_dihedral



##############################################################################################
# GET TERMS IN SYMBOL RELATED BY CERTAIN RELATIONS #
##############################################################################################


def get_rel_instances_in_symb(rel_instance_list, symb):
    '''
    Given a list of relation instances, get their term(s) in the given symbol.
    First step for relation-level relation check.
    ---------
    INPUTS:
    rel_instance_list: list of dicts; outputs of functions `generate_rel_instances`.
    symb: dict; symbol at a given loop order; can be the ground truth or the model predictions.

    OUTPUTS:
    rel_instance_in_symb_list: list of dicts; each item in the list is a dict corresponding to one relation instance
                               in the input rel_instance_list; key is word and value is [symb_coeff, rel_coeff];
                               if the word is not in symb, then its symb_coeff is automatically 0.
    '''
    rel_instance_in_symb_list = []
    if rel_instance_list is None:
        return None

    for rel_instance in rel_instance_list:
        rel_instance_in_symb = {}
        for word, rel_coeff in rel_instance.items():
            symb_coeff = get_coeff_from_word(word, symb)
            rel_instance_in_symb.update({word: [symb_coeff, rel_coeff]})
        rel_instance_in_symb_list.append(rel_instance_in_symb)

    return rel_instance_in_symb_list


def update_rel_instances_in_symb(rel_instance_in_symb_list, symb):
    '''
    Given a list of relation instances in the format {word: [symb_coeff, rel_coeff]},
    update symb_coeff by the new input symbol.
    ---------
    INPUTS:
    rel_instance_list: list of dicts; format: {word: [symb_coeff, rel_coeff]}.
    symb: dict; symbol at a given loop order; can be the ground truth or the model predictions.

    OUTPUTS:
    rel_instance_in_symb_list: list of dicts; same as the output of function 'get_rel_instances_in_symb';
                               each item in the list is a dict corresponding to one relation instance
                               in the input rel_instance_list; key is word and value is [symb_coeff, rel_coeff].
    '''
    rel_instance_in_symb_list_updated = []
    if rel_instance_in_symb_list is None:
        return None


    for rel_instance in rel_instance_in_symb_list:
        rel_instance_in_symb = {}
        for word, coeff_pair in rel_instance.items():
            symb_coeff = get_coeff_from_word(word, symb)
            rel_instance_in_symb.update({word: [symb_coeff, coeff_pair[1]]})
        rel_instance_in_symb_list_updated.append(rel_instance_in_symb)

    return rel_instance_in_symb_list_updated


def get_rel_terms_in_symb_per_word(word, symb, rel, rel_slot='any', format='full'):
    '''
    Given a word, get the related term(s) in the given symbol according to the specified relation.
    This serves as an intermediate step to get related term(s) for more words in the full symbol.
    ---------
    INPUTS:
    word: str.
    symb: dict.
    rel: dict.
    rel_slot: str; one of the three choices 'first', 'final', 'any';
              if 'first' or 'final', the relation can only be at the first or final few slots of a word;
              if 'any', the relation can be at any slot of a word.

    OUTPUTS:
    rel_terms_list: list of dicts; each item in the list is a dict in the format of
                    {'bbbf' (word): [16 (coeff), 1 (rel coeff)]}.
    '''
    if rel_slot not in {'first', 'initial', 'final', 'any'}: raise ValueError
    rel_terms_list = []
    nterm = len(rel)
    nletter = len(next(iter(rel)))  # number of letters in each term
    if format not in ["full","quad","oct"]:
        print("Error, bad format!")
        raise ValueError

    # first entry relation
    if rel_slot == 'first':
        rel_terms = {}

        if format == 'full':
            if word[:nletter] not in rel:
                return rel_terms_list
            else:
                rel_terms.update({word: [get_coeff_from_word(word, symb), rel[word[:nletter]]]})
                rel_terms_list.append(rel_terms)
                return rel_terms_list
        else: # compact formats
            if word[1:nletter] not in rel: # ignore the prefix
                return rel_terms_list
            else:
                rel_terms.update({word: [get_coeff_from_word(word, symb), rel[word[1:nletter]]]})
                rel_terms_list.append(rel_terms)
                return rel_terms_list

    # first entry relation
    if rel_slot == 'initial':
        rel_terms = {}

        if format == 'full':
            if word[:nletter] not in rel:
                return rel_terms_list
            else:
                rel_terms.update({word: [get_coeff_from_word(word, symb), rel[word[:nletter]]]})
                rel_terms_list.append(rel_terms)
                return rel_terms_list
        else: # compact formats
            if word[1:nletter] not in rel: # ignore the prefix
                return rel_terms_list
            else:
                rel_terms.update({word: [get_coeff_from_word(word, symb), rel[word[1:nletter]]]})
                rel_terms_list.append(rel_terms)
                return rel_terms_list


    # final entries relation
    if rel_slot == 'final':
        rel_terms = {}

        if format == 'full':
            if word[-nletter:] not in rel:
                    return rel_terms_list

            for key in rel:
                if word[-nletter:] == key:
                    pre_subword = word[:-nletter]
                    for key_rel in rel:
                        word_rel = pre_subword+key_rel
                        rel_terms.update({word_rel:[get_coeff_from_word(word_rel, symb), rel[key_rel]]})
                    rel_terms_list.append(rel_terms)
                    return rel_terms_list
        else: # compact formats: no final entries relations
            return None

    # relations that can be at any position slot
    if rel_slot == 'any':

        key_rel_list = list(rel.keys())

        if format == 'full':
            word = word
            prefix=''
        else: # compact formats
            prefix = word[0]
            word = word[1:]


        if not any(key_rel in word for key_rel in key_rel_list):
            # rel_terms = {}
            # rel_terms_list.append(rel_terms)
            return rel_terms_list

        for key_rel in rel:
            if key_rel in word:
                start_pos_list = [i.start() for i in find_all(word,key_rel)]
                rel_terms_pos = []

                for start_pos in start_pos_list:
                    rel_terms = {}

                    pre_subword = word[:start_pos]
                    post_subword = word[start_pos + nletter:]

                    for key_rel in rel:
                        if format == 'full':
                            word_rel = pre_subword+key_rel+post_subword
                        else: # compact formats
                            word_rel = prefix+pre_subword+key_rel+post_subword
                        rel_terms.update({word_rel: [get_coeff_from_word(word_rel, symb), rel[key_rel]]})

                    rel_terms_pos.append(rel_terms)

                rel_terms_list.append(rel_terms_pos)

        return list(itertools.chain(*rel_terms_list))


def get_rel_terms_in_symb(symb, fraction, rel, rel_slot='any', format='full',seed=0):
    '''
    Get the related term(s) in the given symbol according to the specified relation,
    for a fraction of words in the full symbol.
    ---------
    INPUTS:
    symb: dict.
    fraction: float; fraction of total words in the full symbol to be picked as samples;
              between 0 and 1, where 1 gets all words in the full symbol;
    rel: dict.
    rel_slot: str; one of the three choices 'first', 'final', 'any';
              if 'first' or 'final', the relation can only be at the first or final few slots of a word;
              if 'any', the relation can be at any slot of a word.
    seed: int; random number generating seed; default 0.

    OUTPUTS:
    rel_terms_list: list of dicts; each item in the list is a dict in the format of
                    {word: [symb_coeff, rel_coeff]}.
    '''
    if rel_slot not in {'first', 'initial', 'final', 'any'}: raise ValueError
    rel_terms_list_symb = []
    all_words = list(symb.keys())
    num_words_to_pick = int(len(all_words) * fraction)

    if num_words_to_pick <= 0:
        return []

    random.seed(seed)
    random_words = random.sample(all_words, num_words_to_pick)

    for word in random_words:
        rel_terms_list = get_rel_terms_in_symb_per_word(word, symb, rel, rel_slot=rel_slot, format=format)
        if rel_terms_list is None:
            return None
        for rel_terms in rel_terms_list:
            if (rel_terms) and (
            not any([rel_terms == existing_rel_terms for existing_rel_terms in rel_terms_list_symb])):
                rel_terms_list_symb.append(rel_terms)

    return rel_terms_list_symb



##############################################################################################
# CHECK RELATIONS IN SYMBOL #
##############################################################################################

def get_relsum_and_nzero(rel_terms_list, nterm, p_norm):
    for rel_terms in rel_terms_list:
        relsum = 0
        n_nontrivial0_term = 0
        for key, value in rel_terms.items():
            if value[0] == None:  # invalid symb_coeff
                relsum = -1
            else:
                try:
                    relsum += np.prod(value)
                except ArithmeticError:
                    print("overflow error! setting rel sum to -1")
                    relsum = -1

            if not is_trivial0(key):
                n_nontrivial0_term += 1

        if p_norm:
            try:
                relsum /= p_norm ** nterm
            except ArithmeticError:
                print("overflow error! setting rel sum to -1")
                relsum = -1
        yield relsum,n_nontrivial0_term
def check_rel(rel_terms_list, return_rel_info=False, p_norm=None):
    '''
    Check if all relations in the input list of relations are satisfied, i.e., sum up to 0.
    Valid regardless of the sampling approach, i.e., word-oriented or relation-oriented.
    ---------
    INPUTS:
    rel_terms_list: list of dicts; format {word: [symb_coeff, rel_coeff]}.
    return_rel_info: bool; whether to return the detailed info of each relation,
                     including relation sum and number of non-trivial-zero terms in each relation;
                     default False.
    p_norm: float or None; p is the average accuracy of model prediction;
            goal is to normalize the accuracy by the number of terms in a relation; default None.

    OUTPUTS:
    percent: float; percent of correct relations, i.e., those that sum up to 0; between 0 and 1 (1: all correct).
    relsum_list: list; each item in the list is a int/float for one instance,
                 where the int/float corresponds to the rel sum of that particular instance (should all be 0 if correct);
                 return only if return_info_info=True.
    relnontrivial0_list: list; each item in the list is an int for one instance,
                 where the int is the number of non-trivial-zero words in that particular instance;
                 return only if return_rel_info=True.
    '''
    relsum_list, relnontrivial0_list = [], []
    nterm = len(rel_terms_list[0])
    if rel_terms_list is None:
        return None
    #TODO: check this!
    relsum_list, relnontrivial0_list = zip(*[(elem) for elem in get_relsum_and_nzero(rel_terms_list,p_norm)])

    if not relsum_list:
        percent = None
    else:
        percent = relsum_list.count(0) / len(relsum_list)

        if p_norm:
            percent /= p_norm ** nterm

    if return_rel_info:
        return percent, relsum_list, relnontrivial0_list

    return percent



##############################################################################################
# WORD-ORIENTED APPROACH (works at 5 loops, but not scalable!) #
##############################################################################################


# The default relations to check in the format of {rel name: [frac, ..., frac]}, 
# where frac (0-1) is the fraction of the total words in a symbol to be checked  
# and the list order follows rel ID as defined in the relation tables. 
# If some rel ID is not to be checked, then set its corresponding frac to 0.
# Can be modified according to the user's needs. 

rels_to_check_default = {'first': [0.1, 0.1, 0.1], 'double': [0.1, 0.1, 0.1], 'triple': [0.1], 
                         'final': [0.1]*29, 'integral': [0.01, 0.01, 0.01]}


def assess_rels_viaword(symb, symb_truth, rels_to_check, p_norm=None, format='full', seed=0):
    '''
    Assess the success rate of a set of user-specified relations for a given symbol (usually model predictions),
    thru rels_to_check for word-oriented approach.
    One symbol only, which means one epoch model output.
    ---------
    INPUTS:
    symb: dict; usually model predictions.
    symb_truth: dict; truth symbol.
    rels_to_check: dict; user-defined relations to check; formats same as the two defaults defined above.
    p_norm: float or None; p is the average accuracy of model prediction;
            goal is to normalize the accuracy by the number of terms in a relation; default None.
    format: string; different formats to represent the words;
            only accept three choices---'full', 'quad', 'oct';
            if format is 'full', then can use `rels_to_check_full_default`;
            if format is 'quad' or 'oct, then can use `rels_to_check_compact_default`;
            note that here relations living across the seam are not considered, i.e.,
            only relations among exposed letters are considered; the format prefix is generated randomly.
    seed: int; random number generating seed; default 0;
          in principle, can even have a seed_list for different relations (currently not implemented).

    OUTPUTS:
    rel_acc: dict; format: {rel ID: [percent, percent_allcorrect, percent_magcorrect, percent_signcorrect, num_rels]},
                    where percent is the percent of correct relations,
                    percent_allcorrect is the percent of correct relations with all its coeffs correct,
                    percent_magcorrect is the percent of correct relations with all its coeffs mag-correct,
                    percent_signcorrect is the percent of correct relations with all its coeffs sign-correct,
                    and num_rels is the number of relation instances.
    '''
    print('Assessment via word approach starts at: ', datetime.datetime.now())
    rel_acc = {}
    for rel_key, rel_frac_list in rels_to_check.items():
        if rel_key == 'first':
            for i in range(len(rel_frac_list)):
                rel_term_in_symb_list = get_rel_terms_in_symb(symb, rel_frac_list[i], first_entry_rel_table[i],
                                                              rel_slot='first', format=format, seed=seed)
                percent = check_rel(rel_term_in_symb_list, return_rel_info=False, p_norm=p_norm)
                percent_allcorrect, percent_magcorrect, percent_signcorrect = check_coeffs_in_rel(rel_term_in_symb_list,
                                                                                                  symb_truth,
                                                                                                  return_counts=False)
                rel_acc.update({'first{}'.format(i): [percent, percent_allcorrect, percent_magcorrect,
                                                      percent_signcorrect, len(rel_term_in_symb_list)]})
            print('First entry relations done at: ', datetime.datetime.now())

        if rel_key == 'double':
            for i in range(len(rel_frac_list)):
                rel_term_in_symb_list = get_rel_terms_in_symb(symb, rel_frac_list[i], double_adjacency_rel_table[i],
                                                              rel_slot='any', format=format, seed=seed)
                percent = check_rel(rel_term_in_symb_list, return_rel_info=False, p_norm=p_norm)
                percent_allcorrect, percent_magcorrect, percent_signcorrect = check_coeffs_in_rel(rel_term_in_symb_list,
                                                                                                  symb_truth,
                                                                                                  return_counts=False)
                rel_acc.update({'double{}'.format(i): [percent, percent_allcorrect, percent_magcorrect,
                                                       percent_signcorrect, len(rel_term_in_symb_list)]})
            print('Double adjacency relations done at: ', datetime.datetime.now())

        if rel_key == 'triple':
            for i in range(len(rel_frac_list)):
                rel_term_in_symb_list = get_rel_terms_in_symb(symb, rel_frac_list[i], triple_adjacency_rel_table[i],
                                                              rel_slot='any', format=format, seed=seed)
                percent = check_rel(rel_term_in_symb_list, return_rel_info=False, p_norm=p_norm)
                percent_allcorrect, percent_magcorrect, percent_signcorrect = check_coeffs_in_rel(rel_term_in_symb_list,
                                                                                                  symb_truth,
                                                                                                  return_counts=False)
                rel_acc.update({'triple{}'.format(i): [percent, percent_allcorrect, percent_magcorrect,
                                                       percent_signcorrect, len(rel_term_in_symb_list)]})
            print('Triple adjacency relations done at: ', datetime.datetime.now())

        if rel_key == 'final':
            for i in range(len(rel_frac_list)):
                rel_term_in_symb_list = get_rel_terms_in_symb(symb, rel_frac_list[i], final_entries_rel_table[i],
                                                              rel_slot='final', format=format, seed=seed)
                percent = check_rel(rel_term_in_symb_list, return_rel_info=False, p_norm=p_norm)
                percent_allcorrect, percent_magcorrect, percent_signcorrect = check_coeffs_in_rel(rel_term_in_symb_list,
                                                                                                  symb_truth,
                                                                                                  return_counts=False)
                rel_acc.update({'final{}'.format(i): [percent, percent_allcorrect, percent_magcorrect,
                                                      percent_signcorrect, len(rel_term_in_symb_list)]})
            print('Final entries relations done at: ', datetime.datetime.now())

        if rel_key == 'integral':
            for i in range(len(rel_frac_list)):
                rel_term_in_symb_list = get_rel_terms_in_symb(symb, rel_frac_list[i], integral_rel_table[i],
                                                              rel_slot='any', format=format, seed=seed)
                percent = check_rel(rel_term_in_symb_list, return_rel_info=False, p_norm=p_norm)
                percent_allcorrect, percent_magcorrect, percent_signcorrect = check_coeffs_in_rel(rel_term_in_symb_list,
                                                                                                  symb_truth,
                                                                                                  return_counts=False)
                rel_acc.update({'integral{}'.format(i): [percent, percent_allcorrect, percent_magcorrect,
                                                         percent_signcorrect, len(rel_term_in_symb_list)]})
            print('Integrability relations done at: ', datetime.datetime.now())

        if rel_key == 'initial':
            for i in range(len(rel_frac_list)):
                rel_term_in_symb_list = get_rel_terms_in_symb(symb, rel_frac_list[i], initial_entries_rel_table[i],
                                                              rel_slot='initial', format=format, seed=seed)
                percent = check_rel(rel_term_in_symb_list, return_rel_info=False, p_norm=p_norm)
                percent_allcorrect, percent_magcorrect, percent_signcorrect = check_coeffs_in_rel(rel_term_in_symb_list,
                                                                                                  symb_truth,
                                                                                                  return_counts=False)
                rel_acc.update({'initial{}'.format(i): [percent, percent_allcorrect, percent_magcorrect,
                                                      percent_signcorrect, len(rel_term_in_symb_list)]})
            print('Initial entries relations done at: ', datetime.datetime.now())
    return rel_acc
    
##############################################################################################
# RELATION-ORIENTED APPROACH #
##############################################################################################


def assess_rels_viarel(symb, symb_truth, inpath, p_norm=None):
    '''
    Assess the success rate of a set of user-specified relations for a given symbol (usually model predictions),
    thru the stored relation instances for relation-oriented approach.
    One symbol only, which means one epoch model output.
    ---------
    INPUTS:
    symb: dict; usually model predictions.
    symb_truth: dict; truth symbol.
    inpath: str; folder path for rel_data.
    p_norm: float or None; p is the average accuracy of model prediction;
            goal is to normalize the accuracy by the number of terms in a relation; default None.

    OUTPUTS:
    rel_acc: dict; format: {rel ID: [percent, percent_allcorrect, percent_magcorrect, percent_signcorrect, num_rels]},
                    where percent is the percent of correct relations,
                    percent_allcorrect is the percent of correct relations with all its coeffs correct,
                    percent_magcorrect is the percent of correct relations with all its coeffs mag-correct,
                    percent_signcorrect is the percent of correct relations with all its coeffs sign-correct,
                    and num_rels is the number of relation instances.
    '''
    print('Assessment via relation approach starts at: ', datetime.datetime.now())
    rel_acc = {}

    for filename in os.listdir(inpath):
        if filename.endswith('.txt'): continue
        print('Assessing relation file {} ...'.format(filename))
        parts = filename.split("_")
        rel_key = parts[-1].split(".")[0]

        file_path = os.path.join(inpath, filename)
        if os.path.isfile(file_path) and filename.endswith('.json'):
            with open(file_path, 'r') as openfile:
                rel_instance_list = json.load(openfile)

                rel_instance_in_symb_list = update_rel_instances_in_symb(rel_instance_list, symb)
                percent = check_rel(rel_instance_in_symb_list, return_rel_info=False, p_norm=p_norm)
                percent_allcorrect, percent_magcorrect, percent_signcorrect = check_coeffs_in_rel(rel_instance_in_symb_list, symb_truth, return_counts=False)
                rel_acc.update({rel_key: [percent, percent_allcorrect, percent_magcorrect, percent_signcorrect, len(rel_instance_in_symb_list)]})

    print('Assessment via relation approach ends at: ', datetime.datetime.now())
    return rel_acc


def check_coeffs_in_rel(rel_terms_list, symb_truth_list, return_counts=False,require_satisfied=True):
    '''
    Check if all relations in the input list of relations are satisfied, i.e., sum up to 0.
    Valid regardless of the sampling approach, i.e., word-oriented or relation-oriented.
    ---------
    INPUTS:
    rel_terms_list: list of dicts; format {word: [symb_coeff, rel_coeff]}.
    symb_truth: list of dicts;format {word: [symb_coeff, rel_coeff]}. the truth symbol against which the correctness of
                symb_coeff predicted by the model for each word is checked.
    return_counts: bool; whether to return the count of correct coeffs in each rel instance;
                    default False.

    OUTPUTS:
    percent_allcorrect: float; percent of correct relations with all its word coeffs also correct.
    percent_magcorrect: float; percent of correct relations with all its word coeffs magnitude correct.
    correct_coeffs_in_rel_list: list of lists; format [[bool, int, int], [], ...], where bool suggests if the current relation
                            instance is correct, the first int indicates how many of its word coeffs are right,
                            and the second int suggests how many word coeffs are magnitude correct;
                            return only if return_counts=True.
    '''
    correct_coeffs_in_rel_list = []
    n_allcorrect_rel, n_magcorrect_rel, n_signcorrect_rel = 0, 0, 0
    n_allcorrect_norel, n_magcorrect_norel, n_signcorrect_norel = 0, 0, 0
    if rel_terms_list is None:
        return None

    for rel_terms, symb_truth in zip(rel_terms_list,symb_truth_list):
        relsum = 0
        n_allcorrect, n_magcorrect, n_signcorrect = 0, 0, 0
        nterm = len(rel_terms)

        for (key, value), (truth_key, truth_value) in zip(rel_terms.items(),symb_truth.items()):
            if value[0] == None:  # invalid symb_coeff
                relsum = -1
            else:
                try:
                    relsum += np.prod(value)
                except ArithmeticError:
                    print("overflow error! setting rel sum to -1")
                    relsum = -1

            if value[0] != None:
                if value[0] == truth_value[0]:
                    n_allcorrect += 1

                if np.abs(value[0]) == np.abs(truth_value[0]):
                    n_magcorrect += 1

                if np.sign(value[0]) == np.sign(truth_value[0]):
                    n_signcorrect += 1

        if relsum == 0:
            rel_correct = True
        else:
            rel_correct = False

        if rel_correct == True and n_allcorrect == nterm:
            n_allcorrect_rel += 1

        if rel_correct == True and n_magcorrect == nterm:
            n_magcorrect_rel += 1

        if rel_correct == True and n_signcorrect == nterm:
            n_signcorrect_rel += 1

        if n_allcorrect == nterm:
            n_allcorrect_norel += 1

        if n_magcorrect == nterm:
            n_magcorrect_norel += 1

        if n_signcorrect == nterm:
            n_signcorrect_norel += 1

        correct_coeffs_in_rel_list.append([rel_correct, n_allcorrect, n_magcorrect, n_signcorrect])
    if not correct_coeffs_in_rel_list:
        percent_allcorrect, percent_magcorrect, percent_signcorrect = None, None, None
    else:
        if require_satisfied:
            percent_allcorrect = n_allcorrect_rel / len(correct_coeffs_in_rel_list)
            percent_magcorrect = n_magcorrect_rel / len(correct_coeffs_in_rel_list)
            percent_signcorrect = n_signcorrect_rel / len(correct_coeffs_in_rel_list)
        else:
            percent_allcorrect = n_allcorrect_norel / len(correct_coeffs_in_rel_list)
            percent_magcorrect = n_magcorrect_norel / len(correct_coeffs_in_rel_list)
            percent_signcorrect = n_signcorrect_norel / len(correct_coeffs_in_rel_list)
    if return_counts:
        return percent_allcorrect, percent_magcorrect, percent_signcorrect, correct_coeffs_in_rel_list

    return percent_allcorrect, percent_magcorrect, percent_signcorrect
##############################################################################################
# ZERO SAMPLING  #
##############################################################################################

# Assume all words are in the full format (no quad, oct).

def is_trivial0(word):
    '''
    Check if a given word (assuming valid and in full format) is a trivial zero word.
    ---------
    INPUTS:
    word: str.
    OUTPUTS:
    True/False: bool.
    '''
    for rel in first_entry_rel_table: # prefix rule
        if word[0] in rel:
            return True

    for rel in final_entries_rel_table[:3]: # suffix rule
        if word[-1] in rel:
            return True

    for rel in get_rel_table_dihedral(double_adjacency_rel_table): # adjacency rule
        for rel_key in rel:
            if rel_key in word:
                return True

    return False



def replace_trivial0_terms(symb, return_symb=False):
    '''
    Find all the trivial zero words in a given symbol (assume valid and in full format)
    and manually force their coeffs to be zero, regardless of the original coeffs in the given symbol.
    ---------
    INPUTS:
    symb: dict.
    return_symb: bool; whether to return the full given symbol
                       with its trivial zero terms updated to have coeff=0;
                       default False.
    OUTPUTS:
    if return_symb == False, then
        trivial0_terms: dict; dict for trivial zero terms with {'word': 0} in the given symbol.
    if return_symb == True, then
        symb_updated: dict; full input symbol with its trivial zero terms updated to have coeff=0.
    '''
    trivial0_terms = {}
    symb_updated = symb.copy()
    for word in symb:
        if is_trivial0(word):
            trivial0_terms.update({word: 0})
            symb_updated.update({word: 0})

    if not return_symb:
        return trivial0_terms

    if return_symb:
        return symb_updated

def sumdict(k,d1,d2):
    out={}
    for k in d1 | d2:
        if (k in d1) and (k in d2): val = d1[k]+d2[k]
        elif (k in d1): val = d1[k]
        elif (k in d2): val = d2[k]
        else: val = 0
    out[k]=val
    return out