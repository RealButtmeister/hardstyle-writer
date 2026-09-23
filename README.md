# Hardstyle Writer

A desktop writer for hardstyle and hard-dance vocals: MC lines, chants, spoken hooks, and crowd calls. It checks word rules, line counts, and pronunciation-based end rhymes.

## Run from source

1. Install Python 3.11 or newer with Tcl/Tk support. On Windows, enable the Python launcher during installation.
2. Open a terminal in this repository.
3. Run `python setup_dictionary.py` once to download CMUdict for the rhyme checker.


```powershell
python rap_writer.py
```

On Windows, you can also double-click **Launch Hardstyle Writer.vbs** after setup. The launcher discovers an installed Python; it contains no machine-specific path.

The Python code uses the standard library. Tkinter is supplied by your Python installation, not by pip. See [BUILD.md](BUILD.md) for environment and validation steps.

## Using the writer

Enter a brief, choose the writing controls and length, then add blocked or wanted words. Use Connection to select a model and enter an API key for the current session, or set `OPENAI_API_KEY` locally. Writing requires network access and API usage; the app sends the brief, word lists, and any draft submitted for rewriting to the provider. It produces text, not audio.

Settings can contain your brief and word lists. They are local and ignored by Git. API keys are not written into settings. Save lyrics only to files you choose, and keep personal drafts and keys out of commits.

The detailed original usage notes are in [README.txt](README.txt).

CMUdict is downloaded separately rather than vendored. Its retained license and attribution are in [data](data/README.md).

## License

No project license was included in the source snapshot. This repository does not assign a new license. Any third-party components retain their own terms.
