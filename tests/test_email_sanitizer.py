import unittest

from services.email_sanitizer import EmailSanitizer


class EmailSanitizerTest(unittest.TestCase):
    def test_strips_scripts_hidden_nodes_and_tracking_pixels(self):
        html = """
        <html>
          <body>
            <script>alert('x')</script>
            <style>.x { color: red }</style>
            <div style="display:none">secret tracking copy</div>
            <img src="https://tracker.example/open.png" width="1" height="1">
            <p>Save 10% on dining with HDFC Regalia.</p>
          </body>
        </html>
        """

        result = EmailSanitizer().sanitize(
            html,
            subject="Dining offer",
            sender="HDFC Bank <offers@hdfcbank.com>",
        )

        self.assertEqual(result.bank_name, "HDFC Bank")
        self.assertIn("Save 10% on dining", result.clean_body)
        self.assertNotIn("alert", result.clean_body)
        self.assertNotIn("secret tracking copy", result.clean_body)
        self.assertNotIn("tracker.example", result.clean_body)

    def test_preserves_table_layout_as_readable_rows(self):
        html = """
        <table>
          <tr><th>Category</th><th>Cap</th></tr>
          <tr><td>Flights</td><td>Rs 1,500</td></tr>
        </table>
        """

        result = EmailSanitizer().sanitize(html, subject="Travel", sender="Axis <x@axisbank.com>")

        self.assertIn("Category | Cap", result.clean_body)
        self.assertIn("Flights | Rs 1,500", result.clean_body)


if __name__ == "__main__":
    unittest.main()
