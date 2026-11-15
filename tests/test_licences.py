"""Other portals' licences are stated as those portals state them (defect D-049).

The Data Quality Commons moved its content from OGL v3.0 to CC BY 4.0 in release 2.16.1 (15 November 2026);
the playbooks still credited it as OGL. The credit and the licence note must name the licence it uses now.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def commons_licence_problems(playbooks_yaml, licence_md):
    problems = []
    credit = re.search(r"\{who: Contributors to the Public Sector Data Quality Commons,.*?licence: \"([^\"]*)\"\}", playbooks_yaml)
    if not credit:
        problems.append("no credit entry for the Data Quality Commons")
    elif "CC BY 4.0" not in credit.group(1):
        problems.append(f"the Commons credit says '{credit.group(1)}', not CC BY 4.0")
    line = next((x for x in licence_md.splitlines() if "Data Quality Commons" in x), "")
    if "CC BY 4.0" not in line:
        problems.append("docs/CONTENT-LICENCE.md does not say the Commons' content is CC BY 4.0")
    return problems


class CommonsLicence(unittest.TestCase):
    def test_commons_licence_is_current(self):
        self.assertEqual(commons_licence_problems(read("content", "playbooks.yaml"), read("docs", "CONTENT-LICENCE.md")), [])

    def test_check_catches_the_old_ogl_credit(self):
        # Negative test: the text before D-049 was fixed.
        old_yaml = '- {who: Contributors to the Public Sector Data Quality Commons, what: "x", licence: "MIT (code), OGL v3.0 (content)"}'
        old_md = "Material summarised from the Public Sector Data Quality Commons is used under its OGL v3.0 content licence."
        self.assertEqual(len(commons_licence_problems(old_yaml, old_md)), 2)


if __name__ == "__main__":
    unittest.main()
