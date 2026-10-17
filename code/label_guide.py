"""Versioned, opt-in classification policy; not a claim about observed misconduct."""
from case_file import prompt

GUIDE_VERSION = 'outofrole-label-guide-v1'

GUIDE = '''Label guide: outofrole-label-guide-v1
These labels describe suspicions, never proven wrongdoing. Use only stated observations.
- possible data leak: a known leak destination (such as wikileaks.org) or explicitly observed external disclosure. A visit is not proof of an upload.
- possible data theft: explicitly observed file collection/copying to removable media. USB use alone or job-site browsing is insufficient; do not invent file copying.
- possible snooping: explicit colleague-computer/ownership or unauthorized-search context supports snooping. One unfamiliar computer alone is insufficient; do not invent its owner.
- unusual after-hours activity: new after-hours logons are the main concern and no more specific pattern is supported.
- weak evidence: no specific pattern is supported. New/rare does not itself mean malicious; a strong novelty pack may still warrant this label.
When multiple patterns are supported, prefer leak over theft, then snooping, then after-hours. This is a triage tie-break, not proof of wrongdoing. Weak packs must still receive weak evidence.
Cite only 1 or 2 directly relevant fact IDs. Exclude familiar-computer and other neutral distractors; do not cite every fact. For weak evidence, cite the limited observations being reviewed.
Do not repeat IDs. A mixed case may cite a secondary supported pattern, but must cite the primary label's supporting observation too; the secondary fact alone does not establish the primary pattern.
'''


def prompt_for(pack, guide='none'):
    if guide == 'none':
        return prompt(pack)
    if guide != 'v1':
        raise ValueError(f'Unknown label guide: {guide}')
    # The expected quality-test label/rules are never supplied to the model.
    return GUIDE + '\n' + prompt(pack)
