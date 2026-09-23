HARDSTYLE WRITER

Old-school hardstyle and hard-dance vocals: short commanding MC lines,
dark spoken hooks, reverse-bass chants, hard-trance tension and crowd calls.

GET STARTED
1. Open Hardstyle Writer on the desktop, or Launch Hardstyle Writer.vbs here.
2. Describe the vocal's theme and character. The starter brief is a dark
   underground warehouse chant. Choose a delivery and mood.
3. Choose a length and end-rhyme scheme. AABB couplets is the default:
   lines 1/2 rhyme, then 3/4, then 5/6, and so on.
4. Keep your blocked-word and preferred-word lists. Require all makes every
   preferred word mandatory. You can allow or disable swearing.
5. Click Write rave vocals. The AI drafts and edits the vocal, and the app
   checks pronunciation-based rhymes, word rules and exact line counts.
6. Use Rewrite for your own changes, or Tighten rhymes to improve line endings
   while preserving the theme. Copy, Save .txt and Undo remain available.

RHYMES
AABB couplets: each consecutive pair shares its ending sound.
ABAB alternating: lines 1/3 rhyme and 2/4 rhyme, repeating in four-line blocks.
AAAA chains: each four-line block shares one ending sound.
Every bracketed section restarts the scheme. Incomplete blocks compare only
existing positions; one unpaired line is allowed. Use even line counts for
AABB and multiples of four for complete ABAB/AAAA coverage.

The offline English checker uses the bundled CMU pronunciation dictionary.
It compares sounds from the last stressed vowel onward, accepting recorded
pronunciation variants. Matching spelling alone is insufficient: love/move
does not pass. Repeating the same final word does not count as a rhyme.
Accent-specific, invented or unfamiliar words may be unverified. Generation
asks the model to replace unverified grouped endings instead of guessing.
This checks rhyme sounds; your delivery still determines whether a line works.

The rhyme score above the editor updates as you edit. Newly generated lyrics
must pass every completed rhyme group. Your manual edits remain copyable and
saveable when the existing word rules pass, so the rhyme score is guidance
while you work. Tighten rhymes sends the edited vocal back for another pass.

SONG STRUCTURE
Full song: Intro 4 / Build 4 / Hook 8 / Breakdown 4 / Build 4 / Hook 8 / Outro 4.
Song structure lets you add, remove and reorder up to 12 sections and 160
total lyric lines. One lyric line means one vocal bar; these are words, not
generated audio or a MIDI arrangement. Leave instrumental space in your track
as you place the vocals.

API AND FILES
The existing OPENAI_API_KEY is detected automatically. Connection accepts a
masked replacement key for the current session. The key is not saved in
settings, lyrics or exports. Default model: gpt-5.5; editable in Connection.

Writing or rewriting sends your brief, word lists and draft to OpenAI.
It needs internet and API credit. A normal generation uses two paid requests;
up to two more repairs may run, with four requests maximum. If checks cannot
be satisfied, no failed draft replaces your current vocal. Stop prevents
further requests after the current one returns.

Keep rap_writer.py, lyric_engine.py, rhyme_tools.py and the data folder
together. The launcher uses the installed Python 3 with Tkinter; no extra
Python packages are required. Pronunciation data and its license are in data.
Settings retain your brief, vocabulary and choices. Lyrics are saved only
when you choose Save .txt. Closing an unsaved vocal asks whether to save it.

