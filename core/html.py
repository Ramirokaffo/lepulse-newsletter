from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit


ALLOWED_TAGS = {
    'a', 'b', 'blockquote', 'br', 'code', 'em', 'h1', 'h2', 'h3', 'h4', 'hr',
    'i', 'img', 'li', 'ol', 'p', 'pre', 's', 'span', 'strong', 'table', 'tbody',
    'td', 'th', 'thead', 'tr', 'u', 'ul',
}
VOID_TAGS = {'br', 'hr', 'img'}
BLOCKED_WITH_CONTENT = {'script', 'style', 'iframe', 'object', 'embed', 'svg', 'math'}
ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title', 'target'},
    'img': {'src', 'alt', 'title', 'width', 'height'},
    'ol': {'start'},
    'td': {'colspan', 'rowspan'},
    'th': {'colspan', 'rowspan'},
}
URL_ATTRIBUTES = {'href', 'src'}
NUMERIC_ATTRIBUTES = {'width', 'height', 'start', 'colspan', 'rowspan'}


def _safe_url(value):
    value = value.strip()
    if not value or value.startswith(('/', '#')):
        return value
    return value if urlsplit(value).scheme.lower() in {'http', 'https', 'mailto'} else ''


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.blocked_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in BLOCKED_WITH_CONTENT:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in ALLOWED_TAGS:
            return
        clean_attrs = []
        for name, value in attrs:
            name, value = name.lower(), value or ''
            if name not in ALLOWED_ATTRIBUTES.get(tag, set()):
                continue
            if name in URL_ATTRIBUTES:
                value = _safe_url(value)
                if not value:
                    continue
            if name in NUMERIC_ATTRIBUTES and not value.isdigit():
                continue
            if name == 'target' and value != '_blank':
                continue
            clean_attrs.append(f' {name}="{escape(value, quote=True)}"')
        if tag == 'a' and any(name == 'target' and value == '_blank' for name, value in attrs):
            clean_attrs.append(' rel="noopener noreferrer"')
        self.output.append(f'<{tag}{"".join(clean_attrs)}>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in BLOCKED_WITH_CONTENT:
            self.blocked_depth = max(0, self.blocked_depth - 1)
            return
        if not self.blocked_depth and tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.output.append(f'</{tag}>')

    def handle_data(self, data):
        if not self.blocked_depth:
            self.output.append(escape(data))

    def handle_entityref(self, name):
        if not self.blocked_depth:
            self.output.append(f'&{name};')

    def handle_charref(self, name):
        if not self.blocked_depth:
            self.output.append(f'&#{name};')


def sanitize_html(value):
    sanitizer = _Sanitizer()
    sanitizer.feed(value or '')
    sanitizer.close()
    return ''.join(sanitizer.output)