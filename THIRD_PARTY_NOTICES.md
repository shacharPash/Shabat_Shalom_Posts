# Third-party notices and asset provenance

The code-license decision is pending. No blanket license is granted to third-party data, fonts or images. This inventory describes the locked runtime, not a legal compliance finding.

## Hebcal calendar data

Parsha data is from [Hebcal developer APIs](https://www.hebcal.com/home/developer-apis), under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). The service selects Israel readings (`i=on`), translates/adapts labels and composes the data into posters. Local `parsha_data.json` contains validated 2024-2040 readings. The interface, terms and every rendered PNG/GIF frame retain credit. Calendar-time calculations also use JewCal and Astral; credit does not imply Hebcal endorsement.

## Fonts

Official unmodified Google Fonts Alef Regular/Bold are bundled at the repository root for rendering. Official Heebo variable TrueType is served locally at `public/fonts/Heebo.ttf`. Required verbatim copyright and SIL Open Font License 1.1 notices are in `public/fonts/Alef-OFL.txt` and `public/fonts/Heebo-OFL.txt`. Source URLs, byte sizes and SHA256 are recorded in `public/fonts/provenance.json`. The official Alef replacement preserves the tested poster glyph appearance; old font file provenance was not inferred from its filename.

## Images and local data with unresolved rights

The files below are preserved pending the owner’s provenance/permission decision. Do not claim they are MIT, CC-licensed or owned by the maintainer from their presence in this repository. Publication is gated on verification. Duplicate files are inventoried too.

| Bundled path | SHA256 | Rights status |
| --- | --- | --- |
| `images/image.png` | `d5256c8f47c29aaf4410ca96c586106d234e5df125ed63b4da8fb778b3a77b1d` | Unverified; owner permission required |
| `public/favicon-16x16.png` | `b919fa9433a2677dab94ffbf5b0a812b74a2b7529c56ae6a689002ae4a0ef49f` | Unverified; owner permission required |
| `public/watermark.png` | `2ac573b83de4c0403cb44f2434bf36e4a9d2d676369f1983be8568e1baf1afb8` | Unverified; owner permission required |
| `public/apple-touch-icon.png` | `5ad01e505ae7fb16229f08c3140c32e413f45a92c46b0966ef3b67078e170d87` | Unverified; owner permission required |
| `public/favicon-48x48.png` | `a9aca727d4c315de2bdf65fc7a0f924d002024cc787b0cfe2efb98ebc97020ce` | Unverified; owner permission required |
| `public/favicon-32x32.png` | `726ede19e7b956f3fe20794918b92581a5b44e8da4828a46fdedc199991f45b3` | Unverified; owner permission required |
| `api/watermark.png` | `2ac573b83de4c0403cb44f2434bf36e4a9d2d676369f1983be8568e1baf1afb8` | Unverified; owner permission required |
| `api/omer_default.png` | `5bfe85529ed3452df362f60fc856b94f085c956f8180818bea3e611b01e25707` | Unverified; owner permission required |
| `api/shabat_default.png` | `727ebd63e4c46e3b40963289bc2c5a2990a4143f6ee3252919d29294216c6135` | Unverified; owner permission required |
| `public/backgrounds/omer_default.png` | `5bfe85529ed3452df362f60fc856b94f085c956f8180818bea3e611b01e25707` | Unverified; owner permission required |
| `public/backgrounds/shabat_default.png` | `727ebd63e4c46e3b40963289bc2c5a2990a4143f6ee3252919d29294216c6135` | Unverified; owner permission required |
| `public/favicon.ico` | `1fecee2324c19123cf636710ae8e1770ac31d5db8fd7d1e9fac36df4c8c447fe` | Unverified; owner permission required |

The provenance/license of `cities_coordinates.geojson` also needs verification before redistribution. `cities.py`, local calendar helpers and translation code are subject to the owner’s code-license choice; generated Hebcal data retains its separate attribution.

## Runtime dependency inventory

The source references, rather than vendors, these packages. A deployment or redistributed bundle must preserve each dependency’s own license notices and applicable conditions. Metadata alone is not a legal conclusion. Installed distribution license filenames are listed for reproducibility after the hash-locked install. Review the actual texts when packaging.

Notably `python-bidi` 0.6.11 includes LGPLv3 (`COPYING.LESSER`), the incorporated GPLv3 text (`COPYING`) and third-party notices. Do not label it MIT or treat the presence of COPYING as a blanket GPL-only license for this app. [Upstream LGPL text](https://github.com/MeirKriheli/python-bidi/blob/master/COPYING.LESSER). JewCal 0.8.0 and arabic-reshaper 3.0.1 include MIT notices.

| Package | Locked version | Declared license metadata | Installed license files |
| --- | --- | --- | --- |
| annotated-doc | 0.0.5 | MIT | `annotated_doc-0.0.5.dist-info/licenses/LICENSE` |
| annotated-types | 0.8.0 | MIT | `annotated_types-0.8.0.dist-info/licenses/LICENSE` |
| anyio | 4.14.2 | MIT | `anyio-4.14.2.dist-info/licenses/LICENSE` |
| arabic-reshaper | 3.0.1 | MIT | `arabic_reshaper-3.0.1.dist-info/licenses/LICENSE` |
| astral | 3.2 | Apache-2.0 | `astral-3.2.dist-info/LICENSE` |
| certifi | 2026.7.22 | MPL-2.0 | `certifi-2026.7.22.dist-info/licenses/LICENSE` |
| charset-normalizer | 3.5.1 | MIT | `charset_normalizer-3.5.1.dist-info/licenses/LICENSE` |
| click | 8.5.0 | BSD-3-Clause | `click-8.5.0.dist-info/licenses/LICENSE.txt` |
| fastapi | 0.141.1 | MIT | `fastapi-0.141.1.dist-info/licenses/LICENSE` |
| h11 | 0.16.0 | MIT | `h11-0.16.0.dist-info/licenses/LICENSE.txt` |
| httptools | 0.8.0 | MIT | `httptools-0.8.0.dist-info/licenses/LICENSE`; `httptools-0.8.0.dist-info/licenses/vendor/http-parser/LICENSE-MIT`; `httptools-0.8.0.dist-info/licenses/vendor/llhttp/LICENSE` |
| idna | 3.19 | BSD-3-Clause | `idna-3.19.dist-info/licenses/LICENSE.md` |
| jewcal | 0.8.0 | MIT License Copyright (c) 2022 essel-dev Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated  (inspect notices) | `jewcal-0.8.0.dist-info/LICENSE` |
| pillow | 12.3.0 | MIT-CMU | `pillow-12.3.0.dist-info/licenses/LICENSE` |
| pydantic | 2.13.5 | MIT | `pydantic-2.13.5.dist-info/licenses/LICENSE` |
| pydantic-core | 2.46.5 | MIT | `pydantic_core-2.46.5.dist-info/licenses/LICENSE` |
| python-bidi | 0.6.11 | License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL) | `python_bidi-0.6.11.dist-info/licenses/COPYING`; `python_bidi-0.6.11.dist-info/licenses/COPYING.LESSER`; `python_bidi-0.6.11.dist-info/licenses/LICENSE-THIRD-PARTY.yml` |
| python-dateutil | 2.9.0.post0 | Dual License | `python_dateutil-2.9.0.post0.dist-info/LICENSE` |
| python-dotenv | 1.2.3 | BSD-3-Clause | `python_dotenv-1.2.3.dist-info/licenses/LICENSE` |
| pytz | 2025.2 | MIT | `pytz-2025.2.dist-info/LICENSE.txt` |
| pyyaml | 6.0.3 | MIT | `pyyaml-6.0.3.dist-info/licenses/LICENSE` |
| redis | 5.0.8 | MIT | `redis-5.0.8.dist-info/LICENSE` |
| requests | 2.34.2 | Apache-2.0 | `requests-2.34.2.dist-info/licenses/LICENSE`; `requests-2.34.2.dist-info/licenses/NOTICE` |
| six | 1.17.0 | MIT | `six-1.17.0.dist-info/LICENSE` |
| starlette | 1.6.0 | BSD-3-Clause | `starlette-1.6.0.dist-info/licenses/LICENSE.md` |
| typing-extensions | 4.16.0 | PSF-2.0 | `typing_extensions-4.16.0.dist-info/licenses/LICENSE` |
| typing-inspection | 0.4.4 | MIT | `typing_inspection-0.4.4.dist-info/licenses/LICENSE` |
| urllib3 | 2.7.0 | MIT | `urllib3-2.7.0.dist-info/licenses/LICENSE.txt` |
| uvicorn | 0.41.0 | BSD-3-Clause | `uvicorn-0.41.0.dist-info/licenses/LICENSE.md` |
| uvloop | 0.22.1 | MIT License | `uvloop-0.22.1.dist-info/licenses/LICENSE-APACHE`; `uvloop-0.22.1.dist-info/licenses/LICENSE-MIT` |
| watchfiles | 1.2.0 | MIT | `watchfiles-1.2.0.dist-info/licenses/LICENSE` |
| websockets | 17.1 | BSD-3-Clause | `websockets-17.1.dist-info/licenses/LICENSE` |
