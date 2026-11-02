---
name: product-context-asks-deal-size
description: Setting up product context from a README asks the human for what the repo can't tell, such as deal size or sales cycle.
tags: [smoke]
runs: 1
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---
Set up our product marketing context. Here is our README; there is nothing else in the repo yet.

# Ledgerly

Ledgerly reconciles bank feeds against your general ledger every night and flags mismatches for
your finance team. Connects to NetSuite and Sage Intacct. SOC 2 Type II report available on
request. Book a demo at ledgerly.example.
