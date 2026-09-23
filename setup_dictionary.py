"""Download the separately installed CMUdict data from its official repository."""
from pathlib import Path
import urllib.request

SOURCE = 'https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict'
LIMIT = 8 * 1024 * 1024


def main():
    folder = Path(__file__).resolve().parent / 'data'
    if not (folder / 'CMUDICT-LICENSE.txt').is_file():
        raise RuntimeError('Keep data/CMUDICT-LICENSE.txt with the application before downloading CMUdict.')
    target = folder / 'cmudict.dict'
    if target.is_file():
        print('CMUdict is already installed. No file was changed.')
        return
    with urllib.request.urlopen(SOURCE, timeout=60) as response:
        raw = response.read(LIMIT + 1)
    if len(raw) > LIMIT or len(raw.splitlines()) < 100000:
        raise RuntimeError('The download did not look like the expected pronunciation dictionary.')
    raw.decode('utf-8')
    temporary = folder / 'cmudict.dict.tmp'
    try:
        temporary.write_bytes(raw)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print('CMUdict installed. Keep its license notice in the data folder.')


if __name__ == '__main__':
    main()
