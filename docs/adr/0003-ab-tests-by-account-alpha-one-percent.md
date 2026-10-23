# 3. A/B tests randomise by account, at alpha 1%, in whole weeks

Status: accepted

A customer who contacts support twice must meet the same release, and their conversations are not
independent, so assignment hashes the account and analysis uses the delta method on account-level
ratios. Many tests run all the time, so alpha is 1%. Sample sizes come from a power analysis for a
2pp change and are rounded up to whole weeks so that the weekday mix is the same in both arms.

Consequences: tests take three weeks at current traffic and cannot see gains under about 2pp; the
process study measures how many small real wins that leaves on the table.
