import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReportLeadCaptureTests(unittest.TestCase):
    def setUp(self):
        self.page = (ROOT / "benchmark.html").read_text(encoding="utf-8")
        self.script = (ROOT / "ace-benchmark.js").read_text(encoding="utf-8")

    def test_report_download_form_captures_replyable_sales_fields(self):
        self.assertIn('id="report-lead-form"', self.page)
        for field in ("name", "email", "company", "report", "source"):
            self.assertRegex(self.page, rf'name="{field}"')
        self.assertRegex(
            self.page,
            r'name="email"[^>]*type="email"|type="email"[^>]*name="email"',
        )
        self.assertIn('autocomplete="email"', self.page)
        self.assertIn('required', self.page)

    def test_first_party_submission_includes_email_and_report_before_download(self):
        config = (ROOT / "ace-config.js").read_text(encoding="utf-8")
        self.assertIn("REPORT_LEADS_PATH: '/v1/ace/report-leads'", config)
        self.assertIn("CONFIG.API_BASE + CONFIG.REPORT_LEADS_PATH", self.script)
        self.assertIn("email: valueOf('report-lead-email')", self.script)
        self.assertIn("report: request.reportLabel", self.script)
        self.assertRegex(
            self.script,
            re.compile(
                r"fetch\(CONFIG\.API_BASE \+ CONFIG\.REPORT_LEADS_PATH"
                r".*?response\.ok.*?"
                r"ARTIFACTS\.downloadReport",
                re.DOTALL,
            ),
        )
        self.assertNotIn("formspree", self.page.lower())
        self.assertNotIn("formspree", self.script.lower())

    def test_failed_lead_submission_does_not_release_report(self):
        self.assertIn("We could not record your request", self.script)
        failure_block = self.script.split("We could not record your request", 1)[1]
        self.assertIn("return;", failure_block[:500])

    def test_lead_data_is_not_written_to_browser_storage(self):
        lead_code = self.script[self.script.index("REPORT_LEADS_PATH") :]
        self.assertNotIn("localStorage", lead_code)
        self.assertNotIn("sessionStorage", lead_code)

    def test_privacy_discloses_report_confirmation_processor(self):
        privacy = (ROOT / "privacy.html").read_text(encoding="utf-8")
        self.assertIn("Google Workspace", privacy)
        self.assertIn("requester confirmation", privacy)


if __name__ == "__main__":
    unittest.main()
