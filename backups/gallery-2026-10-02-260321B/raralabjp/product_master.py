"""Confirmed product copy shared by Square and Gallery (no IO or inference)."""
import html
from square_links import navigation_html, text_html

COPY_FIELDS = tuple(f'{name}_{lang}' for lang in ('ja', 'en') for name in
                    ('description', 'inclusion_disclosure', 'cut_issue_disclosure'))
SPEC_FIELDS = ('product_name_ja', 'product_name_en', 'stone_name_ja', 'stone_name_en',
               'design_name', 'weight_ct', 'dimensions_mm', 'origin_ja', 'origin',
               'treatment_ja', 'treatment_en', 'certification_lab_ja', 'certification_lab_en')
PUBLIC_FIELDS = COPY_FIELDS + SPEC_FIELDS + ('price_jpy',)


def language_block(row, lang, include_copy=True):
    parts = []
    for name in (('description', 'inclusion_disclosure', 'cut_issue_disclosure') if include_copy else ()):
        value = row.get(f'{name}_{lang}', '')
        # A disclosure already present verbatim in the description is not repeated.
        if value and not any(value in previous for previous in parts):
            parts.append(value)
    ja = lang == 'ja'
    specs = [('石種' if ja else 'Stone', row.get(f'stone_name_{lang}', '')),
             ('デザイン' if ja else 'Design', row.get('design_name', '')),
             ('重量' if ja else 'Weight', row.get('weight_ct', '') + ' ct'),
             ('寸法' if ja else 'Dimensions', row.get('dimensions_mm', '') + ' mm'),
             ('産地' if ja else 'Origin', row.get('origin_ja' if ja else 'origin', '')),
             ('処理' if ja else 'Treatment', row.get(f'treatment_{lang}', '')),
             ('鑑別機関' if ja else 'Laboratory', row.get(f'certification_lab_{lang}', ''))]
    parts.append('\n'.join(f'{label}: {value}' for label, value in specs if value))
    return '\n\n'.join(parts)


def square_description(row, gallery_url, note_url):
    copy = []
    for name in ('description', 'inclusion_disclosure', 'cut_issue_disclosure'):
        value = row.get(f'{name}_ja', '')
        if value and not any(value in previous for previous in copy):
            copy.append(value)
    prefix = text_html('\n\n'.join(copy)) + '<p><br></p>' if copy else ''
    return (prefix + navigation_html(gallery_url, note_url)
            + text_html(language_block(row, 'ja', include_copy=False))
            + text_html(language_block(row, 'en')))


def gallery_copy_html(row):
    if row.get('product_master_version') != '1':
        return ''
    blocks = ''.join('<section lang="' + lang + '"><p style="white-space:pre-wrap">' +
                     html.escape(language_block(row, lang)) + '</p></section>'
                     for lang in ('ja', 'en'))
    return '<section class="product-description">' + blocks + '</section>'
