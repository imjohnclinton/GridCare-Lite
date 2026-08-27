
import os
import sys
import unittest
 
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
import auth
 
 
class GridCareTestBase(unittest.TestCase):
    def setUp(self):
        self.db_path = ':memory:'
        self.conn = db.init_db(self.db_path)
        # Seed one substation and one user of each role for use across tests
        self.conn.execute(
            "INSERT INTO substations (substation_id, name, region, voltage_kv, status) "
            "VALUES (1, 'Achimota Substation', 'Greater Accra', 11, 'Active')")
        self.conn.commit()
        self.admin_id = auth.register_user(self.conn, 'admin1', 'Password1!', 'Ama Admin', 'admin')
        self.engineer_id = auth.register_user(self.conn, 'eng1', 'Password1!', 'Kofi Engineer', 'engineer')
        self.tech_id = auth.register_user(self.conn, 'tech1', 'Password1!', 'Yaw Tech', 'technician')
        self.cs_id = auth.register_user(self.conn, 'cs1', 'Password1!', 'Efua CS', 'customer_service')
 
    def tearDown(self):
        self.conn.close()
 
 
class TestAuth(GridCareTestBase):
    def test_register_and_login_success(self):
        user = auth.authenticate(self.conn, 'admin1', 'Password1!')
        self.assertEqual(user['role'], 'admin')
 
    def test_login_wrong_password_fails(self):
        with self.assertRaises(db.GridCareError):
            auth.authenticate(self.conn, 'admin1', 'wrongpass')
 
    def test_login_nonexistent_user_fails(self):
        with self.assertRaises(db.GridCareError):
            auth.authenticate(self.conn, 'ghost', 'Password1!')
 
    def test_login_empty_credentials_fails(self):
        with self.assertRaises(db.GridCareError):
            auth.authenticate(self.conn, '', '')
 
    def test_duplicate_username_rejected(self):
        with self.assertRaises(db.GridCareError):
            auth.register_user(self.conn, 'admin1', 'Password1!', 'Another Admin', 'admin')
 
    def test_invalid_role_rejected(self):
        with self.assertRaises(db.GridCareError):
            auth.register_user(self.conn, 'newuser', 'Password1!', 'Someone', 'superuser')
 
    def test_short_password_rejected(self):
        with self.assertRaises(db.GridCareError):
            auth.register_user(self.conn, 'newuser2', 'short', 'Someone', 'engineer')
 
    def test_password_is_hashed_not_plaintext(self):
        row = self.conn.execute("SELECT password_hash FROM users WHERE username='admin1'").fetchone()
        self.assertNotEqual(row['password_hash'], 'Password1!')
 
 
class TestOutages(GridCareTestBase):
    def test_create_outage_against_valid_substation(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Transformer fault', 'High')
        self.assertIsNotNone(outage_id)
        outages = db.list_outages(self.conn)
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0]['status'], 'Open')
 
    def test_create_outage_against_nonexistent_substation_fails(self):
        with self.assertRaises(db.GridCareError):
            db.create_outage(self.conn, 999, self.engineer_id, 'Fault at nonexistent station')
 
    def test_create_outage_empty_description_fails(self):
        with self.assertRaises(db.GridCareError):
            db.create_outage(self.conn, 1, self.engineer_id, '   ')
 
    def test_create_outage_invalid_severity_fails(self):
        with self.assertRaises(db.GridCareError):
            db.create_outage(self.conn, 1, self.engineer_id, 'Fault', severity='Catastrophic')
 
    def test_update_outage_status_valid_transition(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        db.update_outage_status(self.conn, outage_id, 'In Progress', self.admin_id)
        outages = db.list_outages(self.conn, status='In Progress')
        self.assertEqual(len(outages), 1)
 
    def test_update_outage_status_invalid_value_fails(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        with self.assertRaises(db.GridCareError):
            db.update_outage_status(self.conn, outage_id, 'Cancelled', self.admin_id)
 
    def test_update_nonexistent_outage_fails(self):
        with self.assertRaises(db.GridCareError):
            db.update_outage_status(self.conn, 9999, 'Resolved', self.admin_id)
 
    def test_resolving_outage_sets_resolved_at(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        db.update_outage_status(self.conn, outage_id, 'Resolved', self.admin_id)
        row = self.conn.execute('SELECT resolved_at FROM outages WHERE outage_id=?', (outage_id,)).fetchone()
        self.assertIsNotNone(row['resolved_at'])
 
    def test_status_history_recorded(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        db.update_outage_status(self.conn, outage_id, 'In Progress', self.admin_id)
        history = self.conn.execute(
            "SELECT * FROM status_history WHERE entity_type='outage' AND entity_id=?", (outage_id,)
        ).fetchall()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['old_status'], 'Open')
        self.assertEqual(history[0]['new_status'], 'In Progress')
 
 
class TestWorkOrders(GridCareTestBase):
    def test_create_work_order_valid(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        wo_id = db.create_work_order(self.conn, outage_id, self.tech_id, self.admin_id, '2026-09-01')
        self.assertIsNotNone(wo_id)
 
    def test_create_work_order_nonexistent_outage_fails(self):
        with self.assertRaises(db.GridCareError):
            db.create_work_order(self.conn, 9999, self.tech_id, self.admin_id)
 
    def test_create_work_order_assigning_non_technician_fails(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        with self.assertRaises(db.GridCareError):
            db.create_work_order(self.conn, outage_id, self.engineer_id, self.admin_id)
 
    def test_technician_sees_assigned_work_orders(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        db.create_work_order(self.conn, outage_id, self.tech_id, self.admin_id)
        orders = db.list_work_orders_for_technician(self.conn, self.tech_id)
        self.assertEqual(len(orders), 1)
 
    def test_full_outage_to_resolution_workflow(self):
        # Mirrors the demonstration sequence in the spec.
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Line down', 'High')
        wo_id = db.create_work_order(self.conn, outage_id, self.tech_id, self.admin_id, '2026-09-01')
        db.update_work_order_status(self.conn, wo_id, 'Scheduled', self.admin_id)
        db.update_outage_status(self.conn, outage_id, 'In Progress', self.tech_id)
        db.update_work_order_status(self.conn, wo_id, 'Completed', self.tech_id, work_notes='Replaced fuse')
        db.update_outage_status(self.conn, outage_id, 'Resolved', self.tech_id)
 
        outage = db.list_outages(self.conn)[0]
        self.assertEqual(outage['status'], 'Resolved')
        wo = self.conn.execute('SELECT * FROM work_orders WHERE work_order_id=?', (wo_id,)).fetchone()
        self.assertEqual(wo['status'], 'Completed')
        self.assertEqual(wo['work_notes'], 'Replaced fuse')
 
    def test_invalid_work_order_status_fails(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        wo_id = db.create_work_order(self.conn, outage_id, self.tech_id, self.admin_id)
        with self.assertRaises(db.GridCareError):
            db.update_work_order_status(self.conn, wo_id, 'Cancelled', self.admin_id)
 
 
class TestComplaints(GridCareTestBase):
    def test_log_complaint_without_outage_link(self):
        complaint_id = db.log_complaint(self.conn, self.cs_id, 'John Doe', 'No power since morning')
        self.assertIsNotNone(complaint_id)
 
    def test_log_complaint_linked_to_outage(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault')
        complaint_id = db.log_complaint(self.conn, self.cs_id, 'Jane Doe', 'Still no power', outage_id=outage_id)
        complaints = db.list_complaints(self.conn)
        self.assertEqual(complaints[0]['outage_id'], outage_id)
 
    def test_log_complaint_linked_to_nonexistent_outage_fails(self):
        with self.assertRaises(db.GridCareError):
            db.log_complaint(self.conn, self.cs_id, 'Jane Doe', 'Still no power', outage_id=9999)
 
    def test_log_complaint_missing_name_fails(self):
        with self.assertRaises(db.GridCareError):
            db.log_complaint(self.conn, self.cs_id, '  ', 'Details here')
 
    def test_log_complaint_missing_details_fails(self):
        with self.assertRaises(db.GridCareError):
            db.log_complaint(self.conn, self.cs_id, 'Jane Doe', '')
 
 
class TestReporting(GridCareTestBase):
    def test_dashboard_stats_reflect_data(self):
        outage_id = db.create_outage(self.conn, 1, self.engineer_id, 'Fault 1', 'High')
        db.create_outage(self.conn, 1, self.engineer_id, 'Fault 2', 'Low')
        db.update_outage_status(self.conn, outage_id, 'Resolved', self.admin_id)
        db.log_complaint(self.conn, self.cs_id, 'Someone', 'Complaint text')
 
        stats = db.get_dashboard_stats(self.conn)
        self.assertEqual(stats['open_outages'], 1)
        self.assertEqual(stats['resolved_outages'], 1)
        self.assertEqual(stats['total_complaints'], 1)
        self.assertEqual(len(stats['outages_by_region']), 1)
        self.assertEqual(stats['outages_by_region'][0]['region'], 'Greater Accra')
 
        severity_map = {row['severity']: row['c'] for row in stats['outages_by_severity']}
        self.assertEqual(severity_map, {'High': 1, 'Low': 1})
        status_map = {row['status']: row['c'] for row in stats['outages_by_status']}
        self.assertEqual(status_map, {'Resolved': 1, 'Open': 1})
 
    def test_dashboard_stats_on_empty_db(self):
        stats = db.get_dashboard_stats(self.conn)
        self.assertEqual(stats['open_outages'], 0)
        self.assertIsNone(stats['avg_resolution_days'])
 
 
class TestSubstationImport(unittest.TestCase):
    def test_import_from_csv(self):
        import csv
        import tempfile
        conn = db.init_db(':memory:')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Substation ID', 'Name', 'Short Name', 'Region', 'Country',
                              'Latitude', 'Longitude', 'Voltage (kV)', 'Capacity (MVA)',
                              'Commissioning Year', 'Type', 'Status'])
            writer.writerow([1, 'Achimota Substation', 'Achimota', 'Greater Accra', 'Ghana',
                              5.6085, -0.2193, 11, 6.4, 2008, 'Distribution', 'Active'])
            writer.writerow(['not_a_number', 'Bad Row', 'Bad', 'Nowhere', 'Ghana',
                              0, 0, 11, 0, 2000, 'Distribution', 'Active'])
            path = f.name
        imported, skipped = db.import_substations_from_csv(conn, path)
        self.assertEqual(imported, 1)
        self.assertEqual(skipped, 1)
        self.assertTrue(db.substation_exists(conn, 1))
        os.unlink(path)
 
 
if __name__ == '__main__':
    unittest.main(verbosity=2)