"""UI strings for English and Korean. English is the default language."""

LANGS = ("en", "ko")
DEFAULT_LANG = "en"

STRINGS = {
    # main window
    "btn_input": ("✎ Add keywords", "✎ 키워드 입력"),
    "btn_open": ("📂 Open file (CSV/TXT)", "📂 파일 불러오기 (CSV/TXT)"),
    "btn_reset": ("Reset lists", "목록 초기화"),
    "btn_lang": ("🌐 한국어", "🌐 English"),  # shows the language you switch *to*
    "status_ready": ("Press SPIN to draw a keyword", "스핀을 눌러 키워드를 뽑으세요"),
    "status_added": ("{source}: added {added}", "{source}: {added}개 추가"),
    "status_dup": (", skipped {dup} duplicates", ", 중복 {dup}개 건너뜀"),
    "status_spinning": ("Drumroll…", "두구두구…"),
    "status_winner": ("★  {winner}  ★", "★  당첨: {winner}  ★"),
    "status_group": ("Field: {group}", "분야: {group}"),
    "status_copied": ("(copied)", "(복사됨)"),
    "reel_empty": ("Add some keywords", "키워드를 추가하세요"),
    "opt_auto_exclude": ("Remove winners from the candidates", "당첨된 키워드는 후보에서 제외"),
    "opt_speed": ("Spin time", "회전 시간"),
    "speed_short": ("Short", "짧게"),
    "speed_normal": ("Normal", "보통"),
    "speed_long": ("Long", "길게"),
    "btn_copy": ("Copy result", "결과 복사"),
    "search": ("Search", "목록 검색"),
    "candidates": ("Candidates", "후보"),
    "excluded": ("Excluded", "제외됨"),
    "search_count": (" · {n} shown", " · 검색 {n}"),
    "btn_exclude": ("Exclude →", "제외 →"),
    "btn_delete": ("Delete", "삭제"),
    "btn_restore": ("← Restore", "← 후보로 복원"),
    "btn_restore_all": ("Restore all", "모두 복원"),
    "hint_lists": ("Double-click to exclude/restore, Delete key to remove",
                   "더블클릭으로 제외/복원, Delete 키로 삭제"),
    "history": ("Winners", "당첨 기록"),
    "btn_clear_history": ("Clear history", "기록 지우기"),
    "confirm_delete": ("Delete {n} keywords?", "{n}개 키워드를 삭제할까요?"),
    "confirm_clear_history": ("Clear the whole winner history?", "당첨 기록을 모두 지울까요?"),
    "confirm_reset": ("Clear the candidate list, the excluded list and the winner history?",
                      "후보·제외 목록과 당첨 기록을 모두 지울까요?"),
    "file_title": ("Choose keyword files", "키워드 파일 선택"),
    "ft_keywords": ("Keyword files", "키워드 파일"),
    "ft_text": ("Text", "텍스트"),
    "ft_all": ("All files", "모든 파일"),
    "err_open": ("Cannot open the file.\n{path}\n{err}", "파일을 열 수 없습니다.\n{path}\n{err}"),
    "no_keywords_found": ("No keywords found in {name}.", "{name}에서 키워드를 찾지 못했습니다."),
    # manual input dialog
    "input_title": ("Add keywords", "키워드 입력"),
    "input_hint": ("One keyword per line. (Ctrl+Enter: add, Esc: close)",
                   "한 줄에 하나씩 입력하세요. (Ctrl+Enter: 추가, Esc: 닫기)"),
    "input_commas": ("Also split on commas (,)", "쉼표(,)로도 구분"),
    "btn_add": ("Add", "추가"),
    "btn_close": ("Close", "닫기"),
    "manual_source": ("Manual input", "직접 입력"),
    # CSV import dialog
    "csv_title": ("Import CSV - {name}", "CSV 가져오기 - {name}"),
    "csv_prep": ("Preprocessing", "전처리"),
    "csv_encoding": ("Encoding: {enc}", "인코딩: {enc}"),
    "csv_delim": ("Delimiter", "구분자"),
    "delim_auto": ("Auto", "자동"),
    "delim_comma": ("Comma ,", "쉼표 ,"),
    "delim_semicolon": ("Semicolon ;", "세미콜론 ;"),
    "delim_tab": ("Tab", "탭"),
    "delim_pipe": ("Pipe |", "파이프 |"),
    "csv_skip": ("Rows to skip at the top", "상단에서 건너뛸 행"),
    "csv_header": ("Next row is a header (column names) → skip it", "그 다음 첫 행은 헤더(열 이름) → 제외"),
    "csv_drop_num": ("Drop values that are only numbers/dates", "숫자/날짜만 있는 값 제외"),
    "csv_drop_head": ("Drop values equal to the header (repeated headers)", "헤더와 같은 값(반복된 헤더) 제외"),
    "csv_exclude": ("Also exclude (comma-separated)", "추가로 제외할 값(쉼표 구분)"),
    "csv_columns": ("Columns to use as keywords", "키워드로 사용할 열"),
    "csv_raw": ("Source (grey: skipped, yellow: header)", "원본 (회색: 건너뜀, 노랑: 헤더)"),
    "csv_result": ("Keywords to import", "가져올 키워드"),
    "csv_row": ("Row", "행"),
    "csv_too_many_cols": ("… only the first {n} columns are shown", "… 열이 많아 앞의 {n}개만 표시"),
    "csv_no_cols": ("No readable columns.", "읽을 수 있는 열이 없습니다."),
    "csv_group": ("Field (group) column", "분야(그룹) 열"),
    "csv_group_hint": ("← keeps keywords of the same field apart on the reel",
                       "← 같은 분야 키워드가 릴에서 붙지 않게 배열합니다"),
    "csv_sample": ("e.g. {v}", "예: {v}"),
    "csv_empty_col": ("(empty column)", "(빈 열)"),
    "csv_count": ("{n} keywords", "{n}개"),
    "csv_count_groups": (" · {n} fields", " · 분야 {n}개"),
    "csv_count_dup": (" ({n} already in your list will be skipped)", " (이미 목록에 있는 {n}개는 건너뜀)"),
    "kind_num": ("mostly numbers", "숫자 위주"),
    "kind_date": ("mostly dates", "날짜 위주"),
    "kind_url": ("mostly links/emails", "링크/메일 위주"),
    "kind_text": ("text", "텍스트"),
    "kind_empty": ("empty", "빈 열"),
    "none": ("None", "없음"),
    "btn_import": ("Import", "가져오기"),
    "btn_cancel": ("Cancel", "취소"),
}

_lang = DEFAULT_LANG


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else DEFAULT_LANG


def get_lang():
    return _lang


def t(key, **kwargs):
    text = STRINGS[key][LANGS.index(_lang)]
    return text.format(**kwargs) if kwargs else text
