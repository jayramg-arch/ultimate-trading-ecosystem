import io
import sys

filepath = r'C:\Users\jayra\Documents\GeminiVSCode\Weinstein_Unified_Ecosystem.pine'

with io.open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# These are the literal strings in the file (if it was double-encoded)
replacements = {
    'ðŸŸ¢': '🟢',
    'ðŸŸ¡': '🟡',
    'âš«': '⚫',
    'ðŸ ‚': '🐂',
    'ðŸ”„': '🔄',
    'âœ“': '✓',
    'âœ—': '✗',
    'â—‹': '○',
    'â— ': '●',
    'â”€': '─'
}

for k, v in replacements.items():
    content = content.replace(k, v)

with io.open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
