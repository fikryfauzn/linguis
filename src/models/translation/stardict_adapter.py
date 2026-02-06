import re
import html
import os
from typing import Optional, Dict, Any
from .dictionary_adapter import DictionaryAdapter

try:
    from pystardict import Dictionary
    HAS_LIB = True
except ImportError:
    HAS_LIB = False

class StarDictAdapter(DictionaryAdapter):
    """
    T1.3: Real Adapter for StarDict.
    Hardened for OALD 'study' artifacts: 
    - Fixes HTML entities (&apos; -> ')
    - Nukes all-caps headers (ART, MUSIC, etc.)
    - Aggressively strips specific grammar noise strings.
    """
    def __init__(self, dict_path_prefix: str):
        if not HAS_LIB:
            raise ImportError("pystardict not installed.")
        
        prefix = dict_path_prefix[:-4] if dict_path_prefix.endswith(".ifo") else dict_path_prefix
        if not os.path.exists(prefix + ".ifo"):
            raise FileNotFoundError(f"Dictionary not found at: {dict_path_prefix}")
        
        self._dict = Dictionary(prefix)

    def lookup(self, term: str) -> Optional[Dict[str, Any]]:
        return self._lookup_internal(term, visited=set())

    def _lookup_internal(self, term: str, visited: set) -> Optional[Dict[str, Any]]:
        clean_term = term.strip()
        
        # Prevent circular redirects
        if clean_term.lower() in visited:
            print(f"DEBUG: Circular redirect detected for '{clean_term}'")
            return None
        visited.add(clean_term.lower())
        
        variations = self._get_variations(clean_term)
        
        print(f"DEBUG: Looking up '{clean_term}'")
        print(f"DEBUG: Variations: {variations}")
        
        data_blob = None
        found_word = clean_term

        for var in variations:
            print(f"  Trying: '{var}'")
            data_blob = self._dict.get(var) if hasattr(self._dict, 'get') else None
            if not data_blob:
                try: 
                    data_blob = self._dict[var]
                except KeyError: 
                    pass
            
            if data_blob:
                found_word = var
                print(f"  FOUND with: '{var}'")
                break
            else:
                print(f"  Not found")
        
        if not data_blob:
            return None

        return self._parse_oald_blob(found_word, data_blob, visited)

    def _get_variations(self, word: str) -> list[str]:
        vars = [word]
        word_l = word.lower()
        
        # Add lowercase version if word has uppercase
        if word != word_l:
            vars.append(word_l)
        
        # -s, -es plurals/verb forms
        if word_l.endswith('s') and not word_l.endswith('ss'): 
            vars.append(word[:-1])
        if word_l.endswith('es'): 
            vars.append(word[:-2])
        
        # -ies → -y (studies → study)
        if word_l.endswith('ies'): 
            vars.append(word[:-3] + 'y')
        
        # -ed past tense
        if word_l.endswith('ed'): 
            vars.append(word[:-2])  # worked → work
            vars.append(word[:-1])  # bored → bore
        
        # -ing present participle
        if word_l.endswith('ing'): 
            vars.append(word[:-3])      # working → work
            vars.append(word[:-3] + 'e')  # speaking → speake (will try speak via -e drop)
        
        # -ly adverbs → adjectives
        if word_l.endswith('ly'):
            vars.append(word[:-2])  # quickly → quick
        
        # -ness nouns → adjectives  
        if word_l.endswith('ness'):
            vars.append(word[:-4])  # manliness → manli
            if word_l.endswith('iness'):
                vars.append(word[:-5] + 'y')  # happiness → happy
            if word_l.endswith('liness'):
                vars.append(word[:-7] + 'ly')  # manliness → manly
        
        return list(dict.fromkeys(vars))
        
    def _parse_oald_blob(self, word: str, blob: str, visited: set) -> Dict[str, Any]:
        text = blob.decode('utf-8', errors='ignore') if isinstance(blob, bytes) else str(blob)
        text = html.unescape(text)
        
        # Check for redirect entries - use flexible matching for special chars
        redirect_match = re.search(r'Main\s+entry:.*?<kref>([^<]+)</kref>', text, re.DOTALL)
        
        # Only follow redirect if this is ONLY a redirect (no substantive definitions)
        if redirect_match:
            redirect_pos = redirect_match.start()
            content_before = text[:redirect_pos]
            
            # Check for numbered definitions
            has_numbered_defs = bool(re.search(r'<c c="(?:red|darkmagenta)"><b>\d+\.</b></c>', content_before))
            
            # Check for actual definition text (not just metadata/examples)
            # Look for blockquote with text that's not inside <ex>, <c>, or deep nesting
            temp = re.sub(r'<ex>.*?</ex>', '', content_before, flags=re.DOTALL)  # Remove examples
            temp = re.sub(r'<c c="[^"]*">.*?</c>', '', temp, flags=re.DOTALL)  # Remove colored metadata
            temp = re.sub(r'<(?:abr|rref|k|b)>[^<]*</(?:abr|rref|k|b)>', '', temp, flags=re.DOTALL)  # Remove other tags
            temp = re.sub(r'<[^>]+>', '', temp)  # Remove any remaining tags
            
            # Now check if there's meaningful text
            meaningful_text = temp.strip()
            has_real_definition = len(meaningful_text) > 20
            
            if not has_numbered_defs and not has_real_definition:
                redirect_word = redirect_match.group(1)
                print(f"DEBUG: Redirecting '{word}' to '{redirect_word}'")
                return self._lookup_internal(redirect_word, visited)
            else:
                print(f"DEBUG: Found content before redirect - not following redirect for '{word}'")
        
        # Continue with normal parsing...
        phonetic = ""
        ph_match = re.search(r'<c c="darkcyan">\[(.*?)\]</c>', text)
        if ph_match:
            phonetic = f"/{ph_match.group(1)}/"
        
        definitions = []
        pos_split = re.split(r'<c c="orange">\s*([a-z,\s]+?)\s*</c>', text)
        
        if len(pos_split) > 1:
            for i in range(1, len(pos_split), 2):
                raw_pos = pos_split[i].strip().replace(',', '') 
                section_text = pos_split[i+1]
                self._extract_defs_from_section(section_text, raw_pos, definitions, word)
        else:
            self._extract_defs_from_section(text, "entry", definitions, word)
        
        return {"word": word, "phonetic": phonetic, "definitions": definitions}
                    
    def _extract_defs_from_section(self, text: str, pos: str, defs_list: list, word: str):
        noise_markers = r'<(?:c|darkslategray)[^>]*>(?:Thesaurus|Example Bank|Word Origin|Idiom|Verb forms|Derived|Word Family|Collocations):'
        text = re.split(noise_markers, text, flags=re.IGNORECASE)[0]

        if 'Word Origin' in text and word == 'in':
            print(f"DEBUG AFTER SPLIT: Word Origin still present!")
            print(f"Text preview: {text[:500]}")

        # Regex for numbers: capture text after number until next number or semantic header
        pattern = re.compile(
            r'<c c="(?:red|darkmagenta)"><b>\d+\.</b></c>(.*?)(?=<c c="(?:red|darkmagenta)"><b>\d+\.</b></c>|<blockquote>|$)', 
            re.DOTALL
        )
        matches = pattern.findall(text)
        
        if matches:
            for raw_def in matches:
                if 'Word Origin' in raw_def:
                    print(f"DEBUG EXTRACT: Found Word Origin in raw_def")
                    print(f"Raw content: {raw_def[:200]}")
                # Skip Word Origin sections
                if re.search(r'Word Origin:', raw_def, re.IGNORECASE):
                    continue
                clean_def = self._clean_definition_text(raw_def, word)
                if clean_def and len(clean_def) >= 3:
                    if not any(d['text'] == clean_def for d in defs_list):
                        defs_list.append({"pos": pos, "text": clean_def})
        else:
            fallback_pattern = re.compile(r'<blockquote>(.*?)</blockquote>', re.DOTALL)
            fallback_match = fallback_pattern.search(text)
            if fallback_match:
                raw_content = fallback_match.group(1)
                # Skip Word Origin sections
                if re.search(r'Word Origin:', raw_content, re.IGNORECASE):
                    return
                clean_def = self._clean_definition_text(raw_content, word)
                if clean_def:
                    defs_list.append({"pos": pos, "text": clean_def})

    def _clean_definition_text(self, raw_html: str, headword: str) -> str:
        # 1. Strip bold inflected forms (studies, -born, etc.)
        cleaned = re.sub(r'<b>' + re.escape(headword.lower()) + r's?</b>\s*', '', raw_html)
        cleaned = re.sub(r'<b>studies</b>\s*', '', cleaned)
        cleaned = re.sub(r'<b>-\w+</b>\s*', '', cleaned)

        # 2. Strip usage patterns like "good/bad ~", "the younger", "the + word"
        cleaned = re.sub(r'<b>[^<]*[~/][^<]*</b>\s*', '', cleaned)
        cleaned = re.sub(r'<b>the\s+\w+er</b>\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'<b>the\s+' + re.escape(headword) + r'</b>\s*', '', cleaned, flags=re.IGNORECASE)
        
        # 3. Strip usage tildes/headwords in bold
        cleaned = re.sub(r'<b>\s*(?:~|' + re.escape(headword) + r')[^<]*</b>', '', cleaned, flags=re.IGNORECASE)
        
        # 3b. Strip usage patterns like "go, come, try, stay, etc. ~" (without bold tags)
        cleaned = re.sub(r'[a-z]+(?:,\s*[a-z]+)*,?\s+etc\.?\s*~\s*', '', cleaned, flags=re.IGNORECASE)
        
        # 4. Strip entire parenthetical metadata blocks
        # Pattern handles: (BrE, law) or (NAmE, informal) etc.
        # NOTE: May have space/nbsp before opening paren
        cleaned = re.sub(
            r'<c c="darkgray">[^\(]*\(</c>'
            r'(?:(?!</blockquote>).)*?'
            r'<c c="darkgray">\)[^\<]*</c>[\s\xa0]*',
            '', cleaned
        )
        
        # 4b. Strip parenthetical with italic metadata like "(often the Government)"
        cleaned = re.sub(
            r'<c c="darkgray">[^\(]*\(</c>'
            r'<i><c c="darkgray">[^<]*</c></i>\s*'
            r'<b>[^<]*</b>'
            r'<c c="darkgray">\)</c>[\s\xa0]*',
            '', cleaned
        )
        
        # 5. Strip grammatical metadata sequences
        cleaned = re.sub(r'(?:<c c="orangered">[^<]*</c>\s*(?:<c c="darkgray">[^<]*</c>\s*)?)+', '', cleaned)
        
        # 6. Strip remaining regional markers (BrE, NAmE, especially BrE, etc.)
        cleaned = re.sub(r'<c c="sienna">[^<]*</c>\s*', '', cleaned)
        
        # 6b. Strip remaining subject area markers (law, computing, biology, etc.)
        cleaned = re.sub(r'<c c="green">[^<]*</c>\s*', '', cleaned)

        # 6c. Clean up orphaned commas and spaces left after metadata removal
        text_so_far = re.sub(r'<[^>]+>', '', cleaned)  # Preview without tags
        cleaned_preview = re.sub(r'^\s*[,\s]+', '', text_so_far)  # Check what we'd get
        
        # 7. Strip grammatical patterns like "+ noun"
        cleaned = re.sub(r'<b>\s*\+\s*\w+\s*</b>\s*', '', cleaned)
        
        # 8. Strip equals sign references (= bubolic plague)
        cleaned = re.sub(r'<c c="darkcyan"><b>\s*=\s*</b></c>\s*', '', cleaned)
        
        # 9. Strip register/style metadata
        cleaned = re.sub(r'<c c="rosybrown">[^<]*</c>\s*', '', cleaned)
        
        # 10. Strip usage context in italics (in any color tag)
        cleaned = re.sub(r'<i><c c="[^"]*">[^<]*</c></i>\s*', '', cleaned)
        cleaned = re.sub(r'<c c="darkslategray"><i>[^<]*</i></c>\s*', '', cleaned)

        # 11. Strip Word Origin
        cleaned = re.sub(r'<c c="darkslategray">(?:<c>)?Word\s*Origin:?(?:</c>)?</c>\s*', '', cleaned, flags=re.IGNORECASE)
        
        # 12. Process darkslategray content intelligently
        # First, merge consecutive darkslategray tags into single tags
        while True:
            new_cleaned = re.sub(
                r'<c c="darkslategray">([^<]*)</c>\s*<c c="darkslategray">([^<]*)</c>',
                r'<c c="darkslategray">\1\2</c>',
                cleaned
            )
            if new_cleaned == cleaned:
                break
            cleaned = new_cleaned

        # Now filter the merged darkslategray content
        def filter_darkslategray(match):
            content = match.group(1).strip()
            # Remove if empty or too short
            if len(content) < 3:
                return ''
            # Remove if it's a known metadata header
            if re.match(r'^(Word Origin|Idiom|Thesaurus|Example Bank|Derived|Verb forms|Word Family|Collocations)', content, re.IGNORECASE):
                return ''
            # Keep everything else (it's likely part of the definition)
            return content + ' '

        cleaned = re.sub(r'<c c="darkslategray">([^<]*)</c>\s*', filter_darkslategray, cleaned)
        
        # 13. Strip dimgray content (thesaurus usage notes)
        cleaned = re.sub(r'<c c="dimgray">[^<]*</c>\s*', '', cleaned)
        
        # 14. Remove bold tags from middle of text (keep the word itself)
        cleaned = re.sub(r'<b>(' + re.escape(headword) + r')</b>', r'\1', cleaned, flags=re.IGNORECASE)
        
        # 15. Strip parentheses containing only stripped tag remnants
        cleaned = re.sub(r'\([^)]*\)', lambda m: '' if not re.sub(r'\s', '', m.group(0)[1:-1]) else m.group(0), cleaned)
        
        # 16. Strip all remaining tags
        text = re.sub(r'<[^>]+>', '', cleaned).strip()

        # 17. Clean up abbreviation markers and symbols
        text = re.sub(r'\b(?:abbr\.|symb\.)\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*(?:No\.|Fr)\.?\s*\)\s*', '', text)
        text = re.sub(r'\(\s*(?:Fr|No)\.?\s*\)', '', text)
        text = re.sub(r'\(\s*[#\*]+\s*\)', '', text)
        
        # 18. Reject thesaurus entries
        if re.match(r'^[A-Z]\s+\(', text) or re.match(r'^[A-Z]\s+(?:followed|used)', text):
            return ""
        
        # 19. Reject "Word Origin:" artifacts
        if re.search(r'Word\s*Origin', text, re.IGNORECASE):
            return ""
        
        # 20. Reject phonetic definitions (contains phonetic symbols and audio refs)
        if re.search(r'\[ðiː\]|z_\w+\.wav', text, re.IGNORECASE):
            return ""
        
        # 21. Structural Reject: Examples/Thesaurus symbols
        if re.search(r'^\s*[•↑]', text):
            return ""

        # 22. Remove orphaned or empty parentheses
        text = re.sub(r'\s*\(\s*\)\s*', ' ', text)
        text = re.sub(r'^\s*\)\s*', '', text)
        text = re.sub(r'\s*\)\s*(?=\s|$)', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 23. Fix unbalanced parentheses
        text = re.sub(r'\([^)]*$', '', text)
        text = re.sub(r'^\s*\)\s*', '', text)
        text = text.strip()
        
        # 24. Recursive Grammar Prefix Strip (but exclude words that can be definitions)
        grammar_noise = (
            r'^(noun|verb|adjective|adverb|only|before|usually|'
            r'always|passive|countable|uncountable|transitive|intransitive|'
            r'singular|plural|formal|literary|old use|or)\b'
        )
        while True:
            new_text = re.sub(grammar_noise + r'[\s,/\+]*', '', text, flags=re.IGNORECASE).strip()
            if new_text == text:
                break
            text = new_text
        
        # 25. Strip ALL CAPS headers
        text = re.sub(r'^[A-Z\s]{3,}\s+', '', text)
        text = re.sub(r'\s+[A-Z\s]{3,}$', '', text)
        
        # 26. Final Polish
        text = text.replace('↑', '').strip()
        
        # 27. Validation (lowered threshold for short but valid definitions)
        if len(text) < 3 or re.match(r'^[CUI\s,()\-+/]+$', text):
            return ""
        
        # 28. Fix casing
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        return text.strip()

    def close(self):
        self._dict = None