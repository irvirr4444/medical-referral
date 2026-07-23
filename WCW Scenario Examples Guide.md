# WCW Scenario Examples Guide

## Purpose

`scenario_examples.json` is a local, PHI-bearing companion file selected from the Master Sheet export. It provides representative real records for understanding how WCW has used its columns. This guide explains the scenarios without repeating any patient information.

## Selection Method and Limits

Each scenario is selected by a concrete status rule, then the exporter chooses the matching record with the most non-empty displayed fields. These are examples, not gold-standard business rules, not necessarily the most recent record, and not proof that every historical record follows the same convention.

## Referral Intake

**Selection rule:** `Stage = In intake`

**What it demonstrates:** Shows the expected shape of a newly received referral before case-manager/scheduling work is automated.

**Export result:** matched. The selected row contains 18 non-empty projected fields.

## Handoff

**Selection rule:** `Sent to CM = Yes`

**What it demonstrates:** Shows the downstream state after a referral has been sent to a case manager; it is a human-owned handoff example, not a V1 write target.

**Export result:** matched. The selected row contains 17 non-empty projected fields.

## Scheduled

**Selection rule:** `Scheduling Complete = Yes` and `Visit Status = Scheduled`

**What it demonstrates:** Shows the fields that collectively indicate a referral was scheduled, useful for validating a future status-integration rule.

**Export result:** matched. The selected row contains 18 non-empty projected fields.

## Seen

**Selection rule:** `Visit Status = Seen`

**What it demonstrates:** Shows the operational state for a completed visit, useful for understanding reporting and lifecycle interpretation.

**Export result:** matched. The selected row contains 17 non-empty projected fields.

## On Hold

**Selection rule:** `Visit Status = On Holds List` or `Hospitalized`

**What it demonstrates:** Shows the operational exception path for hospitalization or an active holds list; it should remain a human workflow until rules are agreed.

**Export result:** matched. The selected row contains 17 non-empty projected fields.

## Discharged

**Selection rule:** `Visit Status` is one of the discharge-prefixed values used by WCW.

**What it demonstrates:** Shows a discharge outcome. It is useful for understanding history and future reporting, not for deciding a discharge automatically.

**Export result:** matched. The selected row contains 18 non-empty projected fields.

## Safe Use

Keep `scenario_examples.json` local and out of Git because it contains patient data. Use it to validate the data dictionary with authorized WCW staff, then replace representative examples with a manually approved evaluation set for testing automation behavior.
