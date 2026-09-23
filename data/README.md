# Pronunciation dictionary setup

Hardstyle Writer uses [CMUdict from the CMU Sphinx project](https://github.com/cmusphinx/cmudict) for offline US English rhyme checks. The dictionary payload is not vendored in this repository.

Run `python setup_dictionary.py` once from the repository root. It downloads the official `cmudict.dict` into this folder. The app reads the local file afterward and does not download data during lyric generation. `data/cmudict.dict` is ignored by Git.

The original source snapshot included the dictionary unchanged with [CMUDICT-LICENSE.txt](CMUDICT-LICENSE.txt). That notice is retained here; retain it with any downloaded or redistributed copy. Pronunciation variants are accepted, while unknown or accent-specific endings may remain unverified.
