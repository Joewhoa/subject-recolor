# Public Furniture Test Image Attribution

This test set uses two photographs from Wikimedia Commons. Both source images permit commercial use and modification under **CC BY-SA 3.0**. Any publicly distributed edited image derived from them must retain attribution, link the license, indicate that it was modified, and be distributed under CC BY-SA 3.0 or a compatible license.

## Kubus sofa

- Local test file: `workspace/2026-09-03/input/kubus_sofa.jpg`
- Title: **Kubus sofa**
- Creator: **Wikidapit**
- Description: Modern production of a Kubus sofa designed by Josef Hoffmann
- Source page: https://commons.wikimedia.org/wiki/File:Kubus_sofa.jpg
- Original file: https://upload.wikimedia.org/wikipedia/commons/d/d9/Kubus_sofa.jpg
- License: Creative Commons Attribution-ShareAlike 3.0 Unported
- License URL: https://creativecommons.org/licenses/by-sa/3.0/
- Suggested attribution: `“Kubus sofa” by Wikidapit, CC BY-SA 3.0, via Wikimedia Commons. Modified by Subject Recolor.`

## Couch Furniture

- Local test file: `workspace/2026-09-03/input/wooden_couch.jpg`
- Title: **Couch Furniture**
- Creator: **RanjithSiji**
- Description: A couch made with wood
- Source page: https://commons.wikimedia.org/wiki/File:Couch_Furniture.JPG
- Original file: https://upload.wikimedia.org/wikipedia/commons/3/38/Couch_Furniture.JPG
- License: Creative Commons Attribution-ShareAlike 3.0 Unported
- License URL: https://creativecommons.org/licenses/by-sa/3.0/
- Suggested attribution: `“Couch Furniture” by RanjithSiji, CC BY-SA 3.0, via Wikimedia Commons. Modified by Subject Recolor.`

## Test rationale

- `kubus_sofa.jpg` is a clean single-subject leather scene with highlights, seams, tufting, windows and wood flooring. It tests material preservation and background stability.
- `wooden_couch.jpg` is a deliberately difficult multi-instance showroom scene. It tests whether the model recolors all upholstery belonging to the requested subject while preserving dark wooden frames, neighboring objects, the red/green floor and flowers.
- Target card: `deep_teal.png`, synthetic solid color `#2F6B63`, created for this repository and not subject to third-party copyright.

License metadata was retrieved from the Wikimedia Commons API and checked against each file description page. This file is an attribution aid, not legal advice.
