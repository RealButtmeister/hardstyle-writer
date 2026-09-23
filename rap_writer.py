"""Hardstyle Writer: old-school rave vocals with checked end rhymes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import threading
from dataclasses import replace
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from lyric_engine import (
    DEFAULT_BLOCKED_WORDS, DEFAULT_MODEL, LyricRequest,
    GenerationError, GenerationCancelled, ValidationError,
    blocked_hits, missing_good_words, lyric_body, validate_request, generate_lyrics,
)
from rhyme_tools import rhyme_report

APP_DIR = Path(__file__).resolve().parent
BG = '#111315'
PANEL = '#1a1d20'
FIELD = '#24282c'
INK = '#f5f0e7'
MUTED = '#a5a8ad'
ACCENT = '#d8f45b'
GREEN = '#a8d5b2'
RED = '#ff9393'


def environment_key():
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if key:
        return key
    if os.name == 'nt':
        import winreg
        for hive, path in ((winreg.HKEY_CURRENT_USER, 'Environment'),
                           (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')):
            try:
                with winreg.OpenKey(hive, path) as entry:
                    value, _ = winreg.QueryValueEx(entry, 'OPENAI_API_KEY')
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            except OSError:
                pass
    return ''


class RapWriter(tk.Tk):
    def __init__(self, settings_path=None):
        super().__init__()
        self.title('Hardstyle Writer')
        self.geometry('1220x880')
        self.minsize(1040, 740)
        self.configure(bg=BG)
        self.option_add('*Font', ('Segoe UI', 10))
        self.settings_path = Path(settings_path) if settings_path else APP_DIR / 'settings.json'
        self.api_key = environment_key()
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.closed = False
        self.active_id = 0
        self.dirty = False
        self.exported_text = ''
        self.fields = {}
        self.last_result = None
        self._form_states = []
        self.custom_sections = [('Intro', 4), ('Build', 4), ('Hook', 8), ('Breakdown', 4), ('Build', 4), ('Hook', 8), ('Outro', 4)]
        self._last_rhyme_input=None
        self._styles()
        self._build()
        self._load_settings()
        self._refresh_connection()
        self.protocol('WM_DELETE_WINDOW', self._close)
        self.bind('<Control-Return>', lambda e: self.start_generation())
        self.bind('<Control-s>', lambda e: self.save_lyrics())
        self.after(120, self._poll)
        self.after(200, self._update_gate)

    def _styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=FIELD, background=FIELD,
                        foreground=INK, arrowcolor=INK, padding=5, borderwidth=0)
        style.map('TCombobox', fieldbackground=[('readonly', FIELD)],
                  foreground=[('readonly', INK)], selectbackground=[('readonly', FIELD)],
                  selectforeground=[('readonly', INK)])
        style.configure('Vertical.TScrollbar', background='#40454b', troughcolor=PANEL,
                        borderwidth=0, arrowcolor=MUTED)
        style.configure('Rap.Horizontal.TProgressbar', background=ACCENT,
                        troughcolor=FIELD, borderwidth=0, thickness=3)

    def label(self, parent, text, size=10, color=INK, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color,
                        font=('Segoe UI', size, 'bold' if bold else 'normal'),
                        anchor='w', **kwargs)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, relief='flat', bd=0,
                         bg=ACCENT if primary else FIELD, fg=BG if primary else INK,
                         activebackground='#e9ff92' if primary else '#363b41',
                         activeforeground=BG if primary else INK,
                         disabledforeground='#777b80', cursor='hand2',
                         padx=15, pady=9, font=('Segoe UI', 10, 'bold'))

    def text_field(self, parent, name, height=3):
        frame = tk.Frame(parent, bg=FIELD)
        box = tk.Text(frame, height=height, bg=FIELD, fg=INK, insertbackground=ACCENT,
                      selectbackground='#775536', relief='flat', bd=0, wrap='word',
                      padx=10, pady=6, undo=True, font=('Segoe UI', 10))
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=box.yview)
        box.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        box.pack(side='left', fill='both', expand=True)
        frame.pack(fill='x', pady=(4, 8))
        self.fields[name] = box
        return box

    def _build(self):
        header = tk.Frame(self, bg=BG, padx=26, pady=14)
        header.pack(fill='x')
        left_title = tk.Frame(header, bg=BG)
        left_title.pack(side='left')
        self.label(left_title, 'HARDSTYLE WRITER', 22, bold=True).pack(anchor='w')
        self.label(left_title, 'Old-school hard dance. Rave vocals. Strong end rhymes.', 10, MUTED).pack(anchor='w', pady=(3, 0))
        self.connection_btn = self.button(header, 'Connection', self.connection_dialog)
        self.connection_btn.pack(side='right')
        self.connection_label = self.label(header, '', 9, MUTED)
        self.connection_label.pack(side='right', padx=14)

        main = tk.Frame(self, bg=BG, padx=24)
        main.pack(fill='both', expand=True)
        main.columnconfigure(0, weight=0, minsize=400)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        sidebar = tk.Frame(main, bg=PANEL, width=410)
        self.sidebar = sidebar
        sidebar.grid(row=0, column=0, sticky='nsew', padx=(0, 18))
        sidebar.grid_propagate(False)
        sidebar.rowconfigure(0, weight=1)
        sidebar.columnconfigure(0, weight=1)
        canvas = tk.Canvas(sidebar, bg=PANEL, highlightthickness=0, width=390)
        side_scroll = ttk.Scrollbar(sidebar, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=side_scroll.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        side_scroll.grid(row=0, column=1, sticky='ns')
        form = tk.Frame(canvas, bg=PANEL, padx=18, pady=16)
        form_window = canvas.create_window(0, 0, window=form, anchor='nw')
        form.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(form_window, width=e.width))
        def scroll_form(event):
            widget = event.widget
            if isinstance(widget, tk.Text):
                return
            if str(widget).startswith(str(sidebar)):
                canvas.yview_scroll(int(-event.delta / 120), 'units')
        self.bind_all('<MouseWheel>', scroll_form, add='+')

        self.label(form, '01  /  THE BRIEF', 10, ACCENT, True).pack(anchor='w', pady=(0, 7))
        self.label(form, 'What is the rave vocal about?', bold=True).pack(anchor='w')
        self.text_field(form, 'topic', 2)
        self.label(form, 'Vocal character + track details', bold=True).pack(anchor='w')
        self.label(form, 'Dark spoken voice, crowd chant, kick or drop cue.', 9, MUTED).pack(anchor='w')
        self.text_field(form, 'details', 2)

        options = tk.Frame(form, bg=PANEL)
        options.pack(fill='x', pady=(0, 10))
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        self.style_var = tk.StringVar(value='Early hardstyle')
        self.mood_var = tk.StringVar(value='Dark / commanding')
        self.structure_var = tk.StringVar(value='8-line hook')
        self.rhyme_var = tk.StringVar(value='AABB couplets')
        configs = [('Delivery', self.style_var, ['Early hardstyle', 'Reverse-bass hardstyle', 'Hard trance / hard dance', 'Rave MC / crowd chant', 'Dark spoken vocal', 'Jumpstyle chant']),
                   ('Mood', self.mood_var, ['Dark / commanding', 'Raw / aggressive', 'Hypnotic / relentless', 'Rebellious', 'Euphoric / fierce', 'Playful / rowdy'])]
        for column, (title, variable, choices) in enumerate(configs):
            self.label(options, title, 9, MUTED).grid(row=0, column=column, sticky='w')
            ttk.Combobox(options, textvariable=variable, values=choices, state='readonly', width=18).grid(
                row=1, column=column, sticky='ew', padx=(0, 8) if column == 0 else (0, 0), pady=(4, 8))
        self.label(options, 'Length', 9, MUTED).grid(row=2, column=0, sticky='w')
        ttk.Combobox(options, textvariable=self.structure_var, state='readonly', width=18,
                     values=['8 bars', '16 bars', '24 bars', '32 bars', '8-line hook', 'Full song', 'Custom arrangement']).grid(
                         row=3, column=0, sticky='ew', padx=(0, 8), pady=(4, 0))
        self.explicit_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options, text='Swearing is fine', variable=self.explicit_var, bg=PANEL,
                       fg=INK, selectcolor=FIELD, activebackground=PANEL, activeforeground=INK,
                       highlightthickness=0).grid(row=3, column=1, sticky='w')
        self.label(options, 'End rhymes', 9, MUTED).grid(row=4, column=0, sticky='w', pady=(10,0))
        rhyme_box=ttk.Combobox(options,textvariable=self.rhyme_var,state='readonly',
                             values=['AABB couplets','ABAB alternating','AAAA chains'])
        rhyme_box.grid(row=5,column=0,columnspan=2,sticky='ew',pady=(4,0))
        rhyme_box.bind('<<ComboboxSelected>>',lambda event:self._update_gate())
        self.arrange_btn = self.button(options, 'Song structure…', self.structure_dialog)
        self.arrange_btn.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(10, 0))

        self.label(form, '02  /  YOUR WORDS', 10, ACCENT, True).pack(anchor='w', pady=(8, 6))
        self.label(form, 'Blocked words', bold=True).pack(anchor='w')
        self.label(form, 'Never in the result. Separate with commas or new lines.', 9, MUTED).pack(anchor='w')
        blocked = self.text_field(form, 'blocked_words', 2)
        blocked.insert('1.0', DEFAULT_BLOCKED_WORDS)
        blocked.bind('<<Modified>>', self._rules_modified)
        good_heading = tk.Frame(form, bg=PANEL)
        good_heading.pack(fill='x')
        self.label(good_heading, 'Good words', bold=True).pack(side='left')
        self.require_var = tk.BooleanVar(value=False)
        tk.Checkbutton(good_heading, text='Require all', variable=self.require_var,
                       command=self._update_gate, bg=PANEL, fg=INK, selectcolor=FIELD,
                       activebackground=PANEL, activeforeground=INK, highlightthickness=0).pack(side='right')
        self.label(form, 'Words / phrases you like. Commas or new lines.', 9, MUTED).pack(anchor='w')
        good = self.text_field(form, 'good_words', 2)
        good.bind('<<Modified>>', self._rules_modified)

        action_frame = tk.Frame(sidebar, bg=PANEL, padx=18, pady=10)
        action_frame.grid(row=1, column=0, columnspan=2, sticky='ew')
        self.generate_btn = self.button(action_frame, 'Write rave vocals', self.start_generation, True)
        self.generate_btn.pack(side='left', fill='x', expand=True)
        self.cancel_btn = self.button(action_frame, 'Stop', self.cancel_generation)
        self.cancel_btn.configure(state='disabled')
        self.cancel_btn.pack(side='left', padx=(8, 0))

        notebook = tk.Frame(main, bg=PANEL, padx=22, pady=18)
        notebook.grid(row=0, column=1, sticky='nsew')
        notebook.columnconfigure(0, weight=1)
        notebook.rowconfigure(2, weight=1)
        top = tk.Frame(notebook, bg=PANEL)
        top.grid(row=0, column=0, sticky='ew')
        self.label(top, 'THE VOCAL', 11, ACCENT, True).pack(side='left')
        self.count_label = self.label(top, '0 lines', 9, MUTED)
        self.count_label.pack(side='right')
        gate_frame=tk.Frame(notebook,bg=PANEL)
        gate_frame.grid(row=1,column=0,sticky='ew',pady=(6,12))
        self.gate_label = self.label(gate_frame, 'Write a vocal or paste one here to rework it.', 9, MUTED)
        self.gate_label.pack(fill='x')
        self.rhyme_label=self.label(gate_frame,'AABB: each pair ends on different rhyming words.',9,ACCENT)
        self.rhyme_label.pack(fill='x',pady=(4,0))
        editor_frame = tk.Frame(notebook, bg=PANEL)
        editor_frame.grid(row=2, column=0, sticky='nsew')
        self.editor = tk.Text(editor_frame, bg=PANEL, fg=INK, insertbackground=ACCENT, height=1, width=1,
                              relief='flat', bd=0, wrap='word', undo=True, padx=0, pady=8,
                              font=('Segoe UI', 13), spacing1=3, spacing3=5,
                              selectbackground='#775536')
        edit_scroll = ttk.Scrollbar(editor_frame, orient='vertical', command=self.editor.yview)
        self.editor.configure(yscrollcommand=edit_scroll.set)
        edit_scroll.pack(side='right', fill='y')
        self.editor.pack(side='left', fill='both', expand=True)
        self.editor.bind('<<Modified>>', self._editor_modified)
        self.editor.bind('<Control-c>', self._copy_selection)
        self.editor.bind('<Control-C>', self._copy_selection)
        self.editor.bind('<<Copy>>', self._copy_selection)
        self.editor.bind('<<Cut>>', self._cut_selection)
        self.editor.bind('<Control-x>', self._cut_selection)
        self.editor.bind('<Control-X>', self._cut_selection)
        self.label(notebook, 'What should the rewrite change?', 10, INK, True).grid(
            row=3, column=0, sticky='w', pady=(12, 4))
        revision_frame = tk.Frame(notebook, bg=FIELD)
        revision_frame.grid(row=4, column=0, sticky='ew')
        self.revision = tk.Text(revision_frame, height=2, bg=FIELD, fg=INK,
                                insertbackground=ACCENT, relief='flat', padx=10, pady=8,
                                wrap='word', font=('Segoe UI', 10))
        self.revision.pack(fill='x')
        tools = tk.Frame(notebook, bg=PANEL)
        tools.grid(row=5, column=0, sticky='ew', pady=(12, 0))
        self.rewrite_btn = self.button(tools, 'Rewrite', lambda: self.start_generation(True))
        self.rewrite_btn.pack(side='left')
        self.rhyme_btn=self.button(tools,'Tighten rhymes',self.tighten_rhymes)
        self.rhyme_btn.pack(side='left',padx=(8,0))
        self.undo_btn = self.button(tools, 'Undo', self.undo_edit)
        self.undo_btn.pack(side='left', padx=(8, 0))
        self.copy_btn = self.button(tools, 'Copy', self.copy_lyrics)
        self.copy_btn.pack(side='right', padx=(8, 0))
        self.save_btn = self.button(tools, 'Save .txt', self.save_lyrics)
        self.save_btn.pack(side='right')

        footer = tk.Frame(self, bg=BG, padx=26, pady=14)
        footer.pack(side='bottom', fill='x', before=main)
        self.status_var = tk.StringVar(value='Ready. Set the rave theme, choose a rhyme pattern, and write.')
        self.status_label = tk.Label(footer, textvariable=self.status_var, bg=BG, fg=MUTED, anchor='w')
        self.status_label.pack(fill='x')
        self.progressbar = ttk.Progressbar(footer, mode='indeterminate', style='Rap.Horizontal.TProgressbar')
        self.progressbar.pack(fill='x', pady=(8, 0))

    def value(self, name):
        return self.fields[name].get('1.0', 'end-1c').strip()

    def lyrics(self):
        return self.editor.get('1.0', 'end-1c').strip()

    def request(self, rewrite=False):
        return LyricRequest(topic=self.value('topic'), details=self.value('details'),
                            style=self.style_var.get(), mood=self.mood_var.get(),
                            structure=self.structure_text(), explicit=self.explicit_var.get(),
                            blocked_words=self.value('blocked_words'), good_words=self.value('good_words'),
                            require_good_words=self.require_var.get(), model=self.model_var.get(),
                            rhyme_scheme=self.rhyme_var.get(),
                            existing_lyrics=self.lyrics() if rewrite else '',
                            revision_note=self.revision.get('1.0', 'end-1c').strip() if rewrite else '')

    def structure_text(self):
        if self.structure_var.get() == 'Custom arrangement':
            return '\n'.join(f'{name}: {bars}' for name, bars in self.custom_sections)
        return self.structure_var.get()

    def structure_dialog(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self)
        dialog.title('Hardstyle Writer — Song structure')
        dialog.configure(bg=PANEL, padx=24, pady=22)
        dialog.geometry('630x640')
        dialog.minsize(590, 600)
        dialog.transient(self)
        sections = list(self.custom_sections)
        self.label(dialog, 'Build your song', 20, INK, True).pack(anchor='w')
        self.label(dialog, 'Set the sections, their order, and how many bars each gets.', 10, MUTED).pack(anchor='w', pady=(6, 15))
        presets = tk.Frame(dialog, bg=PANEL)
        presets.pack(fill='x', pady=(0, 12))
        def preset(entries):
            sections[:] = entries
            refresh(0)
        self.button(presets, 'Build + hook', lambda: preset([('Build', 4), ('Hook', 8)])).pack(side='left')
        self.button(presets, 'Full rave vocal', lambda: preset([('Intro', 4), ('Build', 4), ('Hook', 8), ('Breakdown', 4), ('Build', 4), ('Hook', 8), ('Outro', 4)])).pack(side='left', padx=8)
        self.button(presets, 'One hook', lambda: preset([('Hook', 8)])).pack(side='left')
        listing = tk.Frame(dialog, bg=PANEL)
        listing.pack(fill='both', expand=True)
        song_list = tk.Listbox(listing, bg=FIELD, fg=INK, selectbackground='#785334', height=6,
                              selectforeground=INK, relief='flat', bd=0,
                              font=('Segoe UI', 12), activestyle='none', exportselection=False)
        scroll = ttk.Scrollbar(listing, orient='vertical', command=song_list.yview)
        song_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        song_list.pack(side='left', fill='both', expand=True)
        summary = self.label(dialog, '', 10, ACCENT)
        summary.pack(anchor='w', pady=(8, 10))
        edits = tk.Frame(dialog, bg=PANEL)
        edits.pack(fill='x')
        edits.columnconfigure(0, weight=1)
        self.label(edits, 'Section name', 9, MUTED).grid(row=0, column=0, sticky='w')
        self.label(edits, 'Bars', 9, MUTED).grid(row=0, column=1, sticky='w', padx=(10, 0))
        name_var = tk.StringVar(value='Hook')
        bars_var = tk.StringVar(value='8')
        ttk.Combobox(edits, textvariable=name_var, values=['Intro', 'Build', 'Hook', 'Drop chant', 'Breakdown', 'Call and response', 'Outro']).grid(row=1, column=0, sticky='ew', pady=(5, 0))
        tk.Spinbox(edits, from_=1, to=64, textvariable=bars_var, width=7, bg=FIELD, fg=INK,
                   buttonbackground=FIELD, insertbackground=ACCENT, relief='flat').grid(row=1, column=1, padx=(10, 0), pady=(5, 0), ipady=7)
        def selected():
            selection = song_list.curselection()
            return selection[0] if selection else None
        def select(event=None):
            index = selected()
            if index is not None:
                name_var.set(sections[index][0])
                bars_var.set(str(sections[index][1]))
        def refresh(index=None):
            song_list.delete(0, 'end')
            for n, (name, bars) in enumerate(sections, 1):
                song_list.insert('end', f'  {n:02d}    {name}    /    {bars} bars')
            total = sum(bars for _, bars in sections)
            summary.configure(text=f'{len(sections)} sections  /  {total} bars total', fg=RED if total > 160 else ACCENT)
            if sections and index is not None:
                song_list.selection_set(min(index, len(sections) - 1))
                select()
        def get_entry():
            name = name_var.get().strip()
            try:
                bars = int(bars_var.get())
            except ValueError:
                bars = 0
            if not name or len(name) > 40 or any(c in name for c in ':[]\r\n'):
                messagebox.showinfo('Section name', 'Use a section name of 1–40 characters, without colons or brackets.', parent=dialog)
                return None
            if not 1 <= bars <= 64:
                messagebox.showinfo('Bars', 'Choose between 1 and 64 bars for this section.', parent=dialog)
                return None
            return name, bars
        def add():
            entry = get_entry()
            if entry:
                if len(sections) >= 12:
                    messagebox.showinfo('Song length', 'Use up to 12 sections.', parent=dialog)
                    return
                sections.append(entry)
                refresh(len(sections) - 1)
        def update():
            index = selected()
            entry = get_entry()
            if index is not None and entry:
                sections[index] = entry
                refresh(index)
        def remove():
            index = selected()
            if index is not None:
                sections.pop(index)
                refresh(index)
        def move(direction):
            index = selected()
            if index is not None and 0 <= index + direction < len(sections):
                sections[index], sections[index + direction] = sections[index + direction], sections[index]
                refresh(index + direction)
        controls = tk.Frame(dialog, bg=PANEL)
        controls.pack(fill='x', pady=(12, 10))
        for title, action in [('Add', add), ('Update', update), ('Remove', remove), ('↑', lambda: move(-1)), ('↓', lambda: move(1))]:
            self.button(controls, title, action).pack(side='left', padx=(0, 7))
        self.label(dialog, '1 lyric line = 1 bar. Up to 12 sections and 160 bars total.', 9, MUTED).pack(anchor='w')
        self.label(dialog, 'Repeated hooks are allowed. The generated order and counts are checked.', 9, MUTED).pack(anchor='w', pady=(3, 0))
        def apply():
            index = selected()
            if index is not None:
                entry = get_entry()
                if entry is None:
                    return
                sections[index] = entry
            if not sections or sum(bars for _, bars in sections) > 160:
                messagebox.showinfo('Song length', 'Add at least one section and keep the total at 160 bars or fewer.', parent=dialog)
                return
            from lyric_engine import parse_structure
            structure = '\n'.join(f'{name}: {bars}' for name, bars in sections)
            try:
                parse_structure(structure)
                for name, _ in sections:
                    if blocked_hits(name, self.value('blocked_words')):
                        raise ValidationError('A section name uses a blocked word. Rename it before continuing.')
            except ValidationError as error:
                messagebox.showinfo('Check this structure', str(error), parent=dialog)
                return
            self.custom_sections = list(sections)
            self.structure_var.set('Custom arrangement')
            self.arrange_btn.configure(text=f'Song structure…  ({len(sections)} sections)')
            self._save_settings()
            dialog.destroy()
        self.button(dialog, 'Use this structure', apply, True).pack(fill='x', pady=(18, 0))
        song_list.bind('<<ListboxSelect>>', select)
        refresh(0)
        dialog.grab_set()

    def _load_settings(self):
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        try:
            data = json.loads(self.settings_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                return
            for name, field in self.fields.items():
                if isinstance(data.get(name), str):
                    field.delete('1.0', 'end')
                    field.insert('1.0', data[name])
            for name, var in [('style', self.style_var), ('mood', self.mood_var),
                              ('structure', self.structure_var), ('model', self.model_var)]:
                if isinstance(data.get(name), str):
                    var.set(data[name])
            if data.get('rhyme_scheme') in ('AABB couplets','ABAB alternating','AAAA chains'):
                self.rhyme_var.set(data['rhyme_scheme'])
            if isinstance(data.get('explicit'), bool):
                self.explicit_var.set(data['explicit'])
            if isinstance(data.get('require_good_words'), bool):
                self.require_var.set(data['require_good_words'])
            sections = data.get('custom_sections')
            if isinstance(sections, list) and 1 <= len(sections) <= 12:
                valid = all(isinstance(s, list) and len(s) == 2 and isinstance(s[0], str)
                            and isinstance(s[1], int) and 1 <= s[1] <= 64 for s in sections)
                if valid and sum(s[1] for s in sections) <= 160:
                    self.custom_sections = [(s[0], s[1]) for s in sections]
        except (OSError, ValueError):
            pass

    def _save_settings(self):
        data = {name: self.value(name) for name in self.fields}
        data.update(style=self.style_var.get(), mood=self.mood_var.get(),
                    structure=self.structure_var.get(), explicit=self.explicit_var.get(),
                    require_good_words=self.require_var.get(), model=self.model_var.get(),
                    rhyme_scheme=self.rhyme_var.get())
        data['custom_sections'] = self.custom_sections
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.settings_path.with_suffix('.tmp')
            temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            temp.replace(self.settings_path)
            return True
        except OSError:
            self.status_var.set('Your preferences could not be saved. You can still write lyrics.')
            return False

    def _refresh_connection(self):
        self.connection_label.configure(text='Key found  /  Uses paid API' if self.api_key
                                         else 'Add your API key to write', fg=GREEN if self.api_key else ACCENT)

    def connection_dialog(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self)
        dialog.title('Hardstyle Writer — Connection')
        dialog.configure(bg=PANEL, padx=24, pady=22)
        dialog.transient(self)
        dialog.resizable(False, False)
        self.label(dialog, 'Connection', 18, INK, True).pack(anchor='w')
        self.label(dialog, 'Your brief and lyrics are sent to OpenAI when you write or rewrite.', 10, MUTED).pack(anchor='w', pady=(8, 3))
        self.label(dialog, 'Requires internet and API credit. API usage is billed separately.', 10, MUTED).pack(anchor='w')
        self.label(dialog, 'API key (only enter to replace the current key)', 10, INK, True).pack(anchor='w', pady=(20, 6))
        key_entry = tk.Entry(dialog, show='•', width=66, bg=FIELD, fg=INK, insertbackground=ACCENT, relief='flat')
        key_entry.pack(fill='x', ipady=8)
        self.label(dialog, 'Entered keys stay in memory for this session. They are never saved.', 9, MUTED).pack(anchor='w', pady=(5, 15))
        self.label(dialog, 'Model', 10, INK, True).pack(anchor='w', pady=(0, 5))
        model = tk.StringVar(value=self.model_var.get())
        ttk.Combobox(dialog, textvariable=model, values=[DEFAULT_MODEL, 'gpt-5-mini', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-5.4-mini'], width=30).pack(anchor='w')
        self.label(dialog, 'Each run uses 2 requests, up to 4 if a draft needs repairs.', 9, MUTED).pack(anchor='w', pady=(15, 4))
        self.label(dialog, 'Words and end rhymes are checked. Try the finished vocal over your track.', 9, MUTED).pack(anchor='w')
        actions = tk.Frame(dialog, bg=PANEL)
        actions.pack(fill='x', pady=(20, 0))
        def apply():
            if key_entry.get().strip():
                self.api_key = key_entry.get().strip()
            self.model_var.set(model.get().strip() or DEFAULT_MODEL)
            self._refresh_connection()
            self._save_settings()
            key_entry.delete(0, 'end')
            dialog.destroy()
        self.button(actions, 'Done', apply, True).pack(side='right')
        dialog.grab_set()

    def _rules_modified(self, event):
        if event.widget.edit_modified():
            event.widget.edit_modified(False)
            if hasattr(self, 'gate_label') and hasattr(self, 'require_var'):
                self._update_gate()

    def _editor_modified(self, event):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            self.dirty = self.lyrics() != self.exported_text
            self._update_gate()

    def _gate_problem(self, text):
        hits = sorted(set(blocked_hits(text, self.value('blocked_words')) +
                          blocked_hits(lyric_body(text), self.value('blocked_words'))))
        if hits:
            return 'Blocked words found: ' + ', '.join(hits[:8])
        if self.require_var.get():
            missing = missing_good_words(lyric_body(text), self.value('good_words'))
            if missing:
                return 'Required good words missing: ' + ', '.join(missing[:8])
        return ''

    def _update_gate(self):
        text = self.lyrics()
        count = len([line for line in lyric_body(text).splitlines() if line.strip()])
        self.count_label.configure(text=f'{count} bars / lines')
        problem = self._gate_problem(text) if text else ''
        if not text:
            label = 'Write a vocal or paste one here to rework it.'
        elif problem:
            label = problem
        else:
            label = 'Word rules passed  /  Try it over your kick pattern.'
        self.gate_label.configure(text=label, fg=RED if problem else GREEN if text else MUTED,
                                  wraplength=max(400, self.editor.winfo_width() - 10))
        rhyme_input=(text,self.rhyme_var.get())
        if rhyme_input!=self._last_rhyme_input:
            self._last_rhyme_input=rhyme_input
            report=rhyme_report(*rhyme_input)
            matched=report['matched_groups'];total=report['total_groups']
            if total:
                rhyme_text=f'End rhymes: {matched}/{total} groups matched · {self.rhyme_var.get()}'
                if report['unknown_words']:rhyme_text+=' · some endings unverified'
                elif matched<total:rhyme_text+=' · try Tighten rhymes'
            elif text and report['issues']:rhyme_text=report['issues'][0]
            else:rhyme_text='End rhymes: add enough lines for the selected pattern.'
            self.rhyme_label.configure(text=rhyme_text,fg=GREEN if total and matched==total else ACCENT,
                wraplength=max(400,self.editor.winfo_width()-10))
        state = 'normal' if text and not problem and not self.busy else 'disabled'
        self.copy_btn.configure(state=state)
        self.save_btn.configure(state=state)

    def tighten_rhymes(self):
        self.start_generation(True,extra_revision=(
            'Strengthen every completed end-rhyme group in the selected scheme. Use distinct, clearly rhyming final words. '
            'Keep the meaning, section counts, old-school hardstyle character and short chantable phrasing. '
            'Change as little else as possible; do not repeat the same ending word to fake a rhyme.'))

    def start_generation(self, rewrite=False, extra_revision=''):
        if self.busy:
            return
        if rewrite and not self.lyrics():
            self.status_var.set('Paste or write a vocal before choosing Rewrite.')
            return
        try:
            request = self.request(rewrite)
            if extra_revision:
                request=replace(request,revision_note='\n'.join(filter(None,(request.revision_note,extra_revision))))
            validate_request(request)
        except (ValidationError, ValueError) as error:
            messagebox.showinfo('Check your brief', str(error), parent=self)
            return
        if not self.api_key:
            self.connection_dialog()
            return
        self._save_settings()
        self.active_id += 1
        job_id = self.active_id
        self.cancel_event = threading.Event()
        cancel = self.cancel_event
        key = self.api_key
        self._set_busy(True)
        self.status_var.set('Writing rave vocals, then tightening the end rhymes…')
        def worker():
            try:
                result = generate_lyrics(request, key,
                                         progress=lambda text: self.events.put((job_id, 'progress', text)),
                                         cancel=cancel)
                self.events.put((job_id, 'result', result))
            except GenerationCancelled:
                self.events.put((job_id, 'cancelled', None))
            except (GenerationError, ValidationError) as error:
                self.events.put((job_id, 'error', str(error)))
            except Exception:
                self.events.put((job_id, 'error', 'Something went wrong. Your existing vocal is still here. Try again.'))
        threading.Thread(target=worker, daemon=True).start()

    def _set_busy(self, busy):
        self.busy = busy
        self.generate_btn.configure(state='disabled' if busy else 'normal')
        self.rewrite_btn.configure(state='disabled' if busy else 'normal')
        self.rhyme_btn.configure(state='disabled' if busy else 'normal')
        self.cancel_btn.configure(state='normal' if busy else 'disabled')
        self.editor.configure(state='disabled' if busy else 'normal')
        self.undo_btn.configure(state='disabled' if busy else 'normal')
        self.arrange_btn.configure(state='disabled' if busy else 'normal')
        self.connection_btn.configure(state='disabled' if busy else 'normal')
        if busy:
            self._form_states = []
            def lock(parent):
                for widget in parent.winfo_children():
                    if isinstance(widget, (tk.Text, ttk.Combobox, tk.Checkbutton)):
                        self._form_states.append((widget, widget.cget('state')))
                        widget.configure(state='disabled')
                    lock(widget)
            lock(self.sidebar)
            self.progressbar.start(14)
        else:
            for widget, state in self._form_states:
                widget.configure(state=state)
            self._form_states = []
            self.progressbar.stop()
        self._update_gate()

    def cancel_generation(self):
        if self.busy:
            self.cancel_event.set()
            self.cancel_btn.configure(state='disabled')
            self.status_var.set('Stopping after the current request returns. No further requests will start.')

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                job_id, kind, payload = self.events.get_nowait()
                if job_id != self.active_id:
                    continue
                if kind == 'progress':
                    if not self.cancel_event.is_set():
                        self.status_var.set(payload)
                elif kind == 'result':
                    self._set_busy(False)
                    if self.cancel_event.is_set():
                        self.status_var.set('Stopped. Your previous vocal is still here.')
                        continue
                    # Rules may have changed while the model was writing. Gate again on the UI thread.
                    issue = self._gate_problem(payload.lyrics)
                    if issue:
                        self.status_var.set('Your word rules changed during writing. Result withheld; write again.')
                        continue
                    self.editor.edit_separator()
                    self.editor.configure(autoseparators=False)
                    self.editor.delete('1.0', 'end')
                    self.editor.insert('1.0', payload.lyrics)
                    self.editor.configure(autoseparators=True)
                    self.editor.edit_separator()
                    self.last_result = payload
                    self.dirty = True
                    self._update_gate()
                    self.status_var.set(f'Ready — edited and checked. {payload.api_calls} requests used. Your ears make the final call.')
                elif kind == 'cancelled':
                    self._set_busy(False)
                    self.status_var.set('Stopped. Your previous vocal is still here.')
                elif kind == 'error':
                    self._set_busy(False)
                    self.status_var.set(payload)
                    messagebox.showerror('Could not finish this vocal', payload, parent=self)
        except queue.Empty:
            pass
        self.after(120, self._poll)

    def _exportable(self):
        text = self.lyrics()
        if not text or self.busy:
            return ''
        issue = self._gate_problem(text)
        if issue:
            self.status_var.set(issue + '. Rewrite or edit before copying or saving.')
            self._update_gate()
            return ''
        return text

    def copy_lyrics(self):
        text = self._exportable()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_var.set('Vocal copied.')

    def undo_edit(self):
        if self.busy:
            return
        try:
            self.editor.edit_undo()
            self.status_var.set('Previous edit restored.')
            self._update_gate()
        except tk.TclError:
            self.status_var.set('Nothing to undo yet.')

    def _copy_selection(self, event=None):
        if not self._exportable():
            return 'break'
        try:
            text = self.editor.get('sel.first', 'sel.last')
        except tk.TclError:
            return 'break'
        if self._gate_problem(text):
            self.status_var.set('Copy the whole vocal to include every required good word.')
            return 'break'
        self.clipboard_clear()
        self.clipboard_append(text)
        return 'break'

    def _cut_selection(self, event=None):
        if not self._exportable():
            return 'break'
        try:
            text = self.editor.get('sel.first', 'sel.last')
        except tk.TclError:
            return 'break'
        if self._gate_problem(text):
            self.status_var.set('This selection does not contain every required good word.')
            return 'break'
        self.clipboard_clear()
        self.clipboard_append(text)
        self.editor.delete('sel.first', 'sel.last')
        return 'break'

    def save_lyrics(self):
        text = self._exportable()
        if not text:
            return
        path = filedialog.asksaveasfilename(parent=self, title='Save your vocal',
                                          initialdir=str(APP_DIR), initialfile='My hardstyle vocal.txt',
                                          defaultextension='.txt', filetypes=[('Text file', '*.txt')])
        if path:
            try:
                Path(path).write_text(text + '\n', encoding='utf-8')
            except OSError:
                messagebox.showerror('Could not save', 'Choose a folder you can write to and try again.', parent=self)
                return
            self.exported_text = text
            self.dirty = False
            self.status_var.set('Vocal saved.')

    def _close(self):
        if self.dirty and self.lyrics():
            response = messagebox.askyesnocancel('Save your vocal?', 'Save your current vocal before closing?', parent=self)
            if response is None:
                return
            if response:
                self.save_lyrics()
                if self.dirty:
                    return
        self.cancel_event.set()
        self._save_settings()
        self.closed = True
        self.destroy()


if __name__ == '__main__':
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    RapWriter().mainloop()
