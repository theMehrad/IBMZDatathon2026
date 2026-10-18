"""Conservative, versioned minimum evidence checks, not a misconduct detector.

Only exact source observation types grant support. Novelty is context, not guilt.
No fact, detector score, membership or original pack is changed by this adapter.
"""
import json
import math
from typing import Any

POLICY_VERSION = 'outofrole-evidence-policy-v2'
# This small explicit project intelligence list is NOT inferred from novelty or labels.
KNOWN_LEAK_DESTINATIONS = frozenset({'wikileaks.org'})
EVENT_TYPES = {
    'used a USB device': 'usb_connection',
    'visited website': 'website_visit',
    'logged on to computer': 'computer_logon',
    'logged on after hours': 'after_hours_logon',
    # Richer source observations are supported but not emitted by current M3.
    'copied files to removable media': 'removable_copy',
    'uploaded files to external website': 'external_upload',
    'logged on to colleague computer': 'colleague_pc_logon',
    'performed unauthorized file search': 'unauthorized_search',
}
OBSERVATIONS = (
    'usb_connected', 'file_copy_observed', 'external_upload_observed',
    'known_leak_destination_visited', 'new_colleague_computer_access_observed',
    'unauthorized_file_search_observed', 'new_after_hours_logon_observed',
)
LABEL_SUPPORT = {
    'possible data theft': ('file_copy_observed',),
    'possible data leak': ('known_leak_destination_visited', 'external_upload_observed'),
    'possible snooping': ('new_colleague_computer_access_observed', 'unauthorized_file_search_observed'),
    'unusual after-hours activity': ('new_after_hours_logon_observed',),
}


def observation_view(pack) -> dict[str, Any]:
    """A typed read-only projection of supplied facts; false means not observed here."""
    support = {name: [] for name in OBSERVATIONS}
    facts = []
    seen = set()
    for fact in pack['facts']:
        id = fact['id']
        share = fact['staff_share']
        if (not isinstance(id, str) or not id or id in seen
                or not isinstance(fact['new_to_person'], bool)
                or isinstance(share, bool) or not isinstance(share, (int, float))
                or not math.isfinite(share) or not 0 <= share <= 1
                or not all(isinstance(fact[key], str) for key in ('what', 'item', 'date'))):
            raise ValueError('Invalid source evidence fields or duplicate fact ID')
        seen.add(id)
        event = EVENT_TYPES.get(fact['what'], 'unrecognized_observation')
        row = dict(id=id, event=event, item=fact['item'], date=fact['date'],
                   context=dict(new_to_person=fact['new_to_person'], staff_share=share))
        facts.append(row)
        checks = {
            'usb_connected': event == 'usb_connection',
            'file_copy_observed': event == 'removable_copy',
            'external_upload_observed': event == 'external_upload',
            'known_leak_destination_visited': event == 'website_visit' and
                fact['item'].lower().removeprefix('www.').removesuffix('.') in KNOWN_LEAK_DESTINATIONS,
            'new_colleague_computer_access_observed': event == 'colleague_pc_logon' and fact['new_to_person'],
            'unauthorized_file_search_observed': event == 'unauthorized_search',
            'new_after_hours_logon_observed': event == 'after_hours_logon' and fact['new_to_person'],
        }
        for name, observed in checks.items():
            if observed:
                support[name].append(id)
    return dict(schema_version=POLICY_VERSION, person=pack['person'],
                novelty_strength=pack['strength'],
                coverage_note='False means not observed in this supplied pack, not proof of absence. '
                              'Novelty strength describes new/rare behavior, not maliciousness.',
                observations={name: bool(ids) for name, ids in support.items()},
                supporting_fact_ids=support, facts=facts)


def check_reply(reply, pack):
    """Return policy problems, never relabel or repair a model answer.

The unchanged structural validator remains the first boundary. The policy checks
minimum support, not the strongest available label or whether the person is guilty.
"""
    from case_file import accept
    label, _, problems = accept(reply, pack)
    if problems:
        return problems
    try:
        view = observation_view(pack)
    except (ValueError, KeyError, TypeError) as exc:
        return [f'Evidence policy: invalid source pack: {exc}']
    citations = json.loads(reply)['facts']
    if len(citations) > 2 or len(set(citations)) != len(citations):
        problems.append('Evidence policy: cite one or two unrepeated fact IDs')
    if label == 'weak evidence':
        return problems  # Conservative abstention is never proof of model quality.
    if label not in LABEL_SUPPORT:
        return ['Evidence policy: unknown positive label']
    supporting = view['supporting_fact_ids']
    primary = {id for name in LABEL_SUPPORT[label] for id in supporting[name]}
    if not primary:
        problems.append('Evidence policy: supplied observations do not support this label')
    elif not primary.intersection(citations):
        problems.append('Evidence policy: cite an observation supporting the proposed label')
    positive_context = {id for groups in LABEL_SUPPORT.values() for name in groups for id in supporting[name]}
    if set(citations) - positive_context:
        problems.append('Evidence policy: neutral or unsupported context cited as positive support')
    return problems
