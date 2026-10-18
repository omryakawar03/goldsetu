from decimal import Decimal
import unittest
from app.domain.money import metal_value_paise, paise_to_rupees, rupees_to_paise
from app.domain.models import InvoiceDocument, InvoiceStatus, InvoiceLineSnapshot, JournalEntryDocument, JournalLine, PaymentDocument, PaymentStatus, PledgeAccountDocument, JewelleryItemDocument


class MoneyTests(unittest.TestCase):
    def test_rupees_round_half_up_to_integer_paise(self):
        self.assertEqual(rupees_to_paise("12.345"), 1235)
        self.assertEqual(paise_to_rupees(1235), Decimal("12.35"))

    def test_money_rejects_binary_float(self):
        with self.assertRaisesRegex(ValueError, "floating-point"):
            rupees_to_paise(1.25)

    def test_metal_amount_uses_decimal_weight_and_paise_rate(self):
        self.assertEqual(metal_value_paise("1.125", 700000), 787500)


class ModelTests(unittest.TestCase):
    def test_journal_must_balance(self):
        with self.assertRaisesRegex(ValueError, "balance"):
            JournalEntryDocument(shop_id="shop-1", transaction_id="tx-1", posted_at="2026-10-14T10:00:00Z", source_type="sale", source_id="inv-1", lines=[JournalLine(account_id="cash", debit_paise=100), JournalLine(account_id="sales", credit_paise=90)])

    def test_journal_accepts_equal_debits_and_credits(self):
        entry = JournalEntryDocument(shop_id="shop-1", transaction_id="tx-1", posted_at="2026-10-14T10:00:00Z", source_type="sale", source_id="inv-1", lines=[JournalLine(account_id="cash", debit_paise=100), JournalLine(account_id="sales", credit_paise=100)])
        self.assertEqual(entry.lines[0].debit_paise, entry.lines[1].credit_paise)

    def test_successful_payment_requires_verified_timestamp(self):
        with self.assertRaisesRegex(ValueError, "verification"):
            PaymentDocument(shop_id="s", invoice_id="i", operation_id="o", idempotency_key="k", method="upi", status=PaymentStatus.SUCCEEDED, amount_paise=100)

    def test_naive_dates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            JournalEntryDocument(shop_id="s", transaction_id="t", posted_at="2026-10-14T10:00:00", source_type="sale", source_id="i", lines=[JournalLine(account_id="a", debit_paise=10), JournalLine(account_id="b", credit_paise=10)])

    def test_jewellery_weights_reject_floats_and_inconsistent_net(self):
        with self.assertRaises(ValueError):
            JewelleryItemDocument(shop_id="s", product_id="p", serial_number="serial", gross_weight_g=1.2, stone_weight_g=0, net_metal_weight_g=1)
        with self.assertRaisesRegex(ValueError, "net metal"):
            JewelleryItemDocument(shop_id="s", product_id="p", serial_number="serial", gross_weight_g="1.0", stone_weight_g="0", net_metal_weight_g="1.1")

    def test_pledge_principal_cannot_exceed_disbursement(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            PledgeAccountDocument(shop_id="s", account_number="P1", customer_id="C1", status="open", principal_disbursed_paise=1000, principal_outstanding_paise=1001, interest_rate_basis_points=1200, interest_method="simple_daily", due_at="2026-12-01T00:00:00Z", custody_reference="locker-1", created_by="staff-1")

    def test_invoice_total_is_validated(self):
        line = InvoiceLineSnapshot(product_id="p", description="Ring", taxable_value_paise=100, tax_paise=3, total_paise=103)
        invoice = InvoiceDocument(shop_id="s", branch_id="b", invoice_number="FY26-1", financial_year="2026-27", operation_id="op", status=InvoiceStatus.PENDING_SYNC, lines=[line], subtotal_paise=100, tax_paise=3, total_paise=103)
        self.assertEqual(invoice.total_paise, 103)
        with self.assertRaisesRegex(ValueError, "invoice total"):
            InvoiceDocument(shop_id="s", branch_id="b", invoice_number="FY26-2", financial_year="2026-27", operation_id="op2", status=InvoiceStatus.PENDING_SYNC, lines=[line], subtotal_paise=100, tax_paise=3, total_paise=104)


if __name__ == "__main__":
    unittest.main()

