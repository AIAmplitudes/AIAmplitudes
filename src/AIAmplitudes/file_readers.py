import re,os
import tempfile
import tarfile
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import json

################### Download tarballs from git ###############################
def _cache_path(cache_dir: str | None = None) -> Path:
    if cache_dir is None:
        ampdir = Path.home() / ".local" / "AIAmplitudesData"
        ampdir.mkdir(exist_ok=True, parents=True)
        return ampdir
    return Path(cache_dir)

relpath = _cache_path(None)
public_repo =  "AIAmplitudes/data_public"

def get_gitfilenames(the_zipurl):
    soup = BeautifulSoup(requests.get(the_zipurl).text)
    files=[]
    for elem in soup.find_all('script', type='application/json'):
        if ".tar" in elem.text:
            files += [i["name"] for i in json.loads(elem.contents[0])["props"]["initialPayload"]["tree"]["items"]]
    return files

def download_unpack(myfile: str, local_dir: Path):
    with tempfile.TemporaryFile() as f:
        with requests.get(myfile, stream=True) as r:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        f.seek(0)
        with tarfile.open(fileobj=f) as tarf:
            for n in tarf.getnames():
                assert os.path.abspath(os.path.join(local_dir, n)).startswith(str(local_dir))
            tarf.extractall(path=local_dir)
    return

def download_all(repo: str = public_repo, cache_dir: str | None = None) -> None:
    local_dir = _cache_path(cache_dir)
    if not len(os.listdir(local_dir))==0:
        print("error! local cache not empty!")
        raise ValueError
    print(f"downloading files from {repo}, unpacking in {local_dir}")
    url=f"https://github.com/{repo}"
    for file in get_gitfilenames(url):
        if not ".tar" in file: continue
        myfile = f"https://raw.githubusercontent.com/{repo}/main/{file}"
        print(f"extracting {myfile}")
        download_unpack(myfile,local_dir)
    return

#######################################################################################

def convert(filename, loop=None, reptype=None):
    #reptype: quad, oct, ae, aef, None
    if reptype in {"oct","quad"}:
        if reptype== "oct":
            base = readSymb(filename, 'Esymboct', loop)[:-2]
            prefix = [f'Br_8_{i}' for i in range(93)]
        elif reptype == "quad":
            base = readSymb(filename, 'Esymbquad', loop)[:-2]
            prefix = [f'Br_4_{i}' for i in range(8)]
        base = re.sub(' ', '', base)
        t = re.split(":=\[|\),|\)\]", base)[1:]
        if len(t[-1]) == 0: t = t[:-1]
        s = [re.split(":=|SB\(|\)", re.sub('[, *]', '', tt)) for tt in t]
        dev = []
        for i, ss in enumerate(s):
            for j, tt in enumerate(ss[1::2]):
                s[i][1 + 2 * j] = prefix[i] + tt
            dev += s[i]
        if len(dev[-1]) == 0: dev = dev[:-1]
    else:
        dev = re.split(":=|SB\(|\)", re.sub('[,*]', '',
                                            readSymb(filename, 'Esymb', loop)))[1:-1]

    keys = dev[1::2]
    values = [int(re.sub('[+-]$', t[0] + '1', t)) for t in dev[0::2]]
    out_dict = {k:v for k, v in zip(keys, values)}

    return out_dict

def readSymb(filename, prefix, loop=None):
    #read a symbol, given a filename and prefix
    assert os.path.isfile(filename)
    assert ('indep' in prefix) or (prefix in {'Esymb', 'Eaef', 'Eae', 'Esymbquad', 'Esymboct',
                      'frontspace', 'backspace','all7_new_common_factor', 'all7_sub_set', 'all6abc_list'})
    if not (('indep' in prefix) or (prefix in {'all7_new_common_factor', 'all7_sub_set', 'all6abc_list'})):
        mypref=prefix + '[' + str(loop) + ']'
    else: mypref=prefix

    with open(filename, 'rt') as f:
        return readFile(f,mypref)

def readFile(f, prefix):
    #read from an open file
    res = ''
    reading_form = False
    for line in f:
        if not reading_form:
            if not line.startswith(prefix): continue
            res = ''
            reading_form = True
        if line.isspace(): break
        res += line[:-2] if line[-2] == '\\' else line[:-1]
        if line[-2] in [":", ";"]:
            break
    return res

def SB_to_dict(mystring):
    def to_coef(mystr):
        if mystr == '-':
            return -1
        elif mystr == '':
            return 1
        else:
            return int(mystr)

    m = mystring.replace('-', '+-').replace(",", "").split('+')
    m2 = [el.replace("(", "").replace(")", "").replace("*", "").split("SB") for el in m]
    sbdict = {elem[1]: to_coef(elem[0]) for elem in m2 if len(elem) > 1}
    return sbdict

def FBconvert(w, name):
    mystr=''.join(str.split(readSymb(filename=name, name=name, loop=w)))
    newstr=re.split(":=|\[|\]",mystr)[4]
    dev = [elem+")" if elem[-1]!=")" else elem for elem in newstr.split("),") if elem]
    return [SB_to_dict(el) for el in dev]
