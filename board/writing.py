"""Concise assistant summaries; technical records belong in task attachments."""
import re

BANNED = [
    (r'\b(?:PID|SHA|sha256|exit ?0|ticks?)\b', 'process IDs, hashes or exit codes'),
    (r'\bT\d+\b|\bE[0-4][a-z]?\b|\bV[01]b?\b', 'internal task or experiment identifiers'),
    (r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:var|tmp|data|localdata)/', 'local paths'),
    (r'\.(?:json|py|md|csv|npz|jsonl|log)\b', 'internal filenames'),
    (r'单列|交 ?Claude|沿用|沿原|保持原|原文件|已核|收核|产物|入口|接续|门禁|回执|落盘|实际退出|标签用法|独有结果|轮次', 'internal workflow shorthand'),
    (r'并不能|并不意味|并不等于|不等于|不能单凭|单凭|不足以|证明不了|解释不了|说明不了|推广为|有个边界|边界要|需要注意|值得注意|你说得对|我承认|越界|闭环|证据链|防线|全链路|矩阵|灰度|一定启发|具有一定|有所保留|坚不可摧|不可抵赖|反而是我觉得|颗粒度|抓手|赋能', 'filler, vague claims or self-commentary'),
    (r'\byou are right\b|\b(?:it is|it\x27s) worth noting\b|\bevidence chain\b|\bclosed loop\b|\bend-to-end\b|\bI must admit\b|\bmerely proves\b|\bairtight\b|\birrefutable\b', 'filler, vague claims or self-commentary'),
    (r'收回|回收|回传|准入|接线|代次|执剑者|原队列|原调度|原断点|大预算|attempt\d*|RAM\d+', 'internal process words (name experiments the way the owner does, give the result number and when the next result lands)'),
]


def validate_message(text):
    text = text.strip()
    problems = []
    if len(text) > 120:
        problems.append('Use at most 120 characters')
    if text.count('\n') > 1:
        problems.append('Use at most two lines')
    for pattern, description in BANNED:
        if re.search(pattern, text, re.I):
            problems.append('Replace ' + description + ' with the concrete result or action')
    return problems
