from dataclasses import dataclass
import keyword
import re


FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
UNCLOSED_FENCE_RE = re.compile(r"```")
DEF_OR_CLASS_RE = re.compile(
    r"(?:^|\n|\s)(?:def\s+[a-zA-Z_]\w*\s*\(|class\s+[a-zA-Z_]\w*\s*[:\(]|lambda\s+[^:\n]+:)",
    re.MULTILINE,
)
DIRECT_RETURN_CODE_RE = re.compile(
    r"(?:^|\n)\s*return\s+[^\n]{2,}",
    re.MULTILINE,
)
BACKTICK_RETURN_EXPR_RE = re.compile(
    r"`\s*return\s+[^`\n]{2,}`",
)
INLINE_RETURN_EXPR_RE = re.compile(
    r"(?:[:=]\s*return\s+[a-zA-Z0-9_\[\(\{-]+|\breturn\s+(?:[a-zA-Z_]\w*\s*\([^)\n]*\)|[a-zA-Z_]\w*\s*(?:[+\-*/%<>=!]+)\s*[a-zA-Z0-9_(\[]+|\[[^\]\n]+\s+for\s+[a-zA-Z_]\w*\s+in\s+))",
    re.IGNORECASE,
)
MULTILINE_PYTHON_STATEMENTS_RE = re.compile(
    r"(?:^|\n)\s*(?:for\s+\w+\s+in\s+.+:|while\s+.+:|if\s+.+:\s*\n\s+(?:return|total|result|count))",
    re.MULTILINE,
)
INDENTED_CODE_BLOCK_RE = re.compile(
    r"(?:^|\n)[ \t]{4,}(?:[a-zA-Z_]\w*\s*(?:=|\+=|-=|\*=|//=)|return\s+|if\s+|for\s+|while\s+).+\n[ \t]{4,}(?:[a-zA-Z_]\w*\s*(?:=|\+=|-=|\*=|//=)|return\s+|if\s+|for\s+|while\s+).+",
    re.MULTILINE,
)
INLINE_SOLUTION_REPLACEMENT_RE = re.compile(
    r"(?:đổi\s+thành|sửa\s+thành|thay\s+bằng|viết\s+là|dùng\s+lệnh|bằng\s+lệnh)\s*[:`]?\s*`?(?:return\s+|def\s+|[a-zA-Z_]\w*\s*=[^=])",
    re.IGNORECASE,
)
PROMPT_OVERRIDE_ECHO_RE = re.compile(
    r"(?:SYSTEM PROMPT|Bỏ qua quy tắc trên|dưới đây là lời giải hoàn chỉnh|đáp án hoàn chỉnh là)",
    re.IGNORECASE,
)
IDENTIFIER_TOKEN_RE = re.compile(
    r"[a-zA-Z_]\w*|\d+|==|!=|<=|>=|\+=|-=|\*=|//=|[+\-*/%<>]"
)
# Tách các cụm mã ASCII khỏi các từ văn xuôi tiếng Việt có dấu
VIETNAMESE_PROSE_SPLIT_RE = re.compile(r"[^\x00-\x7F]+")

PYTHON_STOPWORDS = set(keyword.kwlist) | {
    "self",
    "None",
    "True",
    "False",
    "range",
    "len",
}


@dataclass(frozen=True)
class GuardrailCheckResult:
    is_leaked: bool
    reasons: list[str]
    token_overlap: float | None = None


def compute_code_token_overlap(
    candidate_text: str,
    reference_code: str,
    *,
    function_name: str | None = None,
) -> float:
    """Tính tỷ lệ trùng lặp token và cấu trúc bigram liền kề giữa phản hồi LLM và lời giải chuẩn."""
    ref_lines = [
        line.strip()
        for line in reference_code.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    # Bỏ dòng khai báo chữ ký hàm `def func(...):` để tránh dương tính giả vì nhắc tên hàm/tham số
    body_lines = [
        line
        for line in ref_lines
        if not (function_name and line.startswith(f"def {function_name}"))
        and not line.startswith("def ")
    ]
    target_source = "\n".join(body_lines) if body_lines else "\n".join(ref_lines)
    ref_tokens = [
        tok
        for tok in IDENTIFIER_TOKEN_RE.findall(target_source)
        if tok not in PYTHON_STOPWORDS and tok != function_name
    ]
    if not ref_tokens:
        return 0.0

    cand_tokens = set(IDENTIFIER_TOKEN_RE.findall(candidate_text))
    unigram_matched = sum(1 for tok in ref_tokens if tok in cand_tokens)
    unigram_ratio = unigram_matched / len(ref_tokens)

    # Trích xuất các cặp bigram mã nguồn trong lời giải chuẩn
    ref_bigrams = [
        (ref_tokens[i], ref_tokens[i + 1]) for i in range(len(ref_tokens) - 1)
    ]
    if not ref_bigrams:
        return round(unigram_ratio, 4)

    # Tách văn bản ứng viên theo các từ tiếng Việt có dấu để chỉ ghép bigram trong cùng một cụm biểu thức mã
    cand_bigrams: set[tuple[str, str]] = set()
    for segment in VIETNAMESE_PROSE_SPLIT_RE.split(candidate_text):
        seg_tokens = [
            tok
            for tok in IDENTIFIER_TOKEN_RE.findall(segment)
            if tok not in PYTHON_STOPWORDS and tok != function_name
        ]
        for i in range(len(seg_tokens) - 1):
            cand_bigrams.add((seg_tokens[i], seg_tokens[i + 1]))

    bigram_matched = sum(1 for bg in ref_bigrams if bg in cand_bigrams)
    bigram_ratio = bigram_matched / len(ref_bigrams)

    # Kết hợp tỷ lệ từ đơn (40%) và tỷ lệ cụm biểu thức liền kề (60%) để chống dương tính giả trên bài ngắn
    combined_ratio = 0.4 * unigram_ratio + 0.6 * bigram_ratio
    return round(combined_ratio, 4)


def check_output_guardrail(
    raw_text: str | None,
    *,
    reference_code: str | None = None,
    function_name: str | None = None,
    token_overlap_threshold: float = 0.75,
) -> GuardrailCheckResult:
    """Kiểm duyệt đầu ra LLM bằng Regex, biểu thức lệnh trả về và Token/Bigram Overlap (Vận hành + Benchmark)."""
    if raw_text is None or not raw_text.strip():
        return GuardrailCheckResult(is_leaked=True, reasons=["empty_response"])

    cleaned = raw_text.strip()
    reasons: list[str] = []

    if len(cleaned) < 12:
        reasons.append("response_too_short")

    if FENCED_CODE_RE.search(cleaned) or UNCLOSED_FENCE_RE.search(cleaned):
        reasons.append("fenced_code_block")

    if DEF_OR_CLASS_RE.search(cleaned):
        reasons.append("code_definition_detected")

    if (
        DIRECT_RETURN_CODE_RE.search(cleaned)
        or BACKTICK_RETURN_EXPR_RE.search(cleaned)
        or INLINE_RETURN_EXPR_RE.search(cleaned)
    ):
        reasons.append("direct_return_statement")

    if MULTILINE_PYTHON_STATEMENTS_RE.search(cleaned) or INDENTED_CODE_BLOCK_RE.search(
        cleaned
    ):
        reasons.append("multiline_python_control_block")

    if INLINE_SOLUTION_REPLACEMENT_RE.search(cleaned):
        reasons.append("inline_direct_replacement")

    if PROMPT_OVERRIDE_ECHO_RE.search(cleaned):
        reasons.append("prompt_injection_echo")

    if function_name:
        call_or_def_pattern = re.compile(
            rf"\bdef\s+{re.escape(function_name)}\s*\(",
            re.MULTILINE,
        )
        if call_or_def_pattern.search(cleaned):
            if "code_definition_detected" not in reasons:
                reasons.append("code_definition_detected")

    token_overlap: float | None = None
    if reference_code:
        token_overlap = compute_code_token_overlap(
            cleaned,
            reference_code,
            function_name=function_name,
        )
        if token_overlap >= token_overlap_threshold:
            reasons.append("token_overlap_exceeded")

    return GuardrailCheckResult(
        is_leaked=bool(reasons),
        reasons=reasons,
        token_overlap=token_overlap,
    )
