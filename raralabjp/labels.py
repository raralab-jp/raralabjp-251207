# labels.py

STONE_LABELS = {
    "Montana Sapphire": {
        "ja": "モンタナ・サファイア",
        "en": "Montana Sapphire",
    },
    "Aquamarine": {
        "ja": "アクアマリン",
        "en": "Aquamarine",
    },
    "Pink Tourmaline": {
        "ja": "ピンク・トルマリン",
        "en": "Pink Tourmaline",
    },
}

ORIGIN_LABELS = {
    "Montana, USA": {
        "ja": "モンタナ（アメリカ）",
        "en": "Montana, USA",
    },
    "Rock Creek, Montana, USA": {
        "ja": "ロッククリーク、モンタナ（アメリカ）",
        "en": "Rock Creek, Montana, USA",
    },
    "Umba, Tanzania": {
        "ja": "ウンバ（タンザニア）",
        "en": "Umba, Tanzania",
    },
    "Lindi, Tanzania": {
        "ja": "リンディ（タンザニア）",
        "en": "Lindi, Tanzania",
    },
    "Congo": {
        "ja": "コンゴ",
        "en": "Congo",
    },
    "Afghanistan": {
        "ja": "アフガニスタン",
        "en": "Afghanistan",
    },
}

TREATMENT_LABELS = {
    "None": {
        "ja": "なし",
        "en": "None",
    },
    "Unheated": {
        "ja": "なし（非加熱）",
        "en": "None (Unheated)",
    },
    "Heated": {
        "ja": "加熱",
        "en": "Heated",
    },
    "Unknown": {
        "ja": "不明",
        "en": "Unknown",
    },
}

CLARITY_LABELS = {
    "Eye clean": {
        "ja": "肉眼で目立つインクルージョンなし",
        "en": "Eye clean",
    },
    "Loupe clean": {
        "ja": "10倍ルーペで目立つインクルージョンなし",
        "en": "Loupe clean",
    },
}

CERT_LABELS = {
    "日独宝石研究所": {
        "ja": "日独宝石研究所",
        "en": "Japan Germany Gemmological Laboratory",
    },
    "Japan Germany Gemmological Laboratory": {
        "ja": "日独宝石研究所",
        "en": "Japan Germany Gemmological Laboratory",
    },
    "GIA": {
        "ja": "GIA",
        "en": "GIA",
    },
    "None": {
        "ja": "なし",
        "en": "None",
    },
}


PERSON_LABELS = {
    "Rara Lab": {
        "ja": "Rara Lab",
        "en": "Rara Lab",
    },
    "Rara Labカット部": {
        "ja": "Rara Labカット部",
        "en": "Rara Lab",
    },
    "TJ Jackson": {
        "ja": "TJ Jackson",
        "en": "TJ Jackson",
    },
    "Jim Perkins": {
        "ja": "Jim Perkins",
        "en": "Jim Perkins",
    },
    "Sean O’Neil": {
        "ja": "Sean O’Neil",
        "en": "Sean O’Neil",
    },
    "Sean O'Neil": {
        "ja": "Sean O’Neil",
        "en": "Sean O’Neil",
    },
}

def label(table, value, lang):
    value = "" if value is None else str(value).strip()
    if not value:
        return ""
    return table.get(value, {}).get(lang, value)
