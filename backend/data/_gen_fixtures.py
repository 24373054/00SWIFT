"""Generate currencies.json and countries.json fixtures (ISO 4217 + ISO 3166).

Run once: ``python data/_gen_fixtures.py``. Output overwrites currencies.json
and countries.json in the same directory.
"""
import json
import os

CURRENCIES = [
    ('AED', 784, 2, 'UAE Dirham'), ('AFN', 971, 2, 'Afghani'), ('ALL', 8, 2, 'Lek'),
    ('AMD', 51, 2, 'Armenian Dram'), ('ANG', 532, 2, 'Netherlands Antillean Guilder'),
    ('AOA', 973, 2, 'Kwanza'), ('ARS', 32, 2, 'Argentine Peso'), ('AUD', 36, 2, 'Australian Dollar'),
    ('AWG', 533, 2, 'Aruban Florin'), ('AZN', 944, 2, 'Azerbaijan Manat'), ('BAM', 977, 2, 'Convertible Mark'),
    ('BBD', 52, 2, 'Barbados Dollar'), ('BDT', 50, 2, 'Taka'), ('BGN', 975, 2, 'Bulgarian Lev'),
    ('BHD', 48, 3, 'Bahraini Dinar'), ('BIF', 108, 0, 'Burundi Franc'), ('BMD', 60, 2, 'Bermudian Dollar'),
    ('BND', 96, 2, 'Brunei Dollar'), ('BOB', 68, 2, 'Boliviano'), ('BOV', 984, 2, 'Mvdol'),
    ('BRL', 986, 2, 'Brazilian Real'), ('BSD', 44, 2, 'Bahamian Dollar'), ('BTN', 64, 2, 'Ngultrum'),
    ('BWP', 72, 2, 'Pula'), ('BYN', 933, 2, 'Belarusian Ruble'), ('BZD', 84, 2, 'Belize Dollar'),
    ('CAD', 124, 2, 'Canadian Dollar'), ('CDF', 976, 2, 'Congolese Franc'),
    ('CHE', 947, 2, 'WIR Euro'), ('CHF', 756, 2, 'Swiss Franc'), ('CHW', 948, 2, 'WIR Franc'),
    ('CLF', 990, 4, 'Unidad de Fomento'), ('CLP', 152, 0, 'Chilean Peso'), ('CNY', 156, 2, 'Yuan Renminbi'),
    ('COP', 170, 2, 'Colombian Peso'), ('COU', 970, 2, 'Unidad de Valor Real'), ('CRC', 188, 2, 'Costa Rican Colon'),
    ('CUC', 931, 2, 'Peso Convertible'), ('CUP', 192, 2, 'Cuban Peso'), ('CVE', 132, 2, 'Cabo Verde Escudo'),
    ('CZK', 203, 2, 'Czech Koruna'), ('DJF', 262, 0, 'Djibouti Franc'), ('DKK', 208, 2, 'Danish Krone'),
    ('DOP', 214, 2, 'Dominican Peso'), ('DZD', 12, 2, 'Algerian Dinar'), ('EGP', 818, 2, 'Egyptian Pound'),
    ('ERN', 232, 2, 'Nakfa'), ('ETB', 230, 2, 'Ethiopian Birr'), ('EUR', 978, 2, 'Euro'),
    ('FJD', 242, 2, 'Fiji Dollar'), ('FKP', 238, 2, 'Falkland Islands Pound'), ('GBP', 826, 2, 'Pound Sterling'),
    ('GEL', 981, 2, 'Lari'), ('GHS', 936, 2, 'Ghana Cedi'), ('GIP', 292, 2, 'Gibraltar Pound'),
    ('GMD', 270, 2, 'Dalasi'), ('GNF', 324, 0, 'Guinean Franc'), ('GTQ', 320, 2, 'Quetzal'),
    ('GYD', 328, 2, 'Guyana Dollar'), ('HKD', 344, 2, 'Hong Kong Dollar'), ('HNL', 340, 2, 'Lempira'),
    ('HRK', 191, 2, 'Kuna'), ('HTG', 332, 2, 'Gourde'), ('HUF', 348, 2, 'Forint'),
    ('IDR', 360, 2, 'Rupiah'), ('ILS', 376, 2, 'New Israeli Sheqel'), ('INR', 356, 2, 'Indian Rupee'),
    ('IQD', 368, 3, 'Iraqi Dinar'), ('IRR', 364, 2, 'Iranian Rial'), ('ISK', 352, 0, 'Iceland Krona'),
    ('JMD', 388, 2, 'Jamaican Dollar'), ('JOD', 400, 3, 'Jordanian Dinar'), ('JPY', 392, 0, 'Yen'),
    ('KES', 404, 2, 'Kenyan Shilling'), ('KGS', 417, 2, 'Som'), ('KHR', 116, 2, 'Riel'),
    ('KMF', 174, 0, 'Comorian Franc'), ('KPW', 408, 2, 'North Korean Won'), ('KRW', 410, 0, 'Won'),
    ('KWD', 414, 3, 'Kuwaiti Dinar'), ('KYD', 136, 2, 'Cayman Islands Dollar'), ('KZT', 398, 2, 'Tenge'),
    ('LAK', 418, 2, 'Lao Kip'), ('LBP', 422, 2, 'Lebanese Pound'), ('LKR', 144, 2, 'Sri Lanka Rupee'),
    ('LRD', 430, 2, 'Liberian Dollar'), ('LSL', 426, 2, 'Loti'), ('LYD', 434, 3, 'Libyan Dinar'),
    ('MAD', 504, 2, 'Moroccan Dirham'), ('MDL', 498, 2, 'Moldovan Leu'), ('MGA', 969, 2, 'Malagasy Ariary'),
    ('MKD', 807, 2, 'Denar'), ('MMK', 104, 2, 'Kyat'), ('MNT', 496, 2, 'Tugrik'),
    ('MOP', 446, 2, 'Pataca'), ('MRU', 929, 2, 'Ouguiya'), ('MUR', 480, 2, 'Mauritius Rupee'),
    ('MVR', 462, 2, 'Rufiyaa'), ('MWK', 454, 2, 'Malawi Kwacha'), ('MXN', 484, 2, 'Mexican Peso'),
    ('MXV', 979, 2, 'Mexican Unidad de Inversion (UDI)'), ('MYR', 458, 2, 'Malaysian Ringgit'),
    ('MZN', 943, 2, 'Mozambique Metical'), ('NAD', 516, 2, 'Namibia Dollar'), ('NGN', 566, 2, 'Naira'),
    ('NIO', 558, 2, 'Cordoba Oro'), ('NOK', 578, 2, 'Norwegian Krone'), ('NPR', 524, 2, 'Nepalese Rupee'),
    ('NZD', 554, 2, 'New Zealand Dollar'), ('OMR', 512, 3, 'Rial Omani'), ('PAB', 590, 2, 'Balboa'),
    ('PEN', 604, 2, 'Sol'), ('PGK', 598, 2, 'Kina'), ('PHP', 608, 2, 'Philippine Peso'),
    ('PKR', 586, 2, 'Pakistan Rupee'), ('PLN', 985, 2, 'Zloty'), ('PYG', 600, 0, 'Guarani'),
    ('QAR', 634, 2, 'Qatari Rial'), ('RON', 946, 2, 'Romanian Leu'), ('RSD', 941, 2, 'Serbian Dinar'),
    ('RUB', 643, 2, 'Russian Ruble'), ('RWF', 646, 0, 'Rwanda Franc'), ('SAR', 682, 2, 'Saudi Riyal'),
    ('SBD', 90, 2, 'Solomon Islands Dollar'), ('SCR', 690, 2, 'Seychelles Rupee'), ('SDG', 938, 2, 'Sudanese Pound'),
    ('SEK', 752, 2, 'Swedish Krona'), ('SGD', 702, 2, 'Singapore Dollar'), ('SLL', 694, 2, 'Leone'),
    ('SOS', 706, 2, 'Somali Shilling'), ('SRD', 968, 2, 'Surinam Dollar'), ('SSP', 728, 2, 'South Sudanese Pound'),
    ('STN', 930, 2, 'Dobra'), ('SVC', 222, 2, 'El Salvador Colon'), ('SYP', 760, 2, 'Syrian Pound'),
    ('SZL', 748, 2, 'Lilangeni'), ('THB', 764, 2, 'Baht'), ('TJS', 972, 2, 'Somoni'),
    ('TMT', 934, 2, 'Turkmenistan New Manat'), ('TND', 788, 3, 'Tunisian Dinar'), ('TOP', 776, 2, 'Paanga'),
    ('TRY', 949, 2, 'Turkish Lira'), ('TTD', 780, 2, 'Trinidad and Tobago Dollar'), ('TWD', 901, 2, 'New Taiwan Dollar'),
    ('TZS', 834, 2, 'Tanzanian Shilling'), ('UAH', 980, 2, 'Hryvnia'), ('UGX', 800, 0, 'Uganda Shilling'),
    ('USD', 840, 2, 'US Dollar'), ('USN', 997, 2, 'US Dollar (Next day)'), ('UYI', 940, 0, 'Uruguay Peso en Unidades Indexadas (UI)'),
    ('UYU', 858, 2, 'Peso Uruguayo'), ('UYW', 927, 4, 'Unidad Previsional'), ('UZS', 860, 2, 'Uzbekistan Sum'),
    ('VED', 926, 2, 'Bolivar Soberano'), ('VES', 928, 2, 'Bolivar Soberano'), ('VND', 704, 0, 'Dong'),
    ('VUV', 548, 0, 'Vatu'), ('WST', 882, 2, 'Tala'), ('XAF', 950, 0, 'CFA Franc BEAC'),
    ('XAG', 961, None, 'Silver'), ('XAU', 959, None, 'Gold'),
    ('XBA', 955, None, 'Bond Markets Unit European Composite Unit (EURCO)'),
    ('XBB', 956, None, 'Bond Markets Unit European Monetary Unit (E.M.U.-6)'),
    ('XBC', 957, None, 'Bond Markets Unit European Unit of Account 9 (E.U.A.-9)'),
    ('XBD', 958, None, 'Bond Markets Unit European Unit of Account 17 (E.U.A.-17)'),
    ('XCD', 951, 2, 'East Caribbean Dollar'), ('XDR', 960, None, 'SDR (Special Drawing Right)'),
    ('XOF', 952, 0, 'CFA Franc BCEAO'), ('XPD', 964, None, 'Palladium'), ('XPF', 953, 0, 'CFP Franc'),
    ('XPT', 962, None, 'Platinum'), ('XSU', 994, None, 'Sucre'),
    ('XTS', 963, None, 'Codes specifically reserved for testing purposes'),
    ('XUA', 965, None, 'ADB Unit of Account'),
    ('XXX', 999, None, 'The codes assigned for transactions where no currency is involved'),
    ('YER', 886, 2, 'Yemeni Rial'), ('ZAR', 710, 2, 'Rand'), ('ZMW', 967, 2, 'Zambian Kwacha'),
    ('ZWL', 932, 2, 'Zimbabwe Dollar'),
]

# ISO 3166 alpha-2 -> (name, alpha-3, numeric, currency, iban_structure)
# iban_structure = {"length": N, "positions": [[len, "n"|"c"], ...]} or None if no IBAN.
COUNTRIES = [
    ('AD', 'Andorra', 'AND', '020', 'EUR', {'length': 24, 'positions': [[4, 'n'], [4, 'n'], [12, 'c']]}),
    ('AE', 'United Arab Emirates', 'ARE', '784', 'AED', None),
    ('AL', 'Albania', 'ALB', '008', 'ALL', {'length': 28, 'positions': [[8, 'c'], [16, 'c']]}),
    ('AT', 'Austria', 'AUT', '040', 'EUR', {'length': 20, 'positions': [[5, 'n'], [11, 'n']]}),
    ('AU', 'Australia', 'AUS', '036', 'AUD', None),
    ('BA', 'Bosnia and Herzegovina', 'BIH', '070', 'BAM', {'length': 20, 'positions': [[3, 'n'], [3, 'n'], [8, 'n'], [2, 'n']]}),
    ('BE', 'Belgium', 'BEL', '056', 'EUR', {'length': 16, 'positions': [[3, 'n'], [7, 'n'], [2, 'n']]}),
    ('BG', 'Bulgaria', 'BGR', '100', 'BGN', {'length': 22, 'positions': [[4, 'c'], [4, 'n'], [2, 'c'], [8, 'c']]}),
    ('BH', 'Bahrain', 'BHR', '048', 'BHD', {'length': 22, 'positions': [[4, 'c'], [14, 'c']]}),
    ('BR', 'Brazil', 'BRA', '076', 'BRL', {'length': 29, 'positions': [[8, 'n'], [5, 'n'], [10, 'n'], [1, 'c'], [1, 'c']]}),
    ('BY', 'Belarus', 'BLR', '112', 'BYN', {'length': 28, 'positions': [[4, 'c'], [4, 'n'], [16, 'c']]}),
    ('CA', 'Canada', 'CAN', '124', 'CAD', None),
    ('CH', 'Switzerland', 'CHE', '756', 'CHF', {'length': 21, 'positions': [[5, 'n'], [12, 'c']]}),
    ('CN', 'China', 'CHN', '156', 'CNY', None),
    ('CY', 'Cyprus', 'CYP', '196', 'EUR', {'length': 28, 'positions': [[3, 'n'], [5, 'n'], [16, 'c']]}),
    ('CZ', 'Czech Republic', 'CZE', '203', 'CZK', {'length': 24, 'positions': [[4, 'n'], [6, 'n'], [10, 'n']]}),
    ('DE', 'Germany', 'DEU', '276', 'EUR', {'length': 22, 'positions': [[8, 'n'], [10, 'n']]}),
    ('DK', 'Denmark', 'DNK', '208', 'DKK', {'length': 18, 'positions': [[4, 'n'], [9, 'n'], [1, 'n']]}),
    ('EE', 'Estonia', 'EST', '233', 'EUR', {'length': 20, 'positions': [[2, 'n'], [2, 'n'], [11, 'n'], [1, 'n']]}),
    ('EG', 'Egypt', 'EGY', '818', 'EGP', {'length': 29, 'positions': [[4, 'n'], [4, 'n'], [17, 'n']]}),
    ('ES', 'Spain', 'ESP', '724', 'EUR', {'length': 24, 'positions': [[4, 'n'], [4, 'n'], [2, 'n'], [10, 'n']]}),
    ('FI', 'Finland', 'FIN', '246', 'EUR', {'length': 18, 'positions': [[6, 'n'], [7, 'n'], [1, 'n']]}),
    ('FR', 'France', 'FRA', '250', 'EUR', {'length': 27, 'positions': [[5, 'n'], [5, 'n'], [11, 'c'], [2, 'n']]}),
    ('GB', 'United Kingdom', 'GBR', '826', 'GBP', {'length': 22, 'positions': [[4, 'c'], [6, 'n'], [8, 'n']]}),
    ('GE', 'Georgia', 'GEO', '268', 'GEL', {'length': 22, 'positions': [[2, 'c'], [16, 'n']]}),
    ('GR', 'Greece', 'GRC', '300', 'EUR', {'length': 27, 'positions': [[3, 'n'], [4, 'n'], [16, 'c']]}),
    ('HK', 'Hong Kong', 'HKG', '344', 'HKD', None),
    ('HR', 'Croatia', 'HRV', '191', 'EUR', {'length': 21, 'positions': [[7, 'n'], [10, 'n']]}),
    ('HU', 'Hungary', 'HUN', '348', 'HUF', {'length': 28, 'positions': [[3, 'n'], [4, 'n'], [1, 'n'], [15, 'n']]}),
    ('ID', 'Indonesia', 'IDN', '360', 'IDR', None),
    ('IE', 'Ireland', 'IRL', '372', 'EUR', {'length': 22, 'positions': [[4, 'c'], [6, 'n'], [8, 'n']]}),
    ('IL', 'Israel', 'ISR', '376', 'ILS', {'length': 23, 'positions': [[3, 'n'], [3, 'n'], [13, 'n']]}),
    ('IN', 'India', 'IND', '356', 'INR', None),
    ('IS', 'Iceland', 'ISL', '352', 'ISK', {'length': 26, 'positions': [[4, 'n'], [2, 'n'], [6, 'n'], [10, 'n']]}),
    ('IT', 'Italy', 'ITA', '380', 'EUR', {'length': 27, 'positions': [[1, 'c'], [5, 'n'], [5, 'n'], [12, 'c']]}),
    ('JP', 'Japan', 'JPN', '392', 'JPY', None),
    ('KR', 'South Korea', 'KOR', '410', 'KRW', None),
    ('LI', 'Liechtenstein', 'LIE', '438', 'CHF', {'length': 21, 'positions': [[5, 'n'], [12, 'c']]}),
    ('LT', 'Lithuania', 'LTU', '440', 'EUR', {'length': 20, 'positions': [[5, 'n'], [11, 'n']]}),
    ('LU', 'Luxembourg', 'LUX', '442', 'EUR', {'length': 20, 'positions': [[3, 'n'], [13, 'c']]}),
    ('LV', 'Latvia', 'LVA', '428', 'EUR', {'length': 21, 'positions': [[4, 'c'], [13, 'c']]}),
    ('MC', 'Monaco', 'MCO', '492', 'EUR', {'length': 27, 'positions': [[5, 'n'], [5, 'n'], [11, 'c'], [2, 'n']]}),
    ('MD', 'Moldova', 'MDA', '498', 'MDL', {'length': 24, 'positions': [[2, 'c'], [18, 'c']]}),
    ('ME', 'Montenegro', 'MNE', '499', 'EUR', {'length': 22, 'positions': [[3, 'n'], [13, 'n'], [2, 'n']]}),
    ('MK', 'North Macedonia', 'MKD', '807', 'MKD', {'length': 19, 'positions': [[3, 'n'], [10, 'c'], [2, 'n']]}),
    ('MT', 'Malta', 'MLT', '470', 'EUR', {'length': 31, 'positions': [[4, 'c'], [5, 'n'], [18, 'c']]}),
    ('NL', 'Netherlands', 'NLD', '528', 'EUR', {'length': 18, 'positions': [[4, 'c'], [10, 'n']]}),
    ('NO', 'Norway', 'NOR', '578', 'NOK', {'length': 15, 'positions': [[4, 'n'], [6, 'n'], [1, 'n']]}),
    ('NZ', 'New Zealand', 'NZL', '554', 'NZD', None),
    ('PL', 'Poland', 'POL', '616', 'PLN', {'length': 28, 'positions': [[8, 'n'], [16, 'n']]}),
    ('PT', 'Portugal', 'PRT', '620', 'EUR', {'length': 25, 'positions': [[4, 'n'], [4, 'n'], [11, 'n'], [2, 'n']]}),
    ('RO', 'Romania', 'ROU', '642', 'RON', {'length': 24, 'positions': [[4, 'c'], [16, 'c']]}),
    ('RS', 'Serbia', 'SRB', '688', 'RSD', {'length': 22, 'positions': [[3, 'n'], [13, 'n'], [2, 'n']]}),
    ('RU', 'Russia', 'RUS', '643', 'RUB', None),
    ('SA', 'Saudi Arabia', 'SAU', '682', 'SAR', {'length': 24, 'positions': [[2, 'n'], [18, 'c']]}),
    ('SE', 'Sweden', 'SWE', '752', 'SEK', {'length': 24, 'positions': [[3, 'n'], [16, 'n'], [1, 'n']]}),
    ('SI', 'Slovenia', 'SVN', '705', 'EUR', {'length': 19, 'positions': [[5, 'n'], [8, 'n'], [2, 'n']]}),
    ('SK', 'Slovakia', 'SVK', '703', 'EUR', {'length': 24, 'positions': [[4, 'n'], [6, 'n'], [10, 'n']]}),
    ('SM', 'San Marino', 'SMR', '674', 'EUR', {'length': 27, 'positions': [[1, 'c'], [5, 'n'], [5, 'n'], [12, 'c']]}),
    ('TR', 'Turkey', 'TUR', '792', 'TRY', None),
    ('UA', 'Ukraine', 'UKR', '804', 'UAH', {'length': 29, 'positions': [[6, 'n'], [19, 'c']]}),
    ('US', 'United States', 'USA', '840', 'USD', None),
    ('VA', 'Vatican City', 'VAT', '336', 'EUR', {'length': 22, 'positions': [[3, 'n'], [15, 'n']]}),
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))

    cur_out = [
        {'code': c[0], 'iso_3n_code': str(c[1]).zfill(3), 'minor_unit': c[2], 'name': c[3], 'countries': []}
        for c in CURRENCIES
    ]
    with open(os.path.join(here, 'currencies.json'), 'w', encoding='utf-8') as f:
        json.dump(cur_out, f, ensure_ascii=False, indent=2)
    print('currencies.json: %d entries' % len(cur_out))

    ctry_out = [
        {
            'code': c[0],
            'name': c[1],
            'iso_3a_code': c[2],
            'iso_3n_code': c[3],
            'currency_code': c[4],
            'iban_structure': c[5],
        }
        for c in COUNTRIES
    ]
    with open(os.path.join(here, 'countries.json'), 'w', encoding='utf-8') as f:
        json.dump(ctry_out, f, ensure_ascii=False, indent=2)
    print('countries.json: %d entries' % len(ctry_out))


if __name__ == '__main__':
    main()
