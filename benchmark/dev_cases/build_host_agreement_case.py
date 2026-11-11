"""Build the host country agreement worked case (loop D-S39 item 2).

SYNTHETIC. The Republic of Sarvenna, Port Meral and the International Coastal Monitoring
Organisation are invented; no person is named. The case follows the section structure of
published host country agreements and copies no agreement's text. It is a demonstration,
never benchmark evidence (D-S39 item 6).

One table, BLOCKS, holds every paragraph in four states: the opening draft, then rounds 1, 2
and 3. Everything is derived from it, so the versions cannot drift apart:

    host_agreement_three_rounds/
      EXPECTED.md            written by hand, what was planted; never in workload/
      workload/              the sealer's folder (docs/INPUT_FORMAT.md section 12)
        _review_targets.json round 3 as target, round 2 as prior, the rest as grounding
        case_manifest.json   three rounds, two actors, the issues, every source an exact span
        context/             the run input: each round's text as a .docx with real w:ins and
                             w:del against the state before, and each party's note as Markdown
        conventions/         general review rules

scripts/text_extract.py reads a .docx with every tracked change accepted and its headings,
paragraphs and tables kept. `--check` proves each .docx read by the extractor is that round's text
exactly, the one the manifest's spans are measured on, and that the same .docx with every change
rejected is the state before.

    py -3.12 -X utf8 benchmark/dev_cases/build_host_agreement_case.py                # write
    py -3.12 -X utf8 benchmark/dev_cases/build_host_agreement_case.py --check        # compare
    py -3.12 -X utf8 benchmark/dev_cases/build_host_agreement_case.py --ordinary-out <folder>

The multi-round run is sealed from workload/. `--ordinary-out` writes the same members without
case_manifest.json, which is the ordinary two-version review of section 12.
"""
import datetime
import difflib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from xml.sax.saxutils import escape
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CASE = Path(__file__).resolve().parent / "host_agreement_three_rounds"
WORKLOAD = CASE / "workload"
CASE_ID = "seat-agreement-three-rounds"

SYNTHETIC = ("Synthetic document for demonstration only. The states, organisations and persons "
             "it names are fictional.")
ORG = "International Coastal Monitoring Organisation"
HOST = "Republic of Sarvenna"
TITLE = "Agreement between the %s and the %s regarding the seat of the Organisation" % (HOST, ORG)
AUTHOR = {1: "Delegation of Sarvenna", 2: "Delegation of the Organisation", 3: "Delegation of Sarvenna"}
WHEN = {1: "2026-03-09T09:00:00Z", 2: "2026-04-20T09:00:00Z", 3: "2026-06-01T09:00:00Z"}
ROUNDS = (1, 2, 3)

AGREED = "Article status: agreed ad referendum"
PROPOSED = "Article status: proposed as agreed ad referendum"
OPEN = "Article status: open"
STATUS = {"a": AGREED, "p": PROPOSED, "o": OPEN}
STATUS_NOTE = ("Each round is one delegation's mark-up. An article is agreed ad referendum only when "
               "both delegations have recorded it so; a status that delegation alone puts forward "
               "reads proposed as agreed ad referendum.")


def same(text):
    return (text, text, text, text)


def status(*states):
    return tuple(STATUS[s] for s in states)


# ("title", text), ("h", text), ("p", (opening, round 1, round 2, round 3)), ("table", rows):
# None means the paragraph does not stand in that state. A table's rows hold each cell's states.
# Numbering: a paragraph deleted from the middle of an article stays as "n. [Deleted]" so that the
# paragraphs after it keep their numbers, as in a rolling text; a last paragraph simply goes. A
# paragraph inserted in the middle renumbers those after it (Art. 4). Status: see STATUS_NOTE.
BLOCKS = [
    ("title", TITLE),
    ("p", same(SYNTHETIC)),
    ("p", ("Opening draft of the Secretariat, 2 February 2026.",
           "Rolling text of round 1, 9 March 2026, with the changes of the delegation of Sarvenna.",
           "Rolling text of round 2, 20 April 2026, with the changes of the delegation of the Organisation.",
           "Rolling text of round 3, 1 June 2026, with the changes of the delegation of Sarvenna.")),
    ("p", same(STATUS_NOTE)),
    ("p", same("The %s and the %s," % (HOST, ORG))),
    ("p", same("Considering that the Assembly of the Organisation has chosen Port Meral as the seat of "
               "the Organisation and that the Republic of Sarvenna has welcomed that choice,")),
    ("p", same("Wishing to settle the status of the Organisation in the Republic of Sarvenna and to "
               "enable it to carry out its functions independently and efficiently,")),
    ("p", same("Have agreed as follows.")),

    ("h", "Article 1. Use of terms"),
    ("p", status("o", "o", "a", "o")),
    ("p", same("In this Agreement the terms below have the meanings given to them here.")),
    ("p", same('(a) "the Organisation" means the %s.' % ORG)),
    ("p", same('(b) "the Government" means the Government of the %s.' % HOST)),
    ("p", same('(c) "the Director-General" means the chief executive officer of the Organisation or '
               "the person acting on that officer's behalf.")),
    ("p", ('(d) "the premises" means the land and buildings in Port Meral that the Organisation '
           "occupies for its official purposes.",
           '(d) "the premises" means the land and buildings in Port Meral listed by exchange of notes '
           "and used by the Organisation for its official purposes.",
           '(d) "the premises" means the land and buildings in Port Meral listed by exchange of notes '
           "and used by the Organisation for its official purposes.",
           '(d) "the premises" means the land and buildings in Port Meral listed by exchange of notes '
           "and used by the Organisation for its official purposes.")),
    ("p", same('(e) "officials" means the members of the staff of the Organisation, other than persons '
               "recruited locally and paid by the hour.")),
    ("p", same('(f) "dependants" means the spouse and the minor children of an official.')),
    ("p", ('(g) "visa" means the authorisation to enter and to reside in the Republic of Sarvenna.',
           '(g) "visa" means the authorisation to enter and to reside in the Republic of Sarvenna.',
           '(g) "visa" means the authorisation to enter and to reside in the Republic of Sarvenna.',
           '(g) "entry clearance" means the authorisation to enter and to reside in the Republic of '
           "Sarvenna.")),

    ("h", "Article 2. Legal personality"),
    ("p", status("o", "p", "a", "a")),
    ("p", same("The Republic of Sarvenna recognises that the Organisation has legal personality under "
               "its domestic law, including the capacity to conclude contracts, to hold and transfer "
               "movable and immovable property and to be a party to legal proceedings.")),

    ("h", "Article 3. Seat"),
    ("p", status("o", "o", "o", "p")),
    ("p", same("1. The seat of the Organisation shall be at Port Meral.")),
    ("p", ("2. The Government shall make the premises available to the Organisation free of rent for "
           "as long as the seat remains in the Republic of Sarvenna.",
           "2. The Government shall make the premises available to the Organisation free of rent for "
           "an initial period of ten years.",
           "2. The Government shall make the premises available to the Organisation free of rent for "
           "as long as the seat remains in the Republic of Sarvenna.",
           "2. The Government shall make the premises available to the Organisation free of rent for "
           "an initial period of twenty years, renewable by agreement of the parties.")),
    ("p", same("3. The annual contribution of the Republic of Sarvenna to the running of the seat is "
               "set out in Annex II.")),

    ("h", "Article 4. Inviolability of the premises"),
    ("p", status("o", "o", "o", "p")),
    ("p", same("1. The premises shall be inviolable and shall be under the authority of the Organisation.")),
    ("p", ("2. No officer of the Republic of Sarvenna shall enter the premises to carry out any "
           "official duty except with the consent of the Director-General.",
           "2. No officer of the Republic of Sarvenna shall enter the premises to carry out any "
           "official duty except with the consent of the Director-General or in urgent circumstances "
           "determined by the competent authorities.",
           "2. No officer of the Republic of Sarvenna shall enter the premises to carry out any "
           "official duty except with the express consent of the Director-General.",
           "2. No officer of the Republic of Sarvenna shall enter the premises to carry out any "
           "official duty except with the express consent of the Director-General.")),
    ("p", (None, None,
           "3. In case of fire or a like emergency calling for immediate protective action, that "
           "consent shall be presumed if the Director-General cannot be reached in time.",
           "3. In case of fire or a like emergency calling for immediate protective action, that "
           "consent shall be presumed if the Director-General cannot be reached in time.")),
    ("p", (None,
           "3. The Organisation shall not allow the premises to shelter a person sought under an "
           "order of a court of the Republic of Sarvenna.",
           "4. The Organisation shall not allow the premises to shelter a person sought under an "
           "order of a court of the Republic of Sarvenna.",
           "4. The Organisation shall not allow the premises to shelter a person sought under an "
           "order of a court of the Republic of Sarvenna.")),

    ("h", "Article 5. Public services"),
    ("p", status("o", "o", "a", "a")),
    ("p", ("The Government shall ensure that the premises receive electricity, water, gas, "
           "telecommunications and waste collection on terms no less favourable than those granted "
           "to its own ministries.",
           "The Government shall ensure that the premises receive electricity, water, gas, "
           "telecommunications and waste collection on terms no less favourable than those granted "
           "to comparable public bodies.",
           "The Government shall ensure that the premises receive electricity, water, gas, "
           "telecommunications and waste collection on terms no less favourable than those granted "
           "to comparable public bodies.",
           "The Government shall ensure that the premises receive electricity, water, gas, "
           "telecommunications and waste collection on terms no less favourable than those granted "
           "to comparable public bodies.")),

    ("h", "Article 6. Immunity from legal process"),
    ("p", status("o", "o", "o", "p")),
    ("p", same("1. The Organisation and its property shall enjoy immunity from every form of legal "
               "process, except where the Director-General expressly waives that immunity in a "
               "particular case.")),
    ("p", ("2. A waiver shall not extend to any measure of execution.",
           "2. A waiver shall not extend to any measure of execution, save for the enforcement of a "
           "final judgment in a commercial dispute.",
           "2. A waiver shall not extend to any measure of execution, for which a separate express "
           "waiver is required.",
           "2. A waiver shall not extend to any measure of execution, for which a separate express "
           "waiver is required.")),
    ("p", same("3. The property of the Organisation, wherever it is located, shall be immune from "
               "search, requisition, confiscation and expropriation.")),

    ("h", "Article 7. Archives and communications"),
    ("p", status("o", "p", "a", "a")),
    ("p", same("1. The archives of the Organisation, and every document belonging to it or held by it, "
               "shall be inviolable wherever they are located.")),
    ("p", same("2. The official communications of the Organisation shall receive treatment no less "
               "favourable than that which the Government gives to diplomatic missions in the "
               "Republic of Sarvenna.")),

    ("h", "Article 8. Exemption from taxes and duties"),
    ("p", status("o", "o", "o", "p")),
    ("p", same("1. The Organisation, its assets and its income shall be exempt from all direct taxes.")),
    ("p", same("2. The Organisation shall be exempt from customs duties on goods imported for its "
               "official use.")),
    ("p", ("3. The Organisation shall be exempt from value added tax on its purchases for official use.",
           "3. The Organisation shall be exempt from value added tax on its purchases for official "
           "use above 5,000 EUR per invoice.",
           "3. The Organisation shall be exempt from value added tax on its purchases for official "
           "use above 1,000 EUR per invoice.",
           "3. The Organisation shall be exempt from value added tax on its purchases for official "
           "use above 1,000 EUR per invoice.")),
    ("p", (None,
           "4. That exemption shall be given by refund and not at the point of sale. A refund claim "
           "shall be decided within ninety days.",
           "4. That exemption shall be given by refund and not at the point of sale. A refund claim "
           "shall be decided within sixty days.",
           None)),

    ("h", "Article 9. Entry and residence"),
    ("p", status("o", "o", "o", "o")),
    ("p", same("1. The Government shall take every measure needed to facilitate the entry into, the "
               "stay in and the departure from the Republic of Sarvenna of officials, their "
               "dependants, the representatives of members of the Organisation and persons invited "
               "on its official business.")),
    ("p", ("2. Visas for the persons named in paragraph 1 shall be free of charge, and every "
           "application shall be decided within fourteen days.",
           "2. Visas for the persons named in paragraph 1 shall be free of charge, and every "
           "application shall be decided within thirty days.",
           "2. Visas for the persons named in paragraph 1 shall be free of charge, and every "
           "application shall be decided within twenty-one days.",
           "2. Entry clearance for the persons named in paragraph 1 shall be free of charge, and every "
           "application shall be decided within twenty-one days.")),
    ("p", ("3. Dependants shall be authorised to take up employment in the Republic of Sarvenna for "
           "the length of the official's appointment.",
           None,
           "3. Dependants may apply for a work authorisation, which shall not be refused without "
           "stated reasons.",
           None)),

    ("h", "Article 10. Officials"),
    ("p", status("o", "o", "o", "o")),
    ("p", same("1. Officials shall be immune from legal process in respect of words spoken or written "
               "and acts performed by them in their official capacity.")),
    ("p", same("2. Officials shall be exempt from income tax on the salaries paid to them by the "
               "Organisation.")),
    ("p", ("3. Officials may import their furniture and personal effects free of duty on first taking "
           "up their post.",
           "3. Officials may import their furniture and personal effects free of duty within six "
           "months of first taking up their post.",
           "3. Officials may import their furniture and personal effects free of duty within twelve "
           "months of first taking up their post.",
           "3. Officials may import their furniture and personal effects free of duty within twelve "
           "months of first taking up their post.")),
    ("p", (None, None,
           "4. For purchases made on first installation, officials may reclaim value added tax through "
           "the procedure in paragraph 4 of Article 8.",
           "4. For purchases made on first installation, officials may reclaim value added tax through "
           "the procedure in paragraph 4 of Article 8.")),
    ("p", (None, None, None,
           "5. Applications for entry clearance by officials and their dependants shall be decided "
           "within thirty days.")),

    ("h", "Article 11. Security and cooperation"),
    ("p", status("o", "o", "o", "o")),
    ("p", same("1. The Organisation shall cooperate with the competent authorities to further the "
               "proper administration of justice and to prevent any abuse of the privileges granted "
               "in this Agreement.")),
    ("p", (None,
           "2. Nothing in this Agreement shall affect the right of the Republic of Sarvenna to take "
           "precautions in the interest of its security.",
           "2. Nothing in this Agreement shall affect the right of the Republic of Sarvenna to take "
           "precautions in the interest of its security, after consulting the Director-General and "
           "so far as possible without interfering with the work of the Organisation.",
           "2. Nothing in this Agreement shall affect the right of the Republic of Sarvenna to take "
           "precautions in the interest of its security, after consulting the Director-General and "
           "so far as possible without interfering with the work of the Organisation.")),
    ("p", (None, None, None,
           "3. Where the competent authorities consider that public security so requires, they may "
           "enter the premises without the consent of the Director-General.")),

    ("h", "Article 12. Waiver of immunity"),
    ("p", status("o", "p", "a", "a")),
    ("p", same("Privileges and immunities are granted in the interest of the Organisation and not for "
               "the personal benefit of the persons who hold them. The Director-General has the duty "
               "to lift an official's immunity whenever keeping it would stand in the way of justice "
               "and lifting it would do the Organisation no harm.")),

    ("h", "Article 13. Settlement of disputes"),
    ("p", status("o", "o", "o", "p")),
    ("p", ("1. A dispute between the parties on the interpretation or application of this Agreement "
           "that is not settled by negotiation within ninety days shall, at the request of either "
           "party, be referred to a tribunal of three arbitrators.",
           "1. A dispute between the parties on the interpretation or application of this Agreement "
           "shall be settled by negotiation through the diplomatic channel.",
           "1. A dispute between the parties on the interpretation or application of this Agreement "
           "that is not settled by negotiation within ninety days shall, at the request of either "
           "party, be referred to a tribunal of three arbitrators.",
           "1. A dispute between the parties on the interpretation or application of this Agreement "
           "that is not settled by negotiation within ninety days shall, at the request of either "
           "party, be referred to a tribunal of three arbitrators.")),
    ("p", ("2. Each party shall appoint one arbitrator, and the two arbitrators shall appoint the "
           "president of the tribunal. If an appointment is not made within sixty days, either party "
           "may ask an appointing authority agreed by the parties to make it.",
           "2. [Deleted]",
           "2. Each party shall appoint one arbitrator, and the two arbitrators shall appoint the "
           "president of the tribunal. If an appointment is not made within sixty days, either party "
           "may ask an appointing authority agreed by the parties to make it.",
           "2. Each party shall appoint one arbitrator, and the two arbitrators shall appoint the "
           "president of the tribunal. If an appointment is not made within sixty days, either party "
           "may ask an appointing authority agreed by the parties to make it.")),
    ("p", same("3. The Organisation shall make suitable provision for the settlement of disputes of a "
               "private law character to which it is a party.")),

    ("h", "Article 14. Entry into force, amendment and termination"),
    ("p", status("o", "o", "o", "p")),
    ("p", same("1. This Agreement shall enter into force on the date on which the parties notify each "
               "other that their internal procedures are complete.")),
    ("p", same("2. This Agreement may be amended by written agreement of the parties.")),
    ("p", ("3. Either party may terminate this Agreement by written notice. Termination shall take "
           "effect twenty-four months after the date of the notice.",
           "3. Either party may terminate this Agreement by written notice. Termination shall take "
           "effect twelve months after the date of the notice.",
           "3. Either party may terminate this Agreement by written notice. Termination shall take "
           "effect eighteen months after the date of the notice.",
           "3. Either party may terminate this Agreement by written notice. Termination shall take "
           "effect eighteen months after the date of the notice.")),
    ("p", same("Done at Port Meral, in two originals in the English language.")),

    ("h", "Annex I. Schedule of periods"),
    ("p", status("o", "o", "o", "o")),
    ("p", ("Visa decision period: 14 days", "Visa decision period: 30 days",
           "Visa decision period: 21 days", "Entry clearance period: 21 days")),
    ("p", (None, "Refund decision period: 90 days", "Refund decision period: 60 days", None)),
    ("p", same("Arbitrator appointment period: 60 days")),
    ("p", ("Termination notice period: 24 months", "Termination notice period: 12 months",
           "Termination notice period: 18 months", "Termination notice period: 18 months")),

    ("h", "Annex II. Annual contribution of the host state"),
    ("p", status("o", "o", "o", "o")),
    ("p", ("Total annual contribution: 2,400,000 EUR", "Total annual contribution: 2,000,000 EUR",
           "Total annual contribution: 2,200,000 EUR", "Total annual contribution: 2,200,000 EUR")),
    ("table", [
        (same("Contribution line"), same("Annual contribution (EUR)")),
        (same("Premises rent waiver"), same("1,200,000")),
        (same("Building maintenance"), ("500,000", "300,000", "400,000", "400,000")),
        (same("Security services"), ("400,000", "250,000", "300,000", "200,000")),
        (same("Utilities"), ("300,000", "250,000", "300,000", "300,000")),
    ]),
]

# Each party's short note per round: (round, actor) -> paragraphs under one heading.
NOTES = {
    (1, "host_state"): [
        "The Host State welcomes the opening draft of the Secretariat and wishes to conclude a seat "
        "agreement this year. Its changes protect a small number of national interests.",
        "The competent authorities must be able to enter the premises in urgent circumstances. "
        "Relief from value added tax should apply only above 5,000 EUR per invoice and should be "
        "given by refund, since the treasury cannot administer an exemption at the point of sale.",
        "Disputes between the parties belong in the diplomatic channel, and the Host State cannot "
        "accept arbitration. Visa applications need 30 days. The employment of dependants is a "
        "matter for national labour law and has no place in this Agreement.",
        "A termination notice of 12 months is sufficient. The annual contribution can be "
        "2,000,000 EUR.",
    ],
    (1, "organisation"): [
        "The Organisation thanks the Host State for its early reply and notes the changes with "
        "concern on four points.",
        "Unqualified inviolability is the core of any seat agreement, and the Organisation cannot "
        "accept entry on a determination by the authorities alone. It is ready to discuss a "
        "presumption of consent in case of fire.",
        "A refund scheme may be workable, but a threshold of 5,000 EUR would exclude most of what "
        "the Organisation buys. An arbitration clause is indispensable for an organisation that "
        "cannot be sued in the courts of the Host State.",
        "A decision on visas within 14 days is the norm the Organisation needs for its "
        "technical missions, and it continues to attach importance to the employment of dependants.",
        "It asks for a termination notice of 24 months, and for an annual contribution of 2,600,000 EUR "
        "that covers the full running cost of the seat.",
    ],
    (2, "organisation"): [
        "The Organisation has moved on every open article and asks the Host State to respond in kind.",
        "It restores express consent in Article 4 and offers in return a presumption of consent in "
        "case of fire. It accepts a refund scheme with a threshold of 1,000 EUR and a decision "
        "within sixty days.",
        "It proposes 21 days for visas as a compromise, and a termination notice of 18 months. "
        "It restores arbitration, which it cannot give up.",
        "On dependants it now asks only that they may apply for a work authorisation, which is less "
        "than a right to work. It proposes an annual contribution of 2,200,000 EUR.",
    ],
    (2, "host_state"): [
        "The Host State notes the movement of the Organisation and will study the text in capital.",
        "It can consider arbitration if its security interests are protected elsewhere in the "
        "Agreement. It can accept 21 days for visas in principle.",
        "It can accept in principle that dependants may apply for a work authorisation, subject to "
        "drafting. An annual contribution of 2,200,000 EUR can be considered. A termination notice "
        "of 12 months remains its position.",
    ],
    (3, "host_state"): [
        "The Host State presents a text that it regards as close to final.",
        "It accepts arbitration at the request of either party and accepts express consent in "
        "Article 4. It offers rent-free premises for an initial period of twenty years. In return "
        "it has added a provision on public security in Article 11.",
        "The refund procedure is better placed in an administrative arrangement outside the "
        "Agreement, and paragraph 4 of Article 8 has been removed for that reason.",
        "The term visa is replaced by entry clearance, which is the term of national law. Article 1 "
        "is reopened for that change alone. The annual contribution is maintained at 2,200,000 EUR.",
        "The Host State proposes that Articles 3, 4, 6, 8, 13 and 14 be recorded as agreed ad referendum.",
    ],
    (3, "organisation"): [
        "The Organisation welcomes the acceptance of arbitration and of express consent in Article 4, "
        "which it regards as the most important results of this round.",
        "It asks that the text provide that dependants may apply for a work authorisation, as the "
        "Host State accepted in principle in round 2. It wishes to see the administrative arrangement "
        "on refunds before it agrees to move that procedure.",
        "It is still studying the new paragraphs of Articles 10 and 11 and reserves its position on them.",
        "It accepts a termination notice of 18 months. It asks that the annual contribution be restored "
        "to 2,400,000 EUR, since the line for security services has been cut by 100,000 EUR.",
    ],
}
ACTOR_NAME = {"host_state": "the Republic of Sarvenna", "organisation": "the Organisation"}

# Sources: (round, actor, issue, document kind, quote). A note speaks for its own party; a round's
# text speaks for the delegation whose changes that round carries.
TEXT_ACTOR = {1: "host_state", 2: "organisation", 3: "host_state"}
SOURCES = [
    (1, "host_state", "premises-access", "note", "The competent authorities must be able to enter the premises in urgent circumstances."),
    (1, "organisation", "premises-access", "note", "Unqualified inviolability is the core of any seat agreement"),
    (2, "organisation", "premises-access", "note", "It restores express consent in Article 4"),
    (3, "host_state", "premises-access", "note", "accepts express consent in Article 4"),
    (1, "host_state", "premises-access", "text", "except with the consent of the Director-General or in urgent circumstances determined by the competent authorities."),
    (2, "organisation", "premises-access", "text", "except with the express consent of the Director-General."),
    (3, "host_state", "premises-access", "text", "except with the express consent of the Director-General."),
    (1, "host_state", "tax-relief", "note", "Relief from value added tax should apply only above 5,000 EUR per invoice"),
    (1, "organisation", "tax-relief", "note", "a threshold of 5,000 EUR would exclude most of what the Organisation buys."),
    (2, "organisation", "tax-relief", "note", "It accepts a refund scheme with a threshold of 1,000 EUR and a decision within sixty days."),
    (3, "host_state", "tax-relief", "note", "The refund procedure is better placed in an administrative arrangement outside the Agreement"),
    (3, "organisation", "tax-relief", "note", "It wishes to see the administrative arrangement on refunds before it agrees to move that procedure."),
    (1, "host_state", "tax-relief", "text", "Refund decision period: 90 days"),
    (2, "organisation", "tax-relief", "text", "Refund decision period: 60 days"),
    (1, "host_state", "entry-period", "note", "Visa applications need 30 days."),
    (1, "organisation", "entry-period", "note", "A decision on visas within 14 days is the norm"),
    (2, "organisation", "entry-period", "note", "It proposes 21 days for visas as a compromise"),
    (2, "host_state", "entry-period", "note", "It can accept 21 days for visas in principle."),
    (3, "host_state", "entry-period", "note", "The term visa is replaced by entry clearance, which is the term of national law."),
    (1, "host_state", "entry-period", "text", "Visa decision period: 30 days"),
    (2, "organisation", "entry-period", "text", "Visa decision period: 21 days"),
    (3, "host_state", "entry-period", "text", "Entry clearance period: 21 days"),
    (1, "host_state", "dependants", "note", "The employment of dependants is a matter for national labour law"),
    (1, "organisation", "dependants", "note", "it continues to attach importance to the employment of dependants."),
    (2, "organisation", "dependants", "note", "it now asks only that they may apply for a work authorisation"),
    (2, "host_state", "dependants", "note", "It can accept in principle that dependants may apply for a work authorisation, subject to drafting."),
    (3, "organisation", "dependants", "note", "It asks that the text provide that dependants may apply for a work authorisation"),
    (1, "host_state", "dispute-settlement", "note", "Disputes between the parties belong in the diplomatic channel"),
    (1, "organisation", "dispute-settlement", "note", "An arbitration clause is indispensable"),
    (2, "organisation", "dispute-settlement", "note", "It restores arbitration, which it cannot give up."),
    (2, "host_state", "dispute-settlement", "note", "It can consider arbitration if its security interests are protected elsewhere in the Agreement."),
    (3, "host_state", "dispute-settlement", "note", "It accepts arbitration at the request of either party"),
    (3, "organisation", "dispute-settlement", "note", "welcomes the acceptance of arbitration"),
    (1, "host_state", "termination-notice", "note", "A termination notice of 12 months is sufficient."),
    (1, "organisation", "termination-notice", "note", "It asks for a termination notice of 24 months"),
    (2, "organisation", "termination-notice", "note", "a termination notice of 18 months."),
    (2, "host_state", "termination-notice", "note", "A termination notice of 12 months remains its position."),
    (3, "organisation", "termination-notice", "note", "It accepts a termination notice of 18 months."),
    (1, "host_state", "termination-notice", "text", "Termination notice period: 12 months"),
    (2, "organisation", "termination-notice", "text", "Termination notice period: 18 months"),
    (3, "host_state", "termination-notice", "text", "Termination notice period: 18 months"),
    (1, "host_state", "annual-contribution", "note", "The annual contribution can be 2,000,000 EUR."),
    (1, "organisation", "annual-contribution", "note", "an annual contribution of 2,600,000 EUR"),
    (2, "organisation", "annual-contribution", "note", "It proposes an annual contribution of 2,200,000 EUR."),
    (2, "host_state", "annual-contribution", "note", "An annual contribution of 2,200,000 EUR can be considered."),
    (3, "host_state", "annual-contribution", "note", "contribution is maintained at 2,200,000 EUR."),
    (3, "organisation", "annual-contribution", "note", "the annual contribution be restored to 2,400,000 EUR"),
    (1, "host_state", "annual-contribution", "text", "Total annual contribution: 2,000,000 EUR"),
    (2, "organisation", "annual-contribution", "text", "Total annual contribution: 2,200,000 EUR"),
    (3, "host_state", "annual-contribution", "text", "Total annual contribution: 2,200,000 EUR"),
    (3, "host_state", "security-provision", "note", "it has added a provision on public security in Article 11."),
    (3, "organisation", "security-provision", "note", "It is still studying the new paragraphs of Articles 10 and 11 and reserves its position on them."),
    (1, "host_state", "security-provision", "text", "precautions in the interest of its security."),
    (2, "organisation", "security-provision", "text", "after consulting the Director-General and so far as possible without interfering with the work of the Organisation."),
    (3, "host_state", "security-provision", "text", "they may enter the premises without the consent of the Director-General."),
]
ISSUES = ("premises-access", "tax-relief", "entry-period", "dependants", "dispute-settlement",
          "termination-notice", "annual-contribution", "security-provision")
# The unit each issue stated in figures is declared in (D-S70 item 4): the words the notes write
# right after the figure, the operator's own, read by position_gaps as written. Declared by the
# case, never derived from the text.
UNITS = {"tax-relief": "EUR", "entry-period": "days", "termination-notice": "months", "annual-contribution": "EUR"}
# The party the round 3 support is for, and the issues still open after round 3, each with the
# articles and annexes that hold it. Declared by the case, never derived from the text.
SUPPORTED = "organisation"
OPEN_ISSUES = {"tax-relief": ("Article 8", "Article 10"), "entry-period": ("Article 9", "Article 10"),
               "dependants": ("Article 9",), "annual-contribution": ("Annex II",),
               "security-provision": ("Article 4", "Article 11")}
# The Organisation's own position and fallback on each open issue, as its delegation would brief.
POSITIONS = {
    "tax-relief": ("Exemption on every purchase for official use, with no threshold.",
                   "A threshold of 1,000 EUR, with refunds decided in the Agreement itself."),
    "entry-period": ("Every application decided within 14 days.", "Every application decided within 21 days."),
    "dependants": ("Dependants may take up employment.", "Dependants may apply for a work authorisation."),
    "annual-contribution": ("An annual contribution of 2,600,000 EUR.", "An annual contribution of 2,200,000 EUR."),
    "security-provision": ("No entry without the express consent of the Director-General.",
                           "Entry without consent only in a fire or a like emergency, as Article 4 already says."),
}

CONVENTIONS = """# Legal review conventions

Synthetic rules for demonstration only. These are general rules a legal officer applies to a
negotiating text, whatever its subject.

## CONV-H01 Consistency between articles [required] [conformance]

An article, whatever its article status, must not provide the opposite of another article of the same text. Where two articles govern the same conduct, they must be capable of being applied together.

## CONV-H02 Cross-references [required] [conformance]

A reference in the text to an article or a paragraph, whatever the article status, must lead to a provision that exists in this version and that deals with the subject the reference names.

## CONV-H03 Same period and same amount [required] [conformance]

A period or an amount stated for one purpose, whatever the article status, must be the same wherever that purpose is stated in the text, the annexes included.

## CONV-H04 Defined terms [required] [conformance]

A term defined in Article 1 must be used in that form throughout the text, whatever the article status, and a term replaced in one article must be replaced in every article.

## CONV-H05 Contribution arithmetic [required] [conformance]

The total annual contribution must equal the sum of the annual contribution of every contribution line.

## CONV-H06 Position notes [required] [conformance]

Where a delegation's position note for the round records something as agreed in principle, or asks for it to be provided, the text must provide it or the article status must stay open, and a reader must be told which.
"""


def document_name(rnd):
    return "seat_agreement_round_%d" % rnd


def note_name(rnd, actor):
    return "note_%s_round_%d" % (actor, rnd)


def _cells(row, state):
    return [cell[state] for cell in row]


def text_md(state):
    """The state's text as Markdown: state 0 is the opening draft, 1 to 3 the rounds."""
    out = []
    for kind, value in BLOCKS:
        if kind == "title":
            out.append("# " + value)
        elif kind == "h":
            out.append("## " + value)
        elif kind == "p":
            if value[state] is not None:
                out.append(value[state])
        else:
            rows = [_cells(r, state) for r in value]
            lines = ["| %s |" % " | ".join(rows[0]), "|%s|" % "|".join("---" for _ in rows[0])]
            lines += ["| %s |" % " | ".join(r) for r in rows[1:]]
            out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def note_md(rnd, actor):
    head = ["# Position note of %s, round %d" % (ACTOR_NAME[actor], rnd), SYNTHETIC, "## Position"]
    return "\n\n".join(head + NOTES[(rnd, actor)]) + "\n"


def expected_read(state):
    """What the extractor reads from a .docx of this state: its Markdown, whole."""
    return text_md(state).rstrip("\n")


def reads_as_round(reading, rnd):
    """Does a .docx's accepted reading equal this round's text? The comparison --check makes."""
    return reading == expected_read(rnd)


def flat_read(state):
    """The words of this state as read_rejected gives them: paragraphs, then table rows."""
    parts = []
    for kind, value in BLOCKS:
        if kind in ("title", "h"):
            parts.append(value)
        elif kind == "p" and value[state] is not None:
            parts.append(value[state])
    for kind, value in BLOCKS:
        if kind == "table":
            parts += ["\t".join(_cells(r, state)) for r in value]
    return "\n".join(parts)


# ---- the tracked .docx -------------------------------------------------------------------------

class Revisions:
    """Numbers each tracked change and writes it for one round's author and date."""

    def __init__(self, rnd):
        self.next_id = 100
        self.attrs = 'w:author="%s" w:date="%s"' % (AUTHOR[rnd], WHEN[rnd])

    def mark(self):
        self.next_id += 1
        return 'w:id="%d" %s' % (self.next_id, self.attrs)


def _run(text, tag="t"):
    return '<w:r><w:%s xml:space="preserve">%s</w:%s></w:r>' % (tag, escape(text), tag)


def _add(paragraph, xml):
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    wrapper = parse_xml("<w:p %s>%s</w:p>" % (nsdecls("w"), xml))
    for child in list(wrapper):
        paragraph._p.append(child)


def _fill(paragraph, before, after, revisions):
    """Runs turning `before` into `after`, word by word, as tracked changes."""
    a, b = re.findall(r"\s+|\S+", before), re.findall(r"\s+|\S+", after)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            _add(paragraph, _run("".join(a[i1:i2])))
            continue
        if i2 > i1:
            _add(paragraph, "<w:del %s>%s</w:del>" % (revisions.mark(), _run("".join(a[i1:i2]), "delText")))
        if j2 > j1:
            _add(paragraph, "<w:ins %s>%s</w:ins>" % (revisions.mark(), _run("".join(b[j1:j2]))))


def _mark(paragraph, kind, revisions):
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    paragraph._p.get_or_add_pPr().append(
        parse_xml("<w:rPr %s><w:%s %s/></w:rPr>" % (nsdecls("w"), kind, revisions.mark())))


def _outline_zero():
    """Outline level 1 in Word's terms, set on the title: Word's Title style carries none."""
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    return parse_xml('<w:outlineLvl %s w:val="0"/>' % nsdecls("w"))


def round_docx(rnd):
    """The bytes of round `rnd`'s .docx: its text, tracked against the state before."""
    import docx
    document = docx.Document()
    revisions = Revisions(rnd)
    for kind, value in BLOCKS:
        if kind == "title":
            title = document.add_paragraph(value, style="Title")
            title._p.get_or_add_pPr().append(_outline_zero())
        elif kind == "h":
            document.add_paragraph(value, style="Heading 2")
        elif kind == "p":
            before, after = value[rnd - 1], value[rnd]
            if before is None and after is None:
                continue
            paragraph = document.add_paragraph()
            if before is None:
                _add(paragraph, "<w:ins %s>%s</w:ins>" % (revisions.mark(), _run(after)))
                _mark(paragraph, "ins", revisions)
            elif after is None:
                _add(paragraph, "<w:del %s>%s</w:del>" % (revisions.mark(), _run(before, "delText")))
                _mark(paragraph, "del", revisions)
            else:
                _fill(paragraph, before, after, revisions)
        else:
            table = document.add_table(rows=len(value), cols=len(value[0]))
            table.style = "Table Grid"
            for r, row in enumerate(value):
                for c, cell in enumerate(row):
                    _fill(table.cell(r, c).paragraphs[0], cell[rnd - 1], cell[rnd], revisions)
    section = document.sections[0]
    section.header.paragraphs[0].text = SYNTHETIC
    settings = document.settings.element
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    anchor = settings.find(qn("w:defaultTabStop"))
    if anchor is not None:
        anchor.addprevious(OxmlElement("w:trackRevisions"))
    stamp = datetime.datetime(2026, 1, 1, 9, 0, 0)
    props = document.core_properties
    props.author = props.last_modified_by = "Synthetic case builder"
    props.title, props.comments = TITLE, SYNTHETIC
    props.created = props.modified = stamp
    props.revision = rnd
    raw = io.BytesIO()
    document.save(raw)
    return _fixed_zip(raw.getvalue())


def _fixed_zip(data):
    """The same package with fixed member dates and order, so a build is byte-stable."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for name in sorted(source.namelist(), key=lambda n: (n != "[Content_Types].xml", n)):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, source.read(name))
    return out.getvalue()


def _rejected_paragraphs(paragraphs):
    """A paragraph list as it stood with every tracked change rejected."""
    out, joined = [], ""
    for paragraph in paragraphs:
        text = joined
        for run in paragraph._p.xpath("w:r | w:del/w:r"):
            text += "".join(t.text or "" for t in run.xpath("w:t | w:delText"))
        joined = ""
        if paragraph._p.xpath("w:pPr/w:rPr/w:ins"):
            joined = text
        else:
            out.append(text)
    if joined:
        out.append(joined)
    return out


def read_rejected(path):
    import docx
    document = docx.Document(str(path))
    parts = _rejected_paragraphs(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            parts.append("\t".join("\n".join(_rejected_paragraphs(c.paragraphs)) for c in row.cells))
    return "\n".join(parts)


def docx_reading(data):
    """{accepted, rejected} of .docx bytes: the first through the pipeline's own extractor."""
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import text_extract
    with tempfile.TemporaryDirectory(prefix="shimmer_case_docx_") as td:
        path = Path(td) / "round.docx"
        path.write_bytes(data)
        return {"accepted": text_extract.extract_text(path), "rejected": read_rejected(path)}


# ---- the workload --------------------------------------------------------------------------

def unit_spans(text, document_id):
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import pairing_map
    out, cursor = [], 0
    for unit in pairing_map.split_units(text, document_id=document_id):
        body = unit["text"].strip()
        start = text.find(body, cursor)
        if start < 0:
            raise ValueError("unit %s is not a contiguous run of its document" % unit["unit_id"])
        out.append((unit["unit_id"], start, start + len(body)))
        cursor = start + len(body)
    return out


def documents():
    """{document id: text} of every case document."""
    docs = {document_name(r): expected_read(r) for r in ROUNDS}
    for rnd, actor in NOTES:
        docs[note_name(rnd, actor)] = note_md(rnd, actor)
    return docs


def stated_sources():
    """One source per (round, actor, issue), as multi_round_phase needs for an accepted position:
    a party's note states its position, so the text speaks for it only where it wrote no note on
    the issue."""
    noted = {(r, a, i) for r, a, i, kind, _q in SOURCES if kind == "note"}
    return [s for s in SOURCES if s[3] == "note" or (s[0], s[1], s[2]) not in noted]


def issue_rows(docs):
    """The issues, with what the case declares of each one still open."""
    last = document_name(3)
    slugs = [u for u, _a, _b in unit_spans(docs[last], last)]

    def units(heading):
        held = [u.split("-", 1)[1] for u in slugs if u.split("-", 1)[1].startswith(heading.lower().replace(" ", "-") + "-")]
        if len(held) != 1:
            raise ValueError("%s names %d units" % (heading, len(held)))
        return held[0]
    rows = []
    for issue in ISSUES:
        row = dict(issue_id=issue)
        if issue in UNITS:
            row["unit"] = UNITS[issue]
        if issue in OPEN_ISSUES:
            row.update(open=True, text_units=[units(h) for h in OPEN_ISSUES[issue]],
                       position=POSITIONS[issue][0], fallback=POSITIONS[issue][1],
                       closed_units=agreed_units(docs))
        rows.append(row)
    return rows


def agreed_units(docs):
    """The units of the last round both delegations recorded as agreed: their status line reads
    agreed ad referendum, not proposed. Declared in the manifest, never read from text at run time."""
    last = document_name(3)
    return sorted(u.split("-", 1)[1] for u, a, b in unit_spans(docs[last], last) if AGREED in docs[last][a:b])


def sources(docs):
    out, seen = [], {}
    for rnd, actor, issue, kind, quote in stated_sources():
        doc = document_name(rnd) if kind == "text" else note_name(rnd, actor)
        if kind == "text" and actor != TEXT_ACTOR[rnd]:
            raise ValueError("round %d's text is not the %s's" % (rnd, actor))
        text = docs[doc]
        start = text.find(quote)
        if start < 0 or text.find(quote, start + 1) >= 0:
            raise ValueError("%s does not hold exactly once: %r" % (doc, quote))
        end = start + len(quote)
        held = [u for u, a, b in unit_spans(text, doc) if a <= start and end <= b]
        if len(held) != 1:
            raise ValueError("a quote in %s is held by %d units" % (doc, len(held)))
        key = (rnd, actor, issue)
        seen[key] = seen.get(key, 0) + 1
        out.append(dict(source_id="r%d-%s-%s-%d" % (rnd, actor, issue, seen[key]), round_id="r%d" % rnd,
                        actor_id=actor, issue_id=issue, document_id=doc, unit_id=held[0],
                        char_start=start, char_end=end, quote=quote, state="accepted"))
    return out


def build():
    """{path relative to the case folder: bytes} of everything but EXPECTED.md: workload/ and ordinary/."""
    docs = documents()
    manifest = dict(
        schema_version=1, case_id=CASE_ID, fixture=False,
        rounds=[dict(round_id="r%d" % r, sequence=r,
                     document_ids=[document_name(r)] + sorted(note_name(k, a) for k, a in NOTES if k == r))
                for r in ROUNDS],
        actors=[dict(actor_id="host_state"), dict(actor_id="organisation", supported=True)],
        issues=issue_rows(docs),
        sources=sources(docs))
    texts = {document_name(r) for r in ROUNDS}
    names = {n: n + (".docx" if n in texts else ".md") for n in docs}
    target, prior = names[document_name(3)], names[document_name(2)]
    targets = dict(targets=[target], grounding=sorted(v for v in names.values() if v != target),
                   prior=[prior], source="operator", resolved_at="")
    files = {"workload/case_manifest.json": (json.dumps(manifest, indent=2, ensure_ascii=True) + "\n").encode("ascii"),
             "workload/_review_targets.json": (json.dumps(targets, indent=2) + "\n").encode("ascii"),
             "workload/conventions/legal_review_conventions.md": CONVENTIONS.encode("utf-8")}
    for rnd, actor in NOTES:
        files["workload/context/%s.md" % note_name(rnd, actor)] = docs[note_name(rnd, actor)].encode("utf-8")
    for rnd in ROUNDS:
        files["workload/context/%s.docx" % document_name(rnd)] = round_docx(rnd)
    return with_ordinary(files)


def with_ordinary(files):
    """`files` and its ordinary/ folder: the workload's members without case_manifest.json, the
    ordinary two-version review of section 12, committed so it is sealed as it stands."""
    out = dict(files)
    for name, data in files.items():
        if name.startswith("workload/") and name != "workload/case_manifest.json":
            out["ordinary/" + name[len("workload/"):]] = data
    return out


# Written by hand, before any run, beside the case: never built, never in workload/ or ordinary/.
HANDWRITTEN = ("EXPECTED.md", "EXPECTED_MOVEMENT.json", "ROUND3_RUBRIC.md")


def on_disk(folder=CASE):
    """The built files on disk, text LF-normalised (a Windows checkout writes CRLF); the files in
    HANDWRITTEN are written by hand and are not part of the build."""
    folder = Path(folder)
    out = {}
    for path in sorted(folder.rglob("*")):
        name = path.relative_to(folder).as_posix()
        if path.is_file() and name not in HANDWRITTEN:
            data = path.read_bytes()
            out[name] = data if name.endswith(".docx") else data.replace(b"\r\n", b"\n")
    return out


def compare(files, disk):
    """(names that differ, proof per round). A .docx compares on what it reads as, so a different
    python-docx cannot fail the check; its reading is proven against the versions either way."""
    differ = sorted(n for n in set(files) ^ set(disk))
    for name in sorted(set(files) & set(disk)):
        if name.endswith(".docx"):
            if docx_reading(files[name]) != docx_reading(disk[name]):
                differ.append(name)
        elif files[name] != disk[name]:
            differ.append(name)
    proofs = {}
    for rnd in ROUNDS:
        name = "workload/context/%s.docx" % document_name(rnd)
        reading = docx_reading(disk.get(name, files[name]))
        proofs[rnd] = dict(accepted_is_this_round=reads_as_round(reading["accepted"], rnd),
                           rejected_is_the_state_before=reading["rejected"] == flat_read(rnd - 1))
    return differ, proofs


def write_ordinary(folder):
    """The ordinary two-version review of section 12: the workload without its case manifest."""
    folder = Path(folder)
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("the folder is not empty: %s" % folder.name)
    count = 0
    for name, data in build().items():
        if name.startswith("workload/") and name != "workload/case_manifest.json":
            target = folder / name[len("workload/"):]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            count += 1
    return count


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--ordinary-out" in argv:
        print("%d members written" % write_ordinary(argv[argv.index("--ordinary-out") + 1]))
        return 0
    files = build()
    if "--check" in argv:
        differ, proofs = compare(files, on_disk())
        good = not differ and all(all(p.values()) for p in proofs.values())
        print("case folder %s the build; %d rounds read as their versions" % (
            "matches" if not differ else "DIFFERS FROM", sum(all(p.values()) for p in proofs.values())))
        for name in differ:
            print("  differs:", name)
        return 0 if good else 1
    for name, data in files.items():
        target = CASE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print("%d files written under %s" % (len(files), CASE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
