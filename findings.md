# Findings

These are my highlevel first findings:

1. data/raw/reports/example_reports/TeaStoreReports/Cypress_Mocha/Cypress_TeaStore_Report_Original_Noise_2.html and data/raw/reports/example_reports/TeaStoreReports/Cypress_Mocha/Cypress_TeaStore_Report_Original_Noise_3.html are the same => same SHA

2. all tests PASS ... => can not test fail bahaviour (also for Locust...)

3. if we now insert the Mocha we encouter the backdated on purpose error => needs a redesign since this behaviour could happen in the field

4. report to gate mapping currently of since currently: Report <=> Gate 