"""
Part-5/fetch_corpus.py -- DATA-260 HW3, Part 2 corpus builder

Downloads a handful of real, public SJSU pages relevant to the assigned
domain (DOMAIN_ID 0: Campus course catalogue and enrolment -- course program
pages plus registrar add/drop/withdrawal policy pages), strips them down to
plain readable text (nav/header/footer/script/style removed), and saves each
as a local .txt snapshot under corpus/. This is a one-time, reproducible step;
the actual chunking/retrieval comparison scripts read only the local files
afterward, never the network.

Run once to (re)build the corpus:
    python fetch_corpus.py
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

# Menus/sidebars on these pages often aren't wrapped in a literal <nav> tag
# (e.g. a Drupal block rendered as a plain <div>/<ul>), so <nav> removal alone
# leaves a wall of one- or two-word menu-item lines ahead of the real content.
# Catch those by id/class pattern too.
BOILERPLATE_PATTERN = re.compile(
    r"sidebar|menu|breadcrumb|skip-link|skip-to|site-nav|global-nav|mega-?menu|"
    r"cookie|social-share|site-footer|site-header",
    re.IGNORECASE,
)

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "corpus"

SOURCES = [
    {
        "url": "https://www.sjsu.edu/registrar/calendar/fall-2026.php",
        "filename": "sjsu_fall_2026_dates_deadlines.txt",
        "title": "Fall 2026 Dates and Deadlines (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/calendar/spring-2027.php",
        "filename": "sjsu_spring_2027_dates_deadlines.txt",
        "title": "Spring 2027 Dates and Deadlines (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/cs/programs/bsds/index.php",
        "filename": "sjsu_bs_data_science_program.txt",
        "title": "Bachelor of Science in Data Science (SJSU Dept. of Computer Science)",
    },
    {
        "url": "https://www.sjsu.edu/ue/student-petitions/drops/index.php",
        "filename": "sjsu_late_drop_withdrawal_petitions.txt",
        "title": "Undergraduate Late Drop and Semester Withdrawal (SJSU)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/faculty-staff/important-bulletins/spring-2026-registration-bulletin.php",
        "filename": "sjsu_spring_2026_registration_bulletin.txt",
        "title": "Spring 2026 Registration Bulletin (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/registration/repeat-grade-forgiveness.php",
        "filename": "sjsu_repeat_grade_forgiveness.txt",
        "title": "Repeats and Grade Forgiveness (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/academic-records/grade-changes.php",
        "filename": "sjsu_grade_changes.txt",
        "title": "Grades / Grade Changes (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/academic-records/inadmissible-repeat.php",
        "filename": "sjsu_inadmissible_repeat_faq.txt",
        "title": "Repeats: Unauthorized/Inadmissible FAQs (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/ue/student-petitions/index.php",
        "filename": "sjsu_student_petitions.txt",
        "title": "Student Petitions (SJSU Undergraduate Education)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/registration/registration-basics/index.php",
        "filename": "sjsu_registration_basics.txt",
        "title": "Registration Basics (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/registration/enrollment-limit-waitlist.php",
        "filename": "sjsu_enrollment_limit_waitlist.txt",
        "title": "Enrollment Limits and Waitlist (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/cs/programs/mscs/requirements-for-graduation.php",
        "filename": "sjsu_mscs_requirements_for_graduation.txt",
        "title": "MSCS Requirements for Graduation (SJSU Dept. of Computer Science)",
    },
    {
        "url": "https://www.sjsu.edu/cs/programs/mscs/index.php",
        "filename": "sjsu_mscs_program_overview.txt",
        "title": "Master of Science in Computer Science (SJSU Dept. of Computer Science)",
    },
    {
        "url": "https://www.sjsu.edu/cs/programs/mscs/how-to-apply.php",
        "filename": "sjsu_mscs_how_to_apply.txt",
        "title": "MSCS How To Apply (SJSU Dept. of Computer Science)",
    },
    {
        "url": "https://www.sjsu.edu/cs/programs/mscs/mscs-faq.php",
        "filename": "sjsu_mscs_faq.txt",
        "title": "MSCS FAQ (SJSU Dept. of Computer Science)",
    },
    {
        "url": "https://www.sjsu.edu/admissions/graduate/admission-requirements/index.php",
        "filename": "sjsu_graduate_admission_requirements.txt",
        "title": "Graduate Admission Requirements (SJSU Admissions)",
    },
    {
        "url": "https://www.sjsu.edu/admissions/graduate/want-to-apply/international-steps-to-admission/index.php",
        "filename": "sjsu_international_steps_to_admission.txt",
        "title": "International Steps to Admission (SJSU Admissions)",
    },
    {
        "url": "https://www.sjsu.edu/essc/undergraduate/tep/faq.php",
        "filename": "sjsu_transfer_credit_faq_essc.txt",
        "title": "Transfer Credit FAQ (SJSU Engineering Student Success Center)",
    },
    {
        "url": "https://www.sjsu.edu/registrar/academic-records/transfer-credit.php",
        "filename": "sjsu_transferring_credits.txt",
        "title": "Transferring Credits from Other Institutions to SJSU (SJSU Office of the Registrar)",
    },
    {
        "url": "https://www.sjsu.edu/science-ssc/advising/major/index.php",
        "filename": "sjsu_major_ge_advising.txt",
        "title": "Major & General Education Advising (SJSU College of Science)",
    },
    {
        "url": "https://www.sjsu.edu/socsci-ssc/academic-advising/index.php",
        "filename": "sjsu_socsci_academic_advising.txt",
        "title": "Academic Advising (SJSU College of Social Sciences Student Success Center)",
    },
    {
        "url": "https://www.sjsu.edu/socsci-ssc/student-resources/probation-advising/index.php",
        "filename": "sjsu_socsci_academic_notice.txt",
        "title": "Academic Notice (SJSU College of Social Sciences Student Success Center)",
    },
    {
        "url": "https://www.sjsu.edu/chhs-ssc/student-resources/faqs.php",
        "filename": "sjsu_chhs_faqs.txt",
        "title": "Frequently Asked Questions (SJSU CHHS Student Success Center)",
    },
    {
        "url": "https://www.sjsu.edu/socsci-ssc/student-resources/probation-advising/continued-probation.php",
        "filename": "sjsu_socsci_continued_probation.txt",
        "title": "Continued Academic Notice (SJSU College of Social Sciences Student Success Center)",
    },
    {
        "url": "https://www.sjsu.edu/cs/students/undergrad-students/faq.php",
        "filename": "sjsu_cs_undergrad_faq.txt",
        "title": "Undergraduate FAQ (SJSU Dept. of Computer Science)",
    },
    {
        "url": "https://www.sjsu.edu/comm/undergraduate/faq.php",
        "filename": "sjsu_comm_undergrad_faq.txt",
        "title": "FAQ (SJSU Dept. of Communication Studies)",
    },
    {
        "url": "https://www.sjsu.edu/ue/student-petitions/faq/index.php",
        "filename": "sjsu_student_petitions_faq.txt",
        "title": "Student Petitions FAQ (SJSU Undergraduate Education)",
    },
    {
        "url": "https://www.sjsu.edu/general-education/ge-requirements/index.php",
        "filename": "sjsu_ge_requirements.txt",
        "title": "General Education Requirements (SJSU)",
    },
    {
        "url": "https://www.sjsu.edu/ise/programs/faq.php",
        "filename": "sjsu_ise_programs_faq.txt",
        "title": "Programs FAQ (SJSU Dept. of Industrial and Systems Engineering)",
    },
    {
        "url": "https://www.sjsu.edu/lcobssc/advising/faq.php",
        "filename": "sjsu_lcob_advising_faq.txt",
        "title": "Advising FAQ (SJSU Jack Holland Student Success Center, Lucas College of Business)",
    },
    {
        "url": "https://www2.sjsu.edu/luriessc/student-resources/frequently-asked-questions.php",
        "filename": "sjsu_lurie_ssc_faq.txt",
        "title": "Frequently Asked Questions (SJSU Lurie College of Education Student Success Center)",
    },
    {
        "url": "https://www.sjsu.edu/newspartans/faq.php",
        "filename": "sjsu_new_student_faq.txt",
        "title": "FAQ (SJSU New Student and Family Programs)",
    },
]


def fetch_and_clean(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (DATA-260 HW3 coursework fetch)"})
    with urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg", "form", "aside"]):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": BOILERPLATE_PATTERN}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": BOILERPLATE_PATTERN}):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]

    # Menu items that survive the structural removal above tend to be short,
    # punctuation-free lines packed tightly together (a real sentence nearly
    # always ends in ./?/!/:). Drop runs of 4+ consecutive such lines -- a
    # single short heading here and there is left alone.
    def is_menu_like(line: str) -> bool:
        return len(line.split()) <= 6 and not line.rstrip().endswith((".", "?", "!", ":", '"'))

    out = []
    i = 0
    while i < len(lines):
        if is_menu_like(lines[i]):
            j = i
            while j < len(lines) and is_menu_like(lines[j]):
                j += 1
            if j - i >= 4:
                i = j
                continue
        out.append(lines[i])
        i += 1

    cleaned = "\n".join(out)
    return cleaned


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    access_date = time.strftime("%Y-%m-%d")

    for src in SOURCES:
        print(f"fetching {src['url']} ...")
        text = fetch_and_clean(src["url"])
        out_path = CORPUS_DIR / src["filename"]
        out_path.write_text(text, encoding="utf-8")

        data = out_path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        manifest.append({
            "filename": src["filename"],
            "title": src["title"],
            "source_url": src["url"],
            "access_date": access_date,
            "byte_size": len(data),
            "sha256": sha256,
        })
        print(f"  saved {src['filename']}: {len(data)} bytes, sha256={sha256[:12]}...")

    total = sum(m["byte_size"] for m in manifest)
    print(f"\ntotal corpus size: {total} bytes ({total/1024:.1f} KB)")

    manifest_path = HERE.parent / "reports" / "hw03" / "CORPUS_MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": manifest}, f, indent=2)
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()
