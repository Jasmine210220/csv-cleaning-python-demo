import csv
import tempfile
import unittest
from pathlib import Path
from clean_csv import process, normalize_date, FIELDS

ROOT = Path(__file__).parent


class CleanupTests(unittest.TestCase):
    def test_sample_and_repeatability(self):
        files = [ROOT/'inputs/orders_a.csv', ROOT/'inputs/orders_b.csv']
        first = process(files)
        self.assertEqual(first, process(files))
        _, rows, audit, report = first
        self.assertEqual((report['input_rows'],len(rows),len(audit)),(12,10,4))
        self.assertEqual(report['duplicates_removed'],2)
        self.assertEqual(report['dates_normalized'],6)
        self.assertEqual(report['date_issues'],2)
        self.assertEqual([r['order_id'] for r in rows], [f'ORD-{i}' for i in range(1001,1011)])
        self.assertEqual(rows[0]['order_date'],'2026-10-01')
        self.assertEqual(rows[4]['order_date'],'31/02/2026')
        self.assertEqual(rows[4]['date_status'],'INVALID_DATE')
        self.assertEqual(rows[7]['order_date'],'')
        self.assertEqual(rows[7]['date_status'],'MISSING_DATE')
        self.assertEqual(rows[0]['quantity'],'2')

    def check_rejected(self, content, message):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            path=Path(d)/'input.csv'
            path.write_text(content,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,message):
                process([path])

    def test_conflicting_duplicate(self):
        self.check_rejected(','.join(FIELDS)+'\nA,01/10/2026,Pen,1\nA,01/10/2026,Pen,2\n','Conflicting')

    def test_missing_id(self):
        self.check_rejected(','.join(FIELDS)+'\n,01/10/2026,Pen,1\n','missing')

    def test_schema(self):
        self.check_rejected('id,date\nA,2026-10-01\n','expected columns')

    def test_malformed(self):
        self.check_rejected(','.join(FIELDS)+'\nA,01/10/2026,Pen\n','malformed')

    def test_row_limit(self):
        self.check_rejected(','.join(FIELDS)+'\n'+''.join(f'{i},01/10/2026,Pen,1\n' for i in range(5001)),'5,000')

    def test_date_boundaries(self):
        self.assertEqual(normalize_date('29/02/2024'),('2024-02-29','OK'))
        for value in ['29/02/2025','10/19/2026','2026-13-01',' 01/10/2026']:
            self.assertEqual(normalize_date(value),(value,'INVALID_DATE'))

    def test_file_count(self):
        with self.assertRaises(ValueError):
            process([])


if __name__ == '__main__':
    unittest.main()
