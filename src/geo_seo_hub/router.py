from __future__ import annotations

import math
import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import load_registry


_NEGATION_RE = re.compile(
    r"(?:\b(?:do\s+not|don['’]?t|dont|must\s+not|should\s+not|cannot|can['’]?t|cant|"
    r"never|without|skip|avoid|no\s+(?:need|desire|wish))\b|"
    r"\bnot\b(?!\s+only\b)|\bno\b(?![-.]?\w)|"
    r"(?:请勿|不需要|不要|无需|无须|不能|不可|别|禁止|拒绝|不想|不必|不准|切勿|"
    r"不做|不进行|不创建|不生成|不开展|跳过|避免|勿))"
)
_BARE_ZH_NEGATION_RE = re.compile(
    r"不(?!\s*(?:只|仅|光|单(?!\s*独)))\s*(?:再\s*)?"
)
_HARD_CLAUSE_RE = re.compile(r"[;；。.!?！？]")
GOVERNED_ADDITIVE_CONNECTORS = (
    ("and also", r"\band\s+also\b", True),
    ("also", r"\balso\b", True),
    ("and", r"\band\b", False),
    ("plus", r"\bplus\b(?!-size\b)", False),
    ("还要", r"还要", True),
    ("也要", r"也要", True),
    ("还需", r"还需", True),
    ("同时", r"同时", True),
    ("并且", r"并且", False),
    ("以及", r"以及", False),
    ("并", r"并", False),
    ("且", r"且", False),
    ("和", r"和", False),
    ("加", r"加", False),
    ("及", r"及", False),
)
GOVERNED_SEQUENCE_CONNECTORS = (
    ("and then", r"\band\s+then\b", True),
    ("then", r"\bthen\b", True),
    ("followed by", r"\bfollowed\s+by\b", True),
    ("然后", r"然后", True),
    ("再", r"再", True),
)
_GOVERNED_ADDITIVE_PATTERN = "(?:" + "|".join(
    pattern for _, pattern, _ in GOVERNED_ADDITIVE_CONNECTORS
) + ")"
_GOVERNED_SEQUENCE_PATTERN = "(?:" + "|".join(
    pattern for _, pattern, _ in GOVERNED_SEQUENCE_CONNECTORS
) + ")"
_GOVERNED_ADDITIVE_TOKENS = frozenset(
    token for token, _, _ in GOVERNED_ADDITIVE_CONNECTORS
)
_GOVERNED_SEQUENCE_TOKENS = frozenset(
    token for token, _, _ in GOVERNED_SEQUENCE_CONNECTORS
)
_GOVERNED_SEQUENCE_EXCLUSIVITY_TOKENS = frozenset(
    token
    for token, _, preserves_exclusivity in GOVERNED_SEQUENCE_CONNECTORS
    if preserves_exclusivity
)
_GOVERNED_ADDITIVE_SCOPE_BREAKS = frozenset(
    token for token, _, breaks_negation in GOVERNED_ADDITIVE_CONNECTORS if breaks_negation
)
_GOVERNED_SINGLE_ZH_ADDITIVE_TOKENS = frozenset(
    token
    for token, _, _ in GOVERNED_ADDITIVE_CONNECTORS
    if len(token) == 1 and not token.isascii()
)
_GOVERNED_SINGLE_ZH_CONNECTOR_TOKENS = frozenset(
    token
    for token in (*_GOVERNED_ADDITIVE_TOKENS, *_GOVERNED_SEQUENCE_TOKENS)
    if len(token) == 1 and not token.isascii()
)
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?:[;；。.!?！？]|(?:,\s*)?\b(?:but|instead(?:\s+of)?|however|"
    r"rather\s+than|switch(?:ing)?\s+to)(?:\s+please)?\b|"
    rf"(?:[,，]\s*)?{_GOVERNED_SEQUENCE_PATTERN}|"
    r"(?:,\s*)?(?:and\s+)?only\b|"
    rf"(?:[,，]\s*)?{_GOVERNED_ADDITIVE_PATTERN}|,\s*(?:only|just)\b|"
    r"(?:，\s*)?(?:但是|但|改为|转而)(?:请)?|"
    r"(?:，\s*)?只|，\s*(?:只|仅|请)|请)"
)
_WORKFLOW_CONNECTOR_RE = re.compile(
    r"(?:\b(?:but|instead(?:\s+of)?|however|"
    r"rather\s+than|switch(?:ing)?\s+to)\b|"
    rf"{_GOVERNED_SEQUENCE_PATTERN}|"
    rf"{_GOVERNED_ADDITIVE_PATTERN}|"
    r"[,&+;，；、]|但是|但|改为|转而)"
)
_WORKFLOW_CONNECTOR_GAP_CHARACTERS = frozenset(",，、&+;；")
_ADDITIVE_CONNECTOR_RE = re.compile(_GOVERNED_ADDITIVE_PATTERN)
_SEMANTIC_WORKFLOW_CONNECTOR_RE = re.compile(
    rf"(?:{_GOVERNED_SEQUENCE_PATTERN}|{_GOVERNED_ADDITIVE_PATTERN}|[&+;；、])"
)
_SEQUENCE_CONNECTOR_RE = re.compile(_GOVERNED_SEQUENCE_PATTERN)
_REPLACEMENT_CONNECTOR_RE = re.compile(
    r"(?:改为|转而|只|\binstead(?:\s+of)?\b|"
    r"\brather\s+than\b|\bswitch(?:ing)?\s+to\b)"
)
_EXCLUSIVITY_LEAD_IN_RE = re.compile(r"(?:仅仅|仅|光|只)\s*")
_ENGLISH_ADDITIVE_EXCLUSIVITY_RE = re.compile(r"\bno\s+longer\s+only\s+")
_LEXICAL_POSITIVE_ZHI_RE = re.compile(
    r"不\s*(?:(?:仅(?:\s*仅)?|单(?!\s*独)|光|只)\s*(?:是\s*)?)?"
    r"只(?:\s*是)?\s*"
)
_NEGATION_FILLER_RE = re.compile(
    r"\b(?:under|any|circumstances|at|all|ever|in|way|please|just|only|really|want|"
    r"interested|rather)\b|(?:无论如何|在任何情况下|任何形式|都|仅仅|只是)"
)
MAX_ROUTE_CHARACTERS = 8_000
MAX_ROUTE_UTF8_BYTES = 16_384
_ACTION_VERB_PREFIXES = frozenset(
    {
        "build",
        "create",
        "generate",
        "make",
        "produce",
        "refine",
        "write",
        "产出",
        "创建",
        "制作",
        "制定",
        "写",
        "分发",
        "发布",
        "生成",
        "监测",
        "构建",
        "衡量",
        "输出",
    }
)
_SEQUENCE_SCOPE_TOKENS = frozenset(
    {
        "only",
        "and only",
        "just",
        "只",
        "仅",
        "请",
    }
)
GOVERNED_EN_ACTION_LEAD_INS = ("need", "want", "plan", "intend", "prepare")
GOVERNED_ACTION_OBJECT_ARTICLES = ("a", "an", "the", "一个", "个")
GOVERNED_ZH_INTENT_SUFFIX_BLOCKS = (("发布", ("会", "者")),)
_GOVERNED_EN_ACTION_LEAD_IN_PATTERN = (
    r"(?:" + "|".join(re.escape(token) for token in GOVERNED_EN_ACTION_LEAD_INS) + r")"
    r"\b\s+(?:to\b\s+)?"
)
GOVERNED_ZH_ACTION_LEAD_INS = (
    "单独",
    "仅仅",
    "需要",
    "继续",
    "打算",
    "准备",
    "页面",
    "请",
    "想",
    "去",
    "要",
    "做",
    "仅",
    "再",
    "只",
    "光",
)
_GOVERNED_ZH_ACTION_LEAD_IN_PATTERN = "(?:" + "|".join(
    r"单\s*独" if token == "单独" else re.escape(token)
    for token in GOVERNED_ZH_ACTION_LEAD_INS
) + r")\s*"
_ACTION_LEAD_IN_RE = re.compile(
    rf"(?:please\s+|{_GOVERNED_EN_ACTION_LEAD_IN_PATTERN}|"
    rf"(?:{_GOVERNED_ZH_ACTION_LEAD_IN_PATTERN}){{1,4}})"
)
_ZH_ACTION_LEAD_IN_TOKEN_RE = re.compile(_GOVERNED_ZH_ACTION_LEAD_IN_PATTERN)
_EN_ACTION_LEAD_IN_RE = re.compile(
    rf"(?:please\s+|{_GOVERNED_EN_ACTION_LEAD_IN_PATTERN})"
)
_ACTION_OBJECT_ARTICLE_RE = re.compile(
    r"(?:(?:a|an|the)\b|一个|个)\s*"
)


@dataclass(frozen=True)
class ClauseScope:
    start: int
    end: int
    negation_starts: tuple[int, ...]


@dataclass(frozen=True)
class ActionPhraseIndex:
    phrases: frozenset[str]
    intent_phrases: frozenset[str]
    start_pattern: re.Pattern[str]
    span_cache: dict[int, tuple[int, int] | None] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )


@dataclass(frozen=True)
class IntentIndex:
    patterns_by_skill: dict[str, tuple[tuple[str, re.Pattern[str]], ...]]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip())


def build_action_phrase_index(registry: dict[str, Any]) -> ActionPhraseIndex:
    """Compile every registered intent plus narrow request verb prefixes."""
    intent_phrases = {
        phrase
        for skill in registry["skills"]
        for intent in skill["intents"]
        if (phrase := _normalize(intent))
    }
    phrases = set(intent_phrases)
    phrases.update(_ACTION_VERB_PREFIXES)
    alternatives = []
    for phrase in sorted(phrases, key=lambda item: (-len(item), item)):
        suffix = r"(?![\w-])" if phrase[-1].isascii() else ""
        alternatives.append(f"(?:{re.escape(phrase)}){suffix}")
    return ActionPhraseIndex(
        phrases=frozenset(phrases),
        intent_phrases=frozenset(intent_phrases),
        start_pattern=re.compile("(?:" + "|".join(alternatives) + ")"),
    )


def build_intent_index(registry: dict[str, Any]) -> IntentIndex:
    """Compile Registry intents with stable lexical boundaries."""
    suffix_blocks = dict(GOVERNED_ZH_INTENT_SUFFIX_BLOCKS)
    patterns_by_skill = {}
    for skill in registry["skills"]:
        patterns = []
        for intent in skill["intents"]:
            phrase = _normalize(intent)
            if not phrase:
                continue
            escaped = re.escape(phrase)
            if phrase.isascii():
                source = rf"(?<![\w-]){escaped}(?![\w-])"
            else:
                blocked = suffix_blocks.get(phrase, ())
                suffix = (
                    "(?!" + "|".join(re.escape(item) for item in blocked) + ")"
                    if blocked
                    else ""
                )
                source = escaped + suffix
            patterns.append((phrase, re.compile(source)))
        patterns_by_skill[skill["id"]] = tuple(patterns)
    return IntentIndex(patterns_by_skill=patterns_by_skill)


def _quoted_or_code_spans(text: str) -> tuple[tuple[int, int], ...]:
    pairs = {'"': '"', "'": "'", "`": "`", "“": "”", "‘": "’"}
    spans = []
    cursor = 0
    while cursor < len(text):
        opening = text[cursor]
        closing = pairs.get(opening)
        if closing is None:
            cursor += 1
            continue
        if (
            opening == "'"
            and cursor > 0
            and cursor + 1 < len(text)
            and text[cursor - 1].isalnum()
            and text[cursor + 1].isalnum()
        ):
            cursor += 1
            continue
        end = cursor + 1
        while end < len(text):
            if text[end] == closing and (
                end == 0 or text[end - 1] != "\\"
            ):
                end += 1
                break
            end += 1
        spans.append((cursor, end))
        cursor = end
    return tuple(spans)


def _direct_action_after_optional_article(
    text: str,
    action_index: ActionPhraseIndex,
    start: int,
) -> re.Match[str] | None:
    if start < len(text) and text[start] == " ":
        start += 1
    action_match = action_index.start_pattern.match(text, start)
    if action_match is not None:
        return action_match
    article = _ACTION_OBJECT_ARTICLE_RE.match(text, start)
    if article is None:
        return None
    return action_index.start_pattern.match(text, article.end())


def _resolve_action_match(
    text: str,
    action_index: ActionPhraseIndex,
    action_match: re.Match[str] | None,
) -> re.Match[str] | None:
    for _ in range(4):
        if action_match is None:
            return None
        action_phrase = text[action_match.start() : action_match.end()]
        if (
            action_phrase in action_index.intent_phrases
            or action_phrase not in _ACTION_VERB_PREFIXES
        ):
            return action_match
        action_match = _direct_action_after_optional_article(
            text,
            action_index,
            action_match.end(),
        )
    return None


def _registered_intent_match(
    text: str,
    action_index: ActionPhraseIndex,
    action_match: re.Match[str] | None,
) -> re.Match[str] | None:
    if action_match is None:
        return None
    action_phrase = text[action_match.start() : action_match.end()]
    return action_match if action_phrase in action_index.intent_phrases else None


def _registered_action_span(
    text: str,
    action_index: ActionPhraseIndex,
    start: int = 0,
) -> tuple[int, int] | None:
    if start < len(text) and text[start] == " ":
        start += 1
    if start in action_index.span_cache:
        return action_index.span_cache[start]
    lexical_positive = _LEXICAL_POSITIVE_ZHI_RE.match(text, start)
    prefix_end = lexical_positive.end() if lexical_positive else start
    direct_match = action_index.start_pattern.match(text, prefix_end)
    action_match = _registered_intent_match(text, action_index, direct_match)
    if action_match is not None:
        result = action_match.span()
        action_index.span_cache[start] = result
        return result
    article = _ACTION_OBJECT_ARTICLE_RE.match(text, prefix_end)
    if article is not None:
        action_match = _registered_intent_match(
            text,
            action_index,
            action_index.start_pattern.match(text, article.end()),
        )
        if action_match is not None:
            result = action_match.span()
            action_index.span_cache[start] = result
            return result
    action_match = _resolve_action_match(
        text,
        action_index,
        direct_match,
    )
    if action_match is not None:
        result = action_match.span()
        action_index.span_cache[start] = result
        return result
    english_lead_in = _EN_ACTION_LEAD_IN_RE.match(text, prefix_end)
    if english_lead_in is not None:
        action_match = _resolve_action_match(
            text,
            action_index,
            _direct_action_after_optional_article(
                text,
                action_index,
                english_lead_in.end(),
            ),
        )
        if action_match is not None:
            result = action_match.span()
            action_index.span_cache[start] = result
            return result
    cursor = prefix_end
    for _ in range(4):
        token = _ZH_ACTION_LEAD_IN_TOKEN_RE.match(text, cursor)
        if token is None:
            break
        cursor = token.end()
        action_match = _resolve_action_match(
            text,
            action_index,
            _direct_action_after_optional_article(text, action_index, cursor),
        )
        if action_match is not None:
            result = action_match.span()
            action_index.span_cache[start] = result
            return result
    action_index.span_cache[start] = None
    return None


def _raw_replacement_spans(
    text: str,
    action_index: ActionPhraseIndex,
    lexical_positive_spans: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    lexical_positive_index = 0
    spans = []
    for match in _REPLACEMENT_CONNECTOR_RE.finditer(text):
        if match.group() == "只":
            while (
                lexical_positive_index < len(lexical_positive_spans)
                and lexical_positive_spans[lexical_positive_index][1] <= match.start()
            ):
                lexical_positive_index += 1
            if (
                lexical_positive_index < len(lexical_positive_spans)
                and lexical_positive_spans[lexical_positive_index][0]
                <= match.start()
                < lexical_positive_spans[lexical_positive_index][1]
            ):
                continue
            if _registered_action_span(text, action_index, match.end()) is None:
                continue
        spans.append(match.span())
    return tuple(spans)


def _exclusivity_exception_starts(
    text: str,
    action_index: ActionPhraseIndex,
    candidates: tuple[tuple[int, int], ...],
    connector_spans: tuple[tuple[int, int], ...],
    replacement_spans: tuple[tuple[int, int], ...],
    hard_clause_spans: tuple[tuple[int, int], ...],
    gap_prefix: tuple[int, ...],
) -> tuple[frozenset[int], frozenset[int]]:
    exceptions: set[int] = set()
    releases: set[int] = set()
    connector_index = 0
    replacement_index = 0
    hard_clause_index = 0
    for negation_start, action_search_start in candidates:
        action_span = _registered_action_span(text, action_index, action_search_start)
        if action_span is None:
            continue
        action_end = action_span[1]
        while connector_index < len(connector_spans):
            connector_start, connector_end = connector_spans[connector_index]
            if connector_start < action_end:
                connector_index += 1
                continue
            connector_token = _normalize(text[connector_start:connector_end])
            if (
                connector_token in _GOVERNED_SINGLE_ZH_CONNECTOR_TOKENS
                and gap_prefix[action_end] != gap_prefix[connector_start]
            ):
                connector_index += 1
                continue
            break
        while (
            replacement_index < len(replacement_spans)
            and replacement_spans[replacement_index][0] < action_end
        ):
            replacement_index += 1
        while (
            hard_clause_index < len(hard_clause_spans)
            and hard_clause_spans[hard_clause_index][0] < action_end
        ):
            hard_clause_index += 1
        connector_start = (
            connector_spans[connector_index][0]
            if connector_index < len(connector_spans)
            else len(text) + 1
        )
        replacement_start = (
            replacement_spans[replacement_index][0]
            if replacement_index < len(replacement_spans)
            else len(text) + 1
        )
        hard_clause_start = (
            hard_clause_spans[hard_clause_index][0]
            if hard_clause_index < len(hard_clause_spans)
            else len(text) + 1
        )
        if connector_start < replacement_start and connector_start < hard_clause_start:
            exceptions.add(negation_start)
            releases.add(connector_start)
    return frozenset(exceptions), frozenset(releases)


def _connector_starts_scope(
    text: str,
    boundary: re.Match[str],
    scope_start: int,
    negation_spans: tuple[tuple[int, int], ...],
    negation_starts: tuple[int, ...],
    object_prefix: tuple[int, ...],
    negation_action_ends: dict[int, int],
    gap_prefix: tuple[int, ...],
    exclusivity_release_starts: frozenset[int],
    action_index: ActionPhraseIndex,
) -> bool:
    token = _normalize(boundary.group().strip(" ,，"))
    right = text[boundary.end() :].lstrip()
    if _registered_action_span(text, action_index, boundary.end()) is None:
        return False
    is_additive = token in _GOVERNED_ADDITIVE_TOKENS
    is_sequence = token in _GOVERNED_SEQUENCE_TOKENS
    if token in _SEQUENCE_SCOPE_TOKENS or is_additive or is_sequence:
        if token in {"only", "and only"}:
            left = text[max(0, boundary.start() - 12) : boundary.start()]
            if re.search(r"(?:not|no\s+longer)\s+$", left):
                return False
    if (
        token.startswith(("however", "instead"))
        and boundary.group().lstrip().startswith((",", "，"))
        and right.startswith((",", "，"))
    ):
        return False
    if boundary.start() in exclusivity_release_starts:
        return True
    negation_index = bisect_right(negation_starts, boundary.start() - 1) - 1
    if negation_index < 0 or negation_spans[negation_index][0] < scope_start:
        return True
    if token in _GOVERNED_SINGLE_ZH_CONNECTOR_TOKENS:
        negation_start = negation_spans[negation_index][0]
        action_end = negation_action_ends.get(negation_start)
        if (
            action_end is not None
            and gap_prefix[action_end] != gap_prefix[boundary.start()]
        ):
            return False
    if is_additive and token not in _GOVERNED_ADDITIVE_SCOPE_BREAKS:
        return False
    after_negation = negation_spans[negation_index][1]
    return object_prefix[boundary.start()] > object_prefix[after_negation]


def _parse_clause_scopes(
    text: str,
    action_index: ActionPhraseIndex,
    gap_prefix: tuple[int, ...],
    lexical_positive_spans: tuple[tuple[int, int], ...],
) -> tuple[ClauseScope, ...]:
    additive_spans = tuple(
        match.span()
        for match in _ADDITIVE_CONNECTOR_RE.finditer(text)
        if _registered_action_span(text, action_index, match.end()) is not None
    )
    sequence_spans = tuple(
        match.span()
        for match in _SEQUENCE_CONNECTOR_RE.finditer(text)
        if _normalize(match.group()) in _GOVERNED_SEQUENCE_EXCLUSIVITY_TOKENS
        and _registered_action_span(text, action_index, match.end()) is not None
    )
    exclusivity_connector_spans = tuple(sorted((*additive_spans, *sequence_spans)))
    replacement_spans = _raw_replacement_spans(
        text,
        action_index,
        lexical_positive_spans,
    )
    hard_clause_spans = tuple(match.span() for match in _HARD_CLAUSE_RE.finditer(text))
    bare_negation_matches = tuple(_BARE_ZH_NEGATION_RE.finditer(text))
    chinese_candidates = tuple(
        (match.start(), match.end())
        for match in bare_negation_matches
        if match.group().replace(" ", "") == "不再"
        and _EXCLUSIVITY_LEAD_IN_RE.match(text, match.end()) is not None
    )
    english_candidates = tuple(
        match.span() for match in _ENGLISH_ADDITIVE_EXCLUSIVITY_RE.finditer(text)
    )
    exclusivity_exception_starts, exclusivity_release_starts = (
        _exclusivity_exception_starts(
            text,
            action_index,
            tuple(sorted((*chinese_candidates, *english_candidates))),
            exclusivity_connector_spans,
            replacement_spans,
            hard_clause_spans,
            gap_prefix,
        )
    )
    exclusivity_candidates = tuple(
        sorted((*chinese_candidates, *english_candidates))
    )
    exclusivity_action_ends = {
        negation_start: action_span[1]
        for negation_start, action_search_start in exclusivity_candidates
        if negation_start in exclusivity_exception_starts
        and (
            action_span := _registered_action_span(
                text,
                action_index,
                action_search_start,
            )
        )
        is not None
    }
    negation_action_ends: dict[int, int] = {}
    for action_end in exclusivity_action_ends.values():
        negation_action_ends[action_end] = action_end
    static_negation_spans_list: list[tuple[int, int]] = []
    for match in _NEGATION_RE.finditer(text):
        if match.start() in exclusivity_exception_starts:
            continue
        action_span = _registered_action_span(text, action_index, match.end())
        static_negation_spans_list.append(
            (match.start(), action_span[0] if action_span is not None else match.end())
        )
        if action_span is not None:
            negation_action_ends[match.start()] = action_span[1]
    static_negation_spans = tuple(static_negation_spans_list)
    bare_negation_spans: list[tuple[int, int]] = []
    static_index = 0
    for match in bare_negation_matches:
        if match.start() in exclusivity_exception_starts:
            continue
        while (
            static_index < len(static_negation_spans)
            and static_negation_spans[static_index][1] <= match.start()
        ):
            static_index += 1
        if (
            static_index < len(static_negation_spans)
            and static_negation_spans[static_index][0] <= match.start()
            < static_negation_spans[static_index][1]
        ):
            continue
        action_span = _registered_action_span(text, action_index, match.end())
        if action_span is None:
            continue
        bare_negation_spans.append((match.start(), action_span[0]))
        negation_action_ends[match.start()] = action_span[1]
    exclusivity_tail_spans = tuple(
        (action_end, action_end)
        for action_end in exclusivity_action_ends.values()
    )
    negation_spans = tuple(
        sorted(
            (
                *static_negation_spans,
                *bare_negation_spans,
                *exclusivity_tail_spans,
            )
        )
    )
    negation_starts = tuple(span[0] for span in negation_spans)
    ignored = bytearray(len(text))
    filler_spans = tuple(match.span() for match in _NEGATION_FILLER_RE.finditer(text))
    for start, end in (*negation_spans, *filler_spans):
        ignored[start:end] = b"\x01" * (end - start)
    prefix = [0]
    for index, character in enumerate(text):
        prefix.append(prefix[-1] + int(character.isalpha() and not ignored[index]))
    object_prefix = tuple(prefix)
    boundaries: list[int] = [0]
    scope_start = 0
    for boundary in _CLAUSE_BOUNDARY_RE.finditer(text):
        if _HARD_CLAUSE_RE.fullmatch(boundary.group()) or _connector_starts_scope(
            text,
            boundary,
            scope_start,
            negation_spans,
            negation_starts,
            object_prefix,
            negation_action_ends,
            gap_prefix,
            exclusivity_release_starts,
            action_index,
        ):
            scope_start = boundary.end()
            boundaries.append(scope_start)
    boundaries.append(len(text) + 1)
    scopes = []
    for start, end in zip(boundaries, boundaries[1:]):
        left = bisect_right(negation_starts, start - 1)
        right = bisect_right(negation_starts, end - 1)
        negations = negation_starts[left:right]
        scopes.append(ClauseScope(start=start, end=end, negation_starts=negations))
    return tuple(scopes)


def _positive_intent_spans(
    text: str,
    pattern: re.Pattern[str],
    scopes: tuple[ClauseScope, ...],
    ignored_spans: tuple[tuple[int, int], ...],
    lexical_positive_action_starts: frozenset[int],
) -> list[tuple[int, int]]:
    scope_starts = tuple(scope.start for scope in scopes)
    ignored_starts = tuple(span[0] for span in ignored_spans)
    spans = []
    for match in pattern.finditer(text):
        ignored_index = bisect_right(ignored_starts, match.start()) - 1
        if (
            ignored_index >= 0
            and ignored_spans[ignored_index][1] > match.start()
        ):
            continue
        scope = scopes[bisect_right(scope_starts, match.start()) - 1]
        if (
            match.start() in lexical_positive_action_starts
            or not any(start < match.start() for start in scope.negation_starts)
        ):
            spans.append(match.span())
    return spans


def _analyze_skill_intents(
    text: str,
    intent_patterns: tuple[tuple[str, re.Pattern[str]], ...],
    scopes: tuple[ClauseScope, ...],
    ignored_spans: tuple[tuple[int, int], ...],
    lexical_positive_action_starts: frozenset[int],
) -> tuple[int, list[tuple[int, int]]]:
    score = 0
    skill_spans: list[tuple[int, int]] = []
    for phrase, pattern in intent_patterns:
        spans = _positive_intent_spans(
            text,
            pattern,
            scopes,
            ignored_spans,
            lexical_positive_action_starts,
        )
        if spans:
            score += max(1, len(phrase))
            skill_spans.extend(spans)
    return score, skill_spans


def _workflow_matches(
    recipe: dict[str, Any],
    spans_by_skill: dict[str, list[tuple[int, int]]],
    connector_spans: tuple[tuple[int, int, int, int, str], ...],
    gap_prefix: tuple[int, ...],
) -> bool:
    def ordered_pair_matches(first_id: str, second_id: str) -> bool:
        first_ends = sorted(span[1] for span in spans_by_skill.get(first_id, []))
        second_starts = {span[0] for span in spans_by_skill.get(second_id, [])}
        if not first_ends or not second_starts:
            return False
        for connector_start, _, action_start, _, token in connector_spans:
            first_index = bisect_right(first_ends, connector_start) - 1
            if (
                first_index >= 0
                and action_start in second_starts
                and (
                    token not in _GOVERNED_SINGLE_ZH_CONNECTOR_TOKENS
                    or gap_prefix[first_ends[first_index]] == gap_prefix[connector_start]
                )
            ):
                return True
        return False

    steps_by_id = {step["id"]: step for step in recipe["steps"]}
    if any(not spans_by_skill.get(skill_id) for skill_id in recipe["required_skills"]):
        return False
    return all(
        ordered_pair_matches(steps_by_id[parent_id]["skill_id"], step["skill_id"])
        for step in recipe["steps"]
        for parent_id in step["depends_on"]
    )


def _workflow_connector_spans(
    text: str,
    action_index: ActionPhraseIndex,
) -> tuple[tuple[int, int, int, int, str], ...]:
    spans = []
    for match in _WORKFLOW_CONNECTOR_RE.finditer(text):
        action_span = _registered_action_span(text, action_index, match.end())
        if action_span is not None:
            token = _normalize(match.group().strip(" ,，"))
            spans.append(
                (
                    match.start(),
                    match.end(),
                    action_span[0],
                    action_span[1],
                    token,
                )
            )
    return tuple(spans)


def _workflow_gap_prefix(text: str) -> tuple[int, ...]:
    prefix = [0]
    for character in text:
        prefix.append(
            prefix[-1]
            + int(
                not character.isspace()
                and character not in _WORKFLOW_CONNECTOR_GAP_CHARACTERS
            )
        )
    return tuple(prefix)


def _semantic_scope_assessments(
    text: str,
    scopes: tuple[ClauseScope, ...],
    spans_by_skill: dict[str, list[tuple[int, int]]],
    registry: dict[str, Any],
    scorer: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    skills = [skill for skill in registry["skills"] if skill["id"] != "geo"]
    skill_ids = [skill["id"] for skill in skills]
    accepted: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    try:
        for scope in scopes:
            if scope.negation_starts:
                continue
            has_lexical_match = any(
                scope.start <= start < scope.end
                for skill_id, spans in spans_by_skill.items()
                if skill_id != "geo"
                for start, _ in spans
            )
            if has_lexical_match:
                continue
            clause = text[scope.start:scope.end].strip(" ,，;；。")
            if not clause:
                continue
            raw_scores = scorer.score(clause, skill_ids)
            unknown = sorted(set(raw_scores) - set(skill_ids))
            if unknown:
                raise ValueError(f"semantic scorer returned unknown Skill IDs: {unknown}")
            ranked: list[tuple[float, int, dict[str, Any]]] = []
            for index, skill in enumerate(skills):
                value = raw_scores.get(skill["id"], 0.0)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not 0.0 <= float(value) <= 1.0
                ):
                    raise ValueError(f"semantic score is invalid for {skill['id']}")
                ranked.append((float(value), index, skill))
            ranked.sort(key=lambda item: (-item[0], item[1]))
            top_score, _, top_skill = ranked[0]
            threshold = float(top_skill["routing"]["semantic_threshold"])
            if top_score < threshold:
                continue
            second_score, _, second_skill = ranked[1]
            second_threshold = float(second_skill["routing"]["semantic_threshold"])
            margin = float(top_skill["routing"]["ambiguity_margin"])
            assessment = {
                "scope_start": scope.start,
                "scope_end": scope.end,
                "skill_id": top_skill["id"],
                "score": top_score,
                "threshold_version": top_skill["routing"]["threshold_version"],
                "alternatives": [],
            }
            if second_score >= second_threshold and top_score - second_score < margin:
                assessment["alternatives"] = [second_skill["id"]]
                ambiguous.append(assessment)
            else:
                accepted.append(assessment)
    except Exception as exc:
        return [], [], f"{type(exc).__name__}: semantic scorer unavailable"
    return accepted, ambiguous, None


def _semantic_clause_scopes(text: str) -> tuple[ClauseScope, ...]:
    boundaries = list(_CLAUSE_BOUNDARY_RE.finditer(text))
    spans: list[tuple[int, int]] = []
    start = 0
    for boundary in boundaries:
        if boundary.start() > start:
            spans.append((start, boundary.start()))
        start = boundary.end()
    if start < len(text):
        spans.append((start, len(text)))
    if not spans:
        spans.append((0, len(text)))
    scopes = []
    for scope_start, scope_end in spans:
        negations = tuple(
            scope_start + match.start()
            for match in _NEGATION_RE.finditer(text[scope_start:scope_end])
        )
        scopes.append(
            ClauseScope(
                start=scope_start,
                end=scope_end,
                negation_starts=negations,
            )
        )
    return tuple(scopes)


def _ordered_intent_ids(
    spans_by_skill: dict[str, list[tuple[int, int]]],
    semantic_matches: list[dict[str, Any]],
) -> list[str]:
    events = [
        (start, skill_id)
        for skill_id, spans in spans_by_skill.items()
        if skill_id != "geo"
        for start, _ in spans
    ]
    events.extend(
        (item["scope_start"], item["skill_id"])
        for item in semantic_matches
    )
    ordered: list[str] = []
    for _, skill_id in sorted(events, key=lambda item: (item[0], item[1])):
        if skill_id not in ordered:
            ordered.append(skill_id)
    return ordered


def _connected_lexical_intent_ids(
    spans_by_skill: dict[str, list[tuple[int, int]]],
    connector_spans: tuple[tuple[int, int, int, int, str], ...],
    gap_prefix: tuple[int, ...],
) -> set[str]:
    connected: set[str] = set()
    for connector_start, _, action_start, _, token in connector_spans:
        targets = {
            skill_id
            for skill_id, spans in spans_by_skill.items()
            if skill_id != "geo" and any(start == action_start for start, _ in spans)
        }
        for source_id, spans in spans_by_skill.items():
            if source_id == "geo" or source_id in targets:
                continue
            source_ends = [end for _, end in spans if end <= connector_start]
            if not source_ends:
                continue
            nearest_end = max(source_ends)
            if (
                token in _GOVERNED_SINGLE_ZH_CONNECTOR_TOKENS
                and gap_prefix[nearest_end] != gap_prefix[connector_start]
            ):
                continue
            connected.add(source_id)
            connected.update(targets)
    return connected


def route(
    text: str,
    registry_path: Path | None = None,
    *,
    semantic_scorer: Any | None = None,
    hybrid_scorer: Any | None = None,
) -> dict[str, Any]:
    """Select the best registry route and expose its implementation status."""
    if len(text) > MAX_ROUTE_CHARACTERS or len(text.encode("utf-8")) > MAX_ROUTE_UTF8_BYTES:
        raise ValueError(
            "Route text exceeds 8000 characters or 16384 UTF-8 bytes"
        )
    normalized = _normalize(text)
    if not normalized:
        raise ValueError("Route text must not be empty")

    registry = load_registry(registry_path)
    action_index = build_action_phrase_index(registry)
    intent_index = build_intent_index(registry)
    workflow_gap_prefix = _workflow_gap_prefix(normalized)
    lexical_positive_spans = tuple(
        match.span() for match in _LEXICAL_POSITIVE_ZHI_RE.finditer(normalized)
    )
    lexical_positive_action_starts = frozenset(
        action_span[0]
        for lexical_start, _ in lexical_positive_spans
        if (
            action_span := _registered_action_span(
                normalized,
                action_index,
                lexical_start,
            )
        )
        is not None
    )
    scopes = _parse_clause_scopes(
        normalized,
        action_index,
        workflow_gap_prefix,
        lexical_positive_spans,
    )
    ignored_spans = _quoted_or_code_spans(normalized)
    analyses = {
        skill["id"]: _analyze_skill_intents(
            normalized,
            intent_index.patterns_by_skill[skill["id"]],
            scopes,
            ignored_spans,
            lexical_positive_action_starts,
        )
        for skill in registry["skills"]
    }
    ranked = [
        (analyses[skill["id"]][0], index, skill)
        for index, skill in enumerate(registry["skills"])
    ]
    scores = {skill["id"]: score for score, _, skill in ranked}
    spans_by_skill = {skill_id: analysis[1] for skill_id, analysis in analyses.items()}
    semantic_matches: list[dict[str, Any]] = []
    semantic_ambiguities: list[dict[str, Any]] = []
    semantic_error = None
    if hybrid_scorer is not None:
        semantic_matches, semantic_ambiguities, semantic_error = _semantic_scope_assessments(
            normalized,
            _semantic_clause_scopes(normalized),
            spans_by_skill,
            registry,
            hybrid_scorer,
        )
    semantic_by_skill = {
        item["skill_id"]: item
        for item in semantic_matches
    }
    semantic_unavailable = [
        item
        for item in semantic_matches
        if next(skill for skill in registry["skills"] if skill["id"] == item["skill_id"])["status"] != "active"
    ]
    ordered_intents = _ordered_intent_ids(spans_by_skill, semantic_matches)
    connector_spans = _workflow_connector_spans(normalized, action_index)
    connected_lexical_intents = _connected_lexical_intent_ids(
        spans_by_skill,
        connector_spans,
        workflow_gap_prefix,
    )
    planned_ranked = [
        item
        for item in ranked
        if item[0] > 0 and item[2]["status"] != "active"
    ]
    active_stage_matches = {
        skill["id"]
        for skill in registry["skills"]
        if skill["id"] != "geo" and skill["status"] == "active" and scores.get(skill["id"], 0) > 0
    }
    active_stage_matches.update(
        item["skill_id"]
        for item in semantic_matches
        if next(skill for skill in registry["skills"] if skill["id"] == item["skill_id"])["status"] == "active"
    )
    matched_recipes = [] if planned_ranked or semantic_unavailable or semantic_ambiguities else [
        recipe
        for recipe in registry["workflows"]
        if set(recipe["required_skills"]) == active_stage_matches
        and (
            _workflow_matches(recipe, spans_by_skill, connector_spans, workflow_gap_prefix)
            or (
                bool(semantic_matches)
                and _SEMANTIC_WORKFLOW_CONNECTOR_RE.search(normalized) is not None
                and ordered_intents == recipe["required_skills"]
            )
        )
    ]
    workflow = None
    if len(matched_recipes) == 1:
        matched = matched_recipes[0]
        workflow = {
            "id": matched["id"],
            "status": matched["status"],
            "runnable": matched["status"] == "active",
            "steps": [dict(step) for step in matched["steps"]],
        }
    semantic_selected = None
    if semantic_ambiguities:
        semantic_selected = semantic_ambiguities[0]
    elif semantic_unavailable:
        semantic_selected = semantic_unavailable[0]
    elif len({item["skill_id"] for item in semantic_matches}) == 1:
        semantic_selected = semantic_matches[0]

    if planned_ranked:
        ranked = planned_ranked
    elif any(score > 0 and skill["id"] != "geo" for score, _, skill in ranked):
        ranked = [item for item in ranked if item[2]["id"] != "geo"]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    top_score = ranked[0][0]
    if semantic_selected is not None and (top_score == 0 or semantic_selected in semantic_unavailable or semantic_ambiguities):
        selected = next(
            skill
            for skill in registry["skills"]
            if skill["id"] == semantic_selected["skill_id"]
        )
        alternatives = list(semantic_selected["alternatives"])
        reason = f"Matched semantic intent for {selected['id']}."
    elif top_score == 0:
        selected = next(skill for skill in registry["skills"] if skill["id"] == "geo")
        alternatives: list[str] = []
        reason = "No in-domain intent met the routing threshold."
    else:
        selected = ranked[0][2]
        alternatives = [
            item[2]["id"] for item in ranked[1:] if item[0] == top_score and item[0] > 0
        ]
        reason = f"Matched registered intent terms for {selected['id']}."

    if workflow is not None:
        first_skill_id = workflow["steps"][0]["skill_id"]
        selected = next(skill for skill in registry["skills"] if skill["id"] == first_skill_id)
        alternatives = []

    distinct_intents = list(dict.fromkeys(ordered_intents))
    if workflow is not None:
        decision_type = "workflow" if workflow["status"] == "active" else "unavailable"
    elif selected["status"] != "active":
        decision_type = "unavailable"
    elif semantic_ambiguities or (
        len(distinct_intents) > 1
        and (bool(semantic_matches) or len(connected_lexical_intents) > 1)
    ):
        decision_type = "clarify"
    elif top_score == 0 and semantic_selected is None:
        decision_type = "abstain"
    else:
        decision_type = "single_skill"

    runnable = (
        selected["status"] == "active"
        and bool(selected["entry"])
        and (workflow is None or workflow["runnable"])
        and decision_type in {"single_skill", "workflow"}
    )
    if runnable:
        suggestion = None
    elif workflow is not None and workflow["status"] != "active":
        suggestion = None
        reason = (
            f"Matched workflow {workflow['id']}, but its status is "
            f"{workflow['status']}; execution is disabled."
        )
    elif decision_type == "clarify":
        suggestion = None
        reason = "Multiple plausible intents require clarification before execution."
    elif decision_type == "abstain":
        suggestion = None
        reason = "No in-domain intent met the routing threshold; execution is disabled."
    else:
        suggestion = selected.get("nearest_active", "geo-discover")
        reason += f" Stage status is {selected['status']}; no runnable entry is registered."

    result = {
        "protocol_version": registry["protocol_version"],
        "skill_id": selected["id"],
        "status": selected["status"],
        "runnable": runnable,
        "entry": selected["entry"],
        "reason": reason,
        "suggestion": suggestion,
        "alternatives": alternatives,
    }
    decision_alternatives = list(alternatives)
    if decision_type == "clarify" and len(distinct_intents) > 1:
        decision_alternatives = [
            skill_id for skill_id in distinct_intents if skill_id != selected["id"]
        ]
    semantic_evidence = semantic_by_skill.get(selected["id"])
    if semantic_evidence is None and semantic_ambiguities:
        semantic_evidence = semantic_ambiguities[0]
    if decision_type == "abstain":
        matched_intents: list[str] = []
    elif workflow is not None:
        matched_intents = list(workflow_step["skill_id"] for workflow_step in workflow["steps"])
    elif distinct_intents:
        matched_intents = distinct_intents
    else:
        matched_intents = [selected["id"]]
    if workflow is not None and not workflow["runnable"]:
        uncovered_intents = matched_intents[1:]
    elif decision_type == "clarify":
        uncovered_intents = decision_alternatives
    else:
        uncovered_intents = []
    result["decision"] = {
        "type": decision_type,
        "matched_intents": matched_intents,
        "uncovered_intents": uncovered_intents,
        "score": semantic_evidence["score"] if semantic_evidence is not None else None,
        "threshold_version": (
            semantic_evidence["threshold_version"]
            if semantic_evidence is not None
            else f"lexical-registry-{registry['registry_version']}"
        ),
        "alternatives": decision_alternatives,
    }
    if semantic_error is not None:
        result["decision"]["semantic_status"] = "unavailable"
    if workflow is not None and not workflow["runnable"]:
        matched = next(item for item in matched_recipes if item["id"] == workflow["id"])
        result["required_inputs"] = list(matched["required_inputs"])
        result["closest_v0_artifact"] = matched["closest_v0_artifact"]
    elif not runnable and selected["status"] != "active":
        result["required_inputs"] = list(selected["required_inputs"])
        result["closest_v0_artifact"] = selected["closest_v0_artifact"]
    if workflow is not None:
        result["workflow"] = workflow
        if runnable:
            result["reason"] = f"Matched exact multi-intent recipe {workflow['id']}."
    if semantic_scorer is not None:
        from .control.routing import build_shadow_assessment

        try:
            result["shadow"] = build_shadow_assessment(
                normalized,
                registry,
                result,
                semantic_scorer,
            )
        except Exception as exc:
            result["shadow"] = {
                "mode": "shadow",
                "status": "unavailable",
                "production_skill_id": result["skill_id"],
                "shadow_skill_id": None,
                "disagreed": False,
                "decision_reason": f"Shadow scoring unavailable: {type(exc).__name__}.",
                "candidates": [],
            }
    return result
