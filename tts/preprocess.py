import os
import re

def get_lang_descriptor(language):
    s = str(language).upper()
    mapping = {
        'US': 'a',
        'UK': 'b',
        'ES': 'e',
        'FR': 'f',
        'HI': 'h',
        'IT': 'i',
        'JA': 'j',
        'PT-BR': 'p',
        'ZH': 'z',
    }
    return mapping.get(s, language)

def convert_special_characters(text):
    char_map = {
        '-': '杠',
        '_': '下划线',
        '*': '星号',
        '/': '斜杠',
        '\\': '反斜杠',
        '#': '井号',
        '%': '百分号',
        '@': '艾特',
        '$': '美元符号',
        '+': '加号',
        '=': '等号',
        '℃': '摄氏度',
        '|': '竖线',
        '&': '和号',
        '^': '脱字符',
        '~': '波浪号',
        '`': '反引号',
        ':': '冒号',
        ';': '分号',
        '(': '左括号',
        ')': '右括号',
        '[': '左中括号',
        ']': '右中括号',
        '{': '左花括号',
        '}': '右花括号',
        '<': '小于号',
        '>': '大于号',
        '×': '乘号',
        '÷': '除号',
        '°': '度'
    }
    result = text
    for char, chinese in char_map.items():
        result = result.replace(char, chinese)
    return result

def convert_units(text):
    repl = [
        (re.compile(r'°C'), '摄氏度'),
        (re.compile(r'℃'), '摄氏度'),
        (re.compile(r'(?i)\bkg\b'), '千克'),
        (re.compile(r'(?i)\bg\b'), '克'),
        (re.compile(r'(?i)\bkm\b'), '公里'),
        (re.compile(r'(?i)\bcm\b'), '厘米'),
        (re.compile(r'(?i)\bmm\b'), '毫米'),
        (re.compile(r'(?i)\bm\^?2\b'), '平方米'),
        (re.compile(r'(?i)\bm\^?3\b'), '立方米'),
        (re.compile(r'(?i)\bμm\b'), '微米'),
        (re.compile(r'(?i)\bml\b'), '毫升'),
        (re.compile(r'(?i)\bL\b'), '升'),
        (re.compile(r'(?i)\bh\b'), '小时')
    ]
    result = text
    for pattern, val in repl:
        result = pattern.sub(val, result)
    return result

def convert_english_punct_to_chinese(text):
    mapping = {
        ',': '，',
        '.': '。',
        '?': '？',
        '!': '！',
        ':': '：',
        ';': '；',
        '(': '（',
        ')': '）',
        '[': '【',
        ']': '】',
        '{': '｛',
        '}': '｝',
        '<': '《',
        '>': '》',
        '/': '／'
    }
    result_chars = []
    dq_open = True
    n = len(text)
    for i, ch in enumerate(text):
        if ch == '"':
            result_chars.append('“' if dq_open else '”')
            dq_open = not dq_open
        elif ch == '\'':
            result_chars.append('’')
        elif ch == '.' and i > 0 and i < n - 1 and text[i-1].isdigit() and text[i+1].isdigit():
            result_chars.append('点')
        else:
            result_chars.append(mapping.get(ch, ch))
    return ''.join(result_chars)

def remove_linebreaks(text):
    return text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')

def split_long_text(text, max_len=150):
    strong = set('。！？!?')
    soft = set('，、,；;：:')
    sentences = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in strong:
            sentences.append(''.join(buf).strip())
            buf = []
    if buf:
        sentences.append(''.join(buf).strip())
    pieces = []
    for s in sentences:
        if len(s) <= max_len:
            pieces.append(s)
            continue
        segs = []
        start = 0
        last_soft = -1
        for i, ch in enumerate(s):
            if ch in soft:
                last_soft = i
            if i - start + 1 >= max_len:
                if last_soft != -1 and last_soft >= start:
                    cut = last_soft + 1
                    segs.append(s[start:cut].strip())
                    start = cut
                    last_soft = -1
                else:
                    cut = i
                    segs.append(s[start:cut].strip())
                    start = cut
        if start < len(s):
            segs.append(s[start:].strip())
        final = []
        for part in segs:
            if len(part) <= max_len:
                final.append(part)
            else:
                j = 0
                n = len(part)
                while j < n:
                    final.append(part[j:j+max_len].strip())
                    j += max_len
        pieces.extend(final)
    return pieces

def process_character_by_character(text):
    def format_number_chunk(num_str):
        groups = []
        n = len(num_str)
        three_digit_area_prefixes = (
            '010','020','021','022','023','024','025','027','028','029'
        )
        if (n == 18 or n == 17) and num_str.isdigit():
            groups =  [num_str[:4].replace('1', '幺'),num_str[4:6].replace('1', '幺'), num_str[6:10], num_str[10:14].replace('1', '幺'), num_str[14:18]]
        elif n == 11 and num_str[0] == '1':
            groups = [num_str[:3].replace('1', '幺'), num_str[3:7], num_str[7:]]
        elif num_str[0] == '0' and num_str.startswith(three_digit_area_prefixes):
            groups = [num_str[:3].replace('1', '幺'), num_str[3:7], num_str[7:]]
        else:
            i = 0
            while i < n:
                groups.append(num_str[i:i+4].replace('1', '幺'))
                i += 4
        spaced_groups = [' '.join(list(g)) for g in groups]
        return '，'.join(spaced_groups)

    result = []
    i = 0
    prev_token_type = 'other'
    while i < len(text):
        char = text[i]
        if char.isdigit():
            j = i
            while j < len(text) and text[j].isdigit():
                j += 1
            num_chunk = text[i:j]
            formatted = format_number_chunk(num_chunk)
            if prev_token_type in ('digit', 'letter') and (not result or (result and result[-1] != ' ')):
                result.append(' ')
            result.append(formatted)
            i = j
            prev_token_type = 'digit'
            continue
        elif char.isalpha() and ord(char) < 128:
            j = i
            while j < len(text) and text[j].isalpha() and ord(text[j]) < 128:
                j += 1
            word = text[i:j]
            if prev_token_type in ('digit', 'letter') and (not result or (result and result[-1] != ' ')):
                result.append(' ')
            result.append(word)
            i = j
            prev_token_type = 'letter'
            continue
        else:
            result.append(char)
            prev_token_type = 'other'
        i += 1
    text_result = ''.join(result)
    text_result = re.sub(r' +', ' ', text_result)
    return text_result
